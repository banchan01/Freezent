import pandas as pd
import os

# [1] 파일 경로
PARQUET_PATH = "C:/Users/kimmc/Desktop/project/FREEZENT/all_kospi_data.parquet"
EVENT_CSV_PATH = "C:/Users/kimmc/Desktop/project/FREEZENT/event_detected.csv"
OUTPUT_CSV_PATH = "C:/Users/kimmc/Desktop/project/FREEZENT/filtered_kospi_data.csv"

# [2] 파일 확인 및 로딩
if not os.path.exists(PARQUET_PATH) or not os.path.exists(EVENT_CSV_PATH):
    print("[❌] 파일이 존재하지 않습니다.")
    exit()

df = pd.read_parquet(PARQUET_PATH)
event_df = pd.read_csv(EVENT_CSV_PATH)

df["날짜"] = pd.to_datetime(df["날짜"])
event_df["날짜"] = pd.to_datetime(event_df["날짜"])


# [3] 종목명 정규화 함수
def clean_name(name):
    return str(name).strip().replace("\u3000", "").replace("\xa0", "")


df["종목명"] = df["종목명"].apply(clean_name)
event_df["종목명"] = event_df["종목명"].apply(clean_name)

# [4] 30개 종목 리스트 정규화
selected_stocks = [
    "쌍용양회(3우B)",
    "신성건설",
    "우성넥스티어",
    "지엔비씨더스",
    "코오롱(1우)",
    "코오롱글로벌우",
    "코오롱유화",
    "하나니켈2호",
    "하나증권(1우)",
    "한국수출포장",
    "한화타임월드",
    "현대오토넷",
    "화풍집단 KDR",
    "C&중공업",
    "CJ(1우B)",
    # "DKME",
    "KB손해보험",
    "SNT중공업",
    "광희리츠",
    "넥센타이어1우B",
    "대덕GDS우",
    "대한방직",
    "동부하이텍",
    "동양기전",
    "디피아이홀딩스우",
    "메리츠종금",
    "보락",
    "서광건설",
    "세원정공",
]
selected_stocks = [clean_name(s) for s in selected_stocks]

# [5] 이벤트 맵 생성
event_map = event_df.groupby("종목명")["날짜"].apply(list).to_dict()

# [6] 처리
result_list = []

print("\n[📊 종목별 처리 결과]")
print("-" * 60)

for stock in selected_stocks:
    stock_df = df[df["종목명"] == stock].copy()
    stock_df.sort_values("날짜", inplace=True)

    if stock not in event_map:
        print(
            f"[{stock}] 이벤트 없음 → 전체 유지 ({stock_df['날짜'].min().date()} ~ {stock_df['날짜'].max().date()}) / {len(stock_df)}일"
        )
        result_list.append(stock_df)
        continue

    # 이벤트가 있는 종목 → 여러 이벤트 중 손실 가장 적은 쪽 선택
    best_df = None
    best_len = -1
    best_event_date = None

    for event_date in event_map[stock]:
        window_start = event_date - pd.Timedelta(days=5)
        window_end = event_date + pd.Timedelta(days=5)

        before_df = stock_df[stock_df["날짜"] < window_start]
        after_df = stock_df[stock_df["날짜"] > window_end]

        print(f"  🔍 [{stock}] 이벤트 날짜: {event_date.date()}")
        print(f"     ➤ 제거 구간: {window_start.date()} ~ {window_end.date()}")
        print(f"     ➤ before: {len(before_df)}일")
        print(f"     ➤ after : {len(after_df)}일")

        if len(before_df) >= len(after_df):
            candidate_df = before_df
            chosen = "before"
        else:
            candidate_df = after_df
            chosen = "after"

        print(f"     ➤ 선택된 구간: {chosen} ({len(candidate_df)}일)")

        if len(candidate_df) > best_len:
            best_df = candidate_df
            best_len = len(candidate_df)
            best_event_date = event_date

    result_list.append(best_df)
    print(
        f"✅ [{stock}] 최종 선택 날짜: {best_event_date.date()} → {best_df['날짜'].min().date()} ~ {best_df['날짜'].max().date()} / {len(best_df)}일"
    )

# [7] 저장
final_df = (
    pd.concat(result_list).sort_values(by=["종목코드", "날짜"]).reset_index(drop=True)
)
final_df.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8-sig")

print("\n[✅] 최종 결과 저장 완료:", OUTPUT_CSV_PATH)
