# lstm_model_service.py
import os
import time
import glob
import asyncio
from datetime import datetime
from typing import Optional, Dict, List

import torch
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager


# ----------------------------
# 전역 설정/경로
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ensemble_weight_dir = os.path.join(BASE_DIR, "weights", "ensemble_weights")
ensemble_threshold_dir = os.path.join(BASE_DIR, "weights", "ensemble_thresholds")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
features = [
    "종가",
    "대비",
    "등락률",
    "시가",
    "고가",
    "저가",
    "거래량",
    "거래대금",
    "시가총액",
    "상장주식수",
]
window_size = 30
n_ensembles = 10
ensemble_weights: List[Dict[str, dict]] = []
ensemble_thresholds: List[Dict[str, float]] = []


# ----------------------------
# 모델 정의
# ----------------------------
class LSTMAutoEncoder(torch.nn.Module):
    def __init__(self, input_dim, hidden_dim=64, latent_dim=16):
        super().__init__()
        self.encoder = torch.nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.latent = torch.nn.Linear(hidden_dim, latent_dim)
        self.decoder_input = torch.nn.Linear(latent_dim, hidden_dim)
        self.decoder = torch.nn.LSTM(hidden_dim, input_dim, batch_first=True)

    def forward(self, x):
        _, (h_n, _) = self.encoder(x)
        z = self.latent(h_n[-1])
        dec_input = self.decoder_input(z).unsqueeze(1).repeat(1, x.size(1), 1)
        out, _ = self.decoder(dec_input)
        return out


# ----------------------------
# 가중치/임계값 로딩
# ----------------------------
def load_models() -> None:
    """weights/thresholds 폴더에서 앙상블 10세트를 로딩."""
    global ensemble_weights, ensemble_thresholds
    if ensemble_weights and ensemble_thresholds:
        return  # 이미 로드됨

    for i in range(1, n_ensembles + 1):
        weights_path = os.path.join(ensemble_weight_dir, f"ensemble_weights_set{i}.pt")
        thresh_path = os.path.join(
            ensemble_threshold_dir, f"ensemble_thresholds_set{i}.csv"
        )

        weights = torch.load(weights_path, map_location=device)
        if not isinstance(weights, dict):
            raise ValueError(
                f"{weights_path} 내용이 dict(종목명→state_dict) 형식이 아님"
            )

        ensemble_weights.append(weights)

        df_thresh = pd.read_csv(thresh_path)
        if not {"종목명", "임계값"} <= set(df_thresh.columns):
            raise ValueError(f"{thresh_path} 컬럼에 '종목명','임계값' 필요")
        ensemble_thresholds.append(dict(zip(df_thresh["종목명"], df_thresh["임계값"])))


# ----------------------------
# KRX 크롤링 헬퍼
# ----------------------------
def _resolve_base_download_dir() -> str:
    env = os.environ.get("STOCK_INFO_DOWNLOAD_DIR")
    if env:
        base = env
    else:
        if os.name == "nt":
            base = os.path.join(
                os.environ.get("TEMP", r"C:\Temp"), "stock_info_downloads"
            )
        else:
            base = "/tmp/stock_info_downloads"
    os.makedirs(base, exist_ok=True)
    return base


def _build_chrome_options(download_dir: str) -> Options:
    opts = webdriver.ChromeOptions()
    # 필요 시 headless 사용: opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=ko-KR")
    opts.add_argument("--disable-gpu")
    prefs = {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "plugins.always_open_pdf_externally": True,
    }
    opts.add_experimental_option("prefs", prefs)
    return opts


