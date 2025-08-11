from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
import torch
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import httpx
import time
import os
import os
import time
import glob
from datetime import datetime
from typing import Optional

import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 절대 경로로 디렉토리 정의
ensemble_weight_dir = os.path.join(BASE_DIR, "weights", "ensemble_weights")
ensemble_threshold_dir = os.path.join(BASE_DIR, "weights", "ensemble_thresholds")

app = FastAPI()


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


# 요청 형식
class InferenceRequest(BaseModel):
    stock_name: str


# 전역 변수 초기화
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
ensemble_weights = []
ensemble_thresholds = []


# 서버 시작 시 모델과 임계값 로딩
@app.on_event("startup")
def load_models():
    global ensemble_weights, ensemble_thresholds
    for i in range(1, n_ensembles + 1):
        weights_path = os.path.join(ensemble_weight_dir, f"ensemble_weights_set{i}.pt")
        thresh_path = os.path.join(
            ensemble_threshold_dir, f"ensemble_thresholds_set{i}.csv"
        )
        ensemble_weights.append(torch.load(weights_path, map_location=device))
        df_thresh = pd.read_csv(thresh_path)
        ensemble_thresholds.append(dict(zip(df_thresh["종목명"], df_thresh["임계값"])))


# ----------------------------------------
# Helpers
# ----------------------------------------
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
    # 서버/CI 친화 옵션
    # headless 꺼야 작동함
    # opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=ko-KR")
    opts.add_argument("--disable-gpu")

    # 다운로드 환경 설정
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
    """
    download_dir: 이번 요청 전용 하위 폴더
    start_ts: 다운로드 시작 시각 (time.time())
    """
    deadline = time.time() + timeout
    last_seen_csv: Optional[str] = None

    while time.time() < deadline:
        # .crdownload가 없는 최신 CSV 탐색 (요청 시작 이후 생성된 파일만)
        csv_candidates = []
        for path in glob.glob(os.path.join(download_dir, "*.csv")):
            try:
                if os.path.getmtime(path) >= start_ts:
                    csv_candidates.append(path)
            except FileNotFoundError:
                pass

        # 가장 최신 CSV
        if csv_candidates:
            latest = max(csv_candidates, key=os.path.getmtime)
            # .crdownload 동반 여부 체크 (크롬은 csv.crdownload 형태를 씀)
            cr_path = latest + ".crdownload"
            if not os.path.exists(cr_path):
                return latest
            last_seen_csv = latest

        time.sleep(0.5)

    raise TimeoutException(
        f"CSV 파일 다운로드 대기 시간 초과 (마지막 감지: {last_seen_csv or '없음'})"
    )


# 외부 API에서 최근 30일 데이터를 불러오기
# 우선 외부 API 대신 테스트 데이터 사용.
# 실제 데이터 사용시 일자 정렬 기준 보기!!!
async def fetch_recent_data(stock_name: str) -> pd.DataFrame:
    """
    [주식] -> [종목시세] -> [개별종목 시세 추이]
    종목 검색 → 첫 행 선택 → "1개월" 조회 → CSV 다운로드 → 분석
    """
    if not isinstance(stock_name, str) or not stock_name.strip():
        raise ValueError("stock_name은 비어있지 않은 문자열이어야 합니다.")

    # --- 다운로드 폴더: 요청별 전용 하위 폴더 사용
    base_dir = _resolve_base_download_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    req_dir = os.path.join(base_dir, f"req_{stamp}")
    os.makedirs(req_dir, exist_ok=True)

    # --- 크롬 옵션(headless + 다운로드 설정)
    options = _build_chrome_options(req_dir)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    wait = WebDriverWait(driver, 12)

    try:
        # 1) 페이지 진입
        driver.get(
            "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201"
        )

        # 2) 주식 클릭
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "주식"))).click()

        # 3) 종목시세 클릭
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "종목시세"))).click()

        # 4) 개별종목 시세 추이 클릭
        wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'a[data-menu-id="MDC0201020103"]')
            )
        ).click()

        # 5) 살짝 대기
        time.sleep(0.8)

        # 6) 종목 검색 팝업 버튼 클릭
        wait.until(
            EC.element_to_be_clickable((By.ID, "btnisuCd_finder_stkisu0_0"))
        ).click()

        # 7) 검색창에 종목명 입력
        search_input = wait.until(
            EC.presence_of_element_located((By.ID, "searchText__finder_stkisu0_0"))
        )
        search_input.clear()
        search_input.send_keys(stock_name)
        time.sleep(2.5)

        # 8) 조회 버튼 클릭
        wait.until(
            EC.element_to_be_clickable((By.ID, "searchBtn__finder_stkisu0_0"))
        ).click()
        time.sleep(2.5)

        # 9) 결과 테이블 첫 번째 행 클릭
        first_row = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "#jsGrid__finder_stkisu0_0 tbody tr.jsRow")
            )
        )
        first_row.click()

        # 10) "1개월" 버튼 클릭 (UI 요구에 따라 유지)
        wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.cal-btn-range1m"))
        ).click()

        # 11) 조회 버튼 클릭
        wait.until(EC.element_to_be_clickable((By.ID, "jsSearchButton"))).click()
        time.sleep(0.5)

        # 12) 다운로드 버튼 → CSV 선택
        wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.CI-MDI-UNIT-DOWNLOAD"))
        ).click()
        start_ts = time.time()
        wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[data-type="csv"] a'))
        ).click()

        # 13) CSV 파일 생성까지 대기 후 경로 획득
        latest_csv = _wait_download_csv(req_dir, start_ts=start_ts, timeout=90)

        # 14) CSV 로드 (KRX CSV는 euc-kr)
        df = pd.read_csv(latest_csv, encoding="euc-kr")

        return df

    finally:
        try:
            driver.quit()
        except Exception:
            pass


# 비동기 추론 함수 (각 세트별)
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


# 메인 API 엔드포인트
@app.post("/predict")
async def predict_anomaly(req: InferenceRequest):
    t_start = time.time()
    df_input = await fetch_recent_data(req.stock_name)
    tasks = [infer_with_ensemble_set(df_input, i) for i in range(n_ensembles)]
    results = await asyncio.gather(*tasks)
    avg_anomaly_ratio = float(np.mean(results))
    print(avg_anomaly_ratio)
    t_end = time.time()
    elapsed = t_end - t_start
    print(f"추론 시간: {elapsed:.3f}초")
    return {"stock": req.stock_name, "anomaly_ratio": round(avg_anomaly_ratio, 4)}
