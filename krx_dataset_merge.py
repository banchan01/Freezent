import pandas as pd
import glob
import os
from tqdm import tqdm

DATA_DIR = os.path.abspath("C:/Users/kimmc/Desktop/project/kb_ai/dataset")
OUTPUT_PARQUET = os.path.abspath(
    "C:/Users/kimmc/Desktop/project/kb_ai/all_kospi_data.parquet"
)

# 통합할 모든 행 저장할 리스트
all_rows = []

# dataset/의 각 월별 폴더 순회
for yyyymm in sorted(os.listdir(DATA_DIR)):
    subdir = os.path.join(DATA_DIR, yyyymm)
    if not os.path.isdir(subdir):
        continue

    csv_files = sorted(glob.glob(os.path.join(subdir, "kospi_*.csv")))

    for file in tqdm(csv_files, desc=f"{yyyymm} 처리 중"):
        try:
            df = pd.read_csv(file, encoding="euc-kr")
            date_str = os.path.basename(file).replace("kospi_", "").replace(".csv", "")
            df.insert(0, "날짜", pd.to_datetime(date_str, format="%Y%m%d"))
            all_rows.append(df)
        except Exception as e:
            print(f"[ERROR] {file}: {e}")

print("\n[INFO] 전체 데이터 연결 중...")
full_df = pd.concat(all_rows, ignore_index=True)


print("[INFO] Parquet 파일로 저장 중...")
full_df.to_parquet(OUTPUT_PARQUET)
print(f"[완료] Parquet 저장 완료: {OUTPUT_PARQUET}")
