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
features = ['종가', '대비', '등락률', '시가', '고가', '저가', '거래량', '거래대금', '시가총액', '상장주식수']
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
        thresh_path = os.path.join(ensemble_threshold_dir, f"ensemble_thresholds_set{i}.csv")
        ensemble_weights.append(torch.load(weights_path, map_location=device))
        df_thresh = pd.read_csv(thresh_path)
        ensemble_thresholds.append(dict(zip(df_thresh['종목명'], df_thresh['임계값'])))

# 외부 API에서 최근 30일 데이터를 불러오기
# 우선 외부 API 대신 테스트 데이터 사용.
# 실제 데이터 사용시 일자 정렬 기준 보기!!!
async def fetch_recent_data(stock_name: str) -> pd.DataFrame:
    # url = f"https://your-api-provider.com/stock?name={stock_name}"
    # async with httpx.AsyncClient() as client:
    #     response = await client.get(url)
    # if response.status_code != 200:
    #     raise HTTPException(status_code=404, detail="Stock data not found")
    
    # data = response.json()
    # df = pd.DataFrame(data)
    # df = df[features]
    # if len(df) < window_size:
    #     raise HTTPException(status_code=400, detail="Insufficient data (need ≥30 days)")
    data_path = os.path.join(BASE_DIR, "data", "anomaly_data.csv")
    df_input = pd.read_csv(data_path, encoding='cp949')
    df_input = df_input[features]

    return df_input[::-1]

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
    return {
        "stock": req.stock_name,
        "anomaly_ratio": round(avg_anomaly_ratio, 4)
    }
