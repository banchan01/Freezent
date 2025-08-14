from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import time
import os
from typing import Optional, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ensemble_weight_dir = os.path.join(BASE_DIR, "weights", "ensemble_weights")
ensemble_threshold_dir = os.path.join(BASE_DIR, "weights", "ensemble_thresholds")

app = FastAPI()

# ====== 모델 정의 ======
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

# ====== 요청 형식 ======
class InferenceRequest(BaseModel):
    stock_name: str

# ====== 전역 설정 ======
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

# 전역 캐시
ALL_WEIGHTS = {}       # stock_name -> state_dict
ALL_THRESHOLDS = {}    # stock_name -> threshold(float)

# ====== 서버 시작 시 모든 가중치/임계값 로딩 ======
@app.on_event("startup")
def load_all_models():
    global ALL_WEIGHTS, ALL_THRESHOLDS
    ALL_WEIGHTS.clear()
    ALL_THRESHOLDS.clear()

    for i in range(1, n_ensembles + 1):
        weights_path = os.path.join(ensemble_weight_dir, f"ensemble_weights_set{i}.pt")
        thresh_path = os.path.join(ensemble_threshold_dir, f"ensemble_thresholds_set{i}.csv")

        weights_dict = torch.load(weights_path, map_location="cpu")
        df_thresh = pd.read_csv(thresh_path)

        threshold_map = dict(zip(df_thresh["종목명"], df_thresh["임계값"]))
        for stock_name, state_dict in weights_dict.items():
            ALL_WEIGHTS[stock_name] = state_dict
            if stock_name in threshold_map:
                ALL_THRESHOLDS[stock_name] = float(threshold_map[stock_name])

    print(f"[Startup] Loaded {len(ALL_WEIGHTS)} models, {len(ALL_THRESHOLDS)} thresholds.")

# ====== 크롬 옵션 ======
def _build_chrome_options(download_dir: str) -> Options:
    opts = webdriver.ChromeOptions()
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
    while time.time() < deadline:
        csv_candidates = [
            path for path in os.listdir(download_dir)
            if path.endswith(".csv")
        ]
        if csv_candidates:
            latest = max(
                [os.path.join(download_dir, f) for f in csv_candidates],
                key=os.path.getmtime
            )
            cr_path = latest + ".crdownload"
            if not os.path.exists(cr_path):
                return latest
        time.sleep(0.5)
    raise TimeoutException("CSV 다운로드 대기 시간 초과")

# ====== 데이터 수집 ======
async def fetch_recent_data(stock_name: str) -> pd.DataFrame:
    base_dir = "/tmp/stock_info_downloads"
    os.makedirs(base_dir, exist_ok=True)
    req_dir = os.path.join(base_dir, f"req_{int(time.time())}")
    os.makedirs(req_dir, exist_ok=True)

    options = _build_chrome_options(req_dir)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 12)

    try:
        driver.get("http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201")
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "주식"))).click()
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "종목시세"))).click()
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[data-menu-id="MDC0201020103"]'))).click()
        time.sleep(0.8)
        wait.until(EC.element_to_be_clickable((By.ID, "btnisuCd_finder_stkisu0_0"))).click()

        search_input = wait.until(EC.presence_of_element_located((By.ID, "searchText__finder_stkisu0_0")))
        search_input.clear()
        search_input.send_keys(stock_name)
        time.sleep(2.5)
        wait.until(EC.element_to_be_clickable((By.ID, "searchBtn__finder_stkisu0_0"))).click()
        time.sleep(2.5)
        first_row = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#jsGrid__finder_stkisu0_0 tbody tr.jsRow")))
        first_row.click()
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.cal-btn-range1m"))).click()
        wait.until(EC.element_to_be_clickable((By.ID, "jsSearchButton"))).click()
        time.sleep(0.5)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.CI-MDI-UNIT-DOWNLOAD"))).click()
        start_ts = time.time()
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[data-type="csv"] a'))).click()

        latest_csv = _wait_download_csv(req_dir, start_ts=start_ts, timeout=90)
        df = pd.read_csv(latest_csv, encoding="euc-kr")
        print(df.tail(5))
        
        return df
    finally:
        driver.quit()

# ====== 슬라이딩 윈도우 생성 ======
def create_windows(data_2d: np.ndarray, window_size: int) -> np.ndarray:
    return np.array([data_2d[i:i+window_size] for i in range(len(data_2d)-window_size)])

# ====== 추론 ======
def run_last_window_inference(df_input: pd.DataFrame) -> float:
    # 1. 피처 강제 선택
    for col in features:
        if col not in df_input.columns:
            raise HTTPException(status_code=400, detail=f"컬럼 누락: {col}")
    df_input = df_input[features].copy()
    df_input = df_input.dropna()
    if len(df_input) < window_size:
        raise HTTPException(status_code=400, detail="데이터 길이가 30일 미만입니다.")

    # 2. 전체 1년치로 fit → transform
    scaler = MinMaxScaler()
    scaled_all = scaler.fit_transform(df_input.values)

    # 3. 최신 30일만 추출
    last_30_scaled = scaled_all[-window_size:]
    sequence = last_30_scaled.reshape(1, window_size, len(features))
    x_tensor = torch.tensor(sequence, dtype=torch.float32, device=device)

    # 4. 모든 모델에 대해 단일 윈도우 추론
    num_total, num_anomalies = 0, 0
    model = LSTMAutoEncoder(input_dim=len(features)).to(device)
    model.eval()
    with torch.no_grad():
        for stock_name, state_dict in ALL_WEIGHTS.items():
            threshold = ALL_THRESHOLDS.get(stock_name, None)
            if threshold is None:
                continue
            model.load_state_dict(state_dict)
            output = model(x_tensor)
            recon_error = torch.mean((x_tensor - output) ** 2).item()
            if recon_error > threshold:
                num_anomalies += 1
            num_total += 1

    return num_anomalies / num_total if num_total > 0 else 0.0
# ====== API 엔드포인트 ======
@app.post("/predict")
async def predict_anomaly(req: InferenceRequest):
    t_start = time.time()
    df_input = await fetch_recent_data(req.stock_name)
    ratio = run_last_window_inference(df_input)
    elapsed = time.time() - t_start
    return {
        "stock": req.stock_name,
        "anomaly_ratio": round(ratio, 4),
        "elapsed_sec": round(elapsed, 3)
    }