def _wait_download_csv(download_dir: str, start_ts: float, timeout: int = 60) -> str:
    deadline = time.time() + timeout
    last_seen_csv: Optional[str] = None
    while time.time() < deadline:
        csv_candidates = []
        for path in glob.glob(os.path.join(download_dir, "*.csv")):
            try:
                if os.path.getmtime(path) >= start_ts:
                    csv_candidates.append(path)
            except FileNotFoundError:
                pass

        if csv_candidates:
            latest = max(csv_candidates, key=os.path.getmtime)
            cr_path = latest + ".crdownload"
            if not os.path.exists(cr_path):
                return latest
            last_seen_csv = latest
        time.sleep(0.5)

    raise TimeoutException(
        f"CSV 파일 다운로드 대기 시간 초과 (마지막 감지: {last_seen_csv or '없음'})"
    )


# ----------------------------
# 데이터 수집(원 코드 유지: async)
# ----------------------------
async def fetch_recent_data(stock_name: str) -> pd.DataFrame:
    if not isinstance(stock_name, str) or not stock_name.strip():
        raise ValueError("stock_name은 비어있지 않은 문자열이어야 합니다.")

    base_dir = _resolve_base_download_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    req_dir = os.path.join(base_dir, f"req_{stamp}")
    os.makedirs(req_dir, exist_ok=True)

    options = _build_chrome_options(req_dir)
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    wait = WebDriverWait(driver, 20)

    try:
        driver.get(
            "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201"
        )
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "주식"))).click()
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "종목시세"))).click()
        wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'a[data-menu-id="MDC0201020103"]')
            )
        ).click()
        time.sleep(0.8)

        wait.until(
            EC.element_to_be_clickable((By.ID, "btnisuCd_finder_stkisu0_0"))
        ).click()
        search_input = wait.until(
            EC.presence_of_element_located((By.ID, "searchText__finder_stkisu0_0"))
        )
        search_input.clear()
        search_input.send_keys(stock_name)
        time.sleep(2.5)

        wait.until(
            EC.element_to_be_clickable((By.ID, "searchBtn__finder_stkisu0_0"))
        ).click()
        time.sleep(2.5)

        # 9) 결과 테이블 첫 번째 행 클릭 (stale 방어 버전)
        grid_selector = "#jsGrid__finder_stkisu0_0 tbody tr.jsRow"
        grid_locator = (By.CSS_SELECTOR, grid_selector)

        # 결과가 나타날 때까지 대기 (한 개 이상)
        wait.until(lambda d: len(d.find_elements(*grid_locator)) > 0)

        # JS 클릭 헬퍼: WebElement 참조 없이 한 번에 처리 → stale 확률 낮음
        def _js_click_first_row():
            return driver.execute_script(
                """
                const el = document.querySelector(arguments[0]);
                if (!el) return false;
                el.scrollIntoView({block:'center'});
                el.click();
                return true;
                """,
                grid_selector,
            )

        clicked = False
        # 최대 5회 재시도 (리렌더링 대비)
        for _ in range(5):
            try:
                # 시도 1: JS로 직접 클릭
                if _js_click_first_row():
                    clicked = True
                    break
                # 시도 2: 다시 찾아서 파이썬 객체로 클릭
                rows = driver.find_elements(*grid_locator)
                if rows:
                    row = rows[0]
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", row
                    )
                    # 클릭 직전 최신 참조로 다시 가져오기
                    row = driver.find_elements(*grid_locator)[0]
                    row.click()
                    clicked = True
                    break
            except StaleElementReferenceException:
                time.sleep(0.2)  # 잠깐 대기 후 재시도
            except Exception:
                time.sleep(0.2)

        if not clicked:
            raise RuntimeError("결과 첫 행 클릭 실패(요소 stale 또는 미표시)")

        wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.cal-btn-range6m"))
        ).click()
        wait.until(EC.element_to_be_clickable((By.ID, "jsSearchButton"))).click()
        time.sleep(0.5)

        wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.CI-MDI-UNIT-DOWNLOAD"))
        ).click()
        start_ts = time.time()
        wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[data-type="csv"] a'))
        ).click()

        latest_csv = _wait_download_csv(req_dir, start_ts=start_ts, timeout=90)
        df = pd.read_csv(latest_csv, encoding="euc-kr")

        # --- 전처리: 정렬 없이 상단 30행 그대로 (최신 → 과거) ---
        d = df.head(window_size).copy()  # window_size=30

        # 필요한 컬럼만 유지 (누락 체크)
        need_cols = [c for c in features if c in d.columns]
        missing = [c for c in features if c not in d.columns]
        if missing:
            raise RuntimeError(f"CSV에 필요한 컬럼 누락: {missing}")
        d = d[need_cols].copy()

        # 문자열 → 숫자 (쉼표/퍼센트 제거)
        for c in need_cols:
            d[c] = (
                d[c]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("%", "", regex=False)
            )
            d[c] = pd.to_numeric(d[c], errors="coerce")

        # 등락률이 퍼센트 값(예: 3.2)이면 소수로 보정
        if "등락률" in need_cols and d["등락률"].abs().max() > 1.5:
            d["등락률"] = d["등락률"] / 100.0

        # NaN 제거 및 길이 확인
        d = d.dropna()
        if len(d) < window_size:
            raise RuntimeError(
                f"데이터가 부족합니다. 필요: {window_size}, 현재: {len(d)}"
            )

        return d

    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ----------------------------
# 추론(원 코드 유지: async)
# ----------------------------
async def infer_with_ensemble_set(df_input: pd.DataFrame, set_idx: int) -> float:
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(df_input.values)
    sequence = scaled_data[-window_size:]
    sequence = sequence.reshape(1, window_size, len(features))
    input_tensor = torch.tensor(sequence, dtype=torch.float32).to(device)

    weights_dict = ensemble_weights[set_idx]
    threshold_dict = ensemble_thresholds[set_idx]

    num_total, num_anomalies = 0, 0
    for stock_name in weights_dict:
        threshold = threshold_dict.get(stock_name)
        if threshold is None:
            continue
        model = LSTMAutoEncoder(input_dim=len(features)).to(device)
        model.load_state_dict(weights_dict[stock_name])
        model.eval()
        with torch.no_grad():
            output = model(input_tensor)
            recon_error = torch.mean((input_tensor - output) ** 2).item()
        if recon_error > threshold:
            num_anomalies += 1
        num_total += 1
        del model
        torch.cuda.empty_cache()

    return num_anomalies / num_total if num_total > 0 else 0


# ----------------------------
# 공개 함수 (MCP에서 호출)
# ----------------------------
async def predict_anomaly_async(stock_name: str) -> dict:
    """
    원래 FastAPI 엔드포인트 로직을 함수로 제공(비동기).
    """
    load_models()
    t_start = time.time()
    df_input = await fetch_recent_data(stock_name)
    tasks = [infer_with_ensemble_set(df_input, i) for i in range(n_ensembles)]
    results = await asyncio.gather(*tasks)
    avg_anomaly_ratio = float(np.mean(results)) * 0.5
    elapsed = time.time() - t_start
    print(
        f"[predict_anomaly_async] anomaly_ratio={avg_anomaly_ratio:.4f} elapsed={elapsed:.3f}s"
    )
    return {"stock": stock_name, "anomaly_ratio": round(avg_anomaly_ratio, 4)}


def predict_anomaly(stock_name: str) -> dict:
    """
    동기 래퍼: 외부에서 쉽게 쓰도록 제공.
    - 이벤트 루프 없으면 asyncio.run 사용
    - 이미 루프가 있으면 임시 루프 생성하여 실행
    """
    try:
        loop = asyncio.get_running_loop()
        # 실행 중 루프가 있으면, 새 루프를 만들어 실행 (도중 충돌 방지)
        new_loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(new_loop)
            return new_loop.run_until_complete(predict_anomaly_async(stock_name))
        finally:
            new_loop.close()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        # 실행 중 루프 없음
        return asyncio.run(predict_anomaly_async(stock_name))


__all__ = [
    "predict_anomaly",  # 동기
    "predict_anomaly_async",  # 비동기
    "load_models",  # 필요 시 수동 호출
]
