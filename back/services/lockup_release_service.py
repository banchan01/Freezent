from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import json
from datetime import datetime, date
import pandas as pd


# ------------------------------
# 1) 보호예수 분석: DataFrame -> JSON(dict)
# ------------------------------
def lockup_info_to_json(df: pd.DataFrame):
    """
    Seibro에서 내려받은 표(DataFrame)를 받아 보호예수 현황을 JSON(dict)로 반환.
    컬럼 가정:
      - 단축코드, 기업명, 주식종류, 발행형태, 시장구분
      - 등록(예탁)일, 등록(예탁)주식수
      - 반환일, 반환주식수
      - 의무보유사유, 총발행주식수
    규칙:
      - '등록(예탁)주식수'는 아직 반환 전(진행중)일 때 채워짐
      - '반환주식수'는 반환 완료일(반환일 < today)일 때 채워짐
      - 진행/해제 판정은 '반환일'과 오늘(today) 비교
    """

    # 컬럼 표준화(없을 수도 있는 공백/전각 공백 제거)
    df = df.rename(columns={c: c.strip() for c in df.columns})

    # 날짜 변환
    def to_date(s):
        # 20240101 형식 또는 datetime-like
        try:
            return pd.to_datetime(s, format="%Y%m%d", errors="coerce").date()
        except Exception:
            try:
                # 이미 날짜형일 수 있음
                return pd.to_datetime(s, errors="coerce").date()
            except Exception:
                return None

    if '등록(예탁)일' in df.columns:
        df['등록(예탁)일'] = df['등록(예탁)일'].apply(to_date)
    if '반환일' in df.columns:
        df['반환일'] = df['반환일'].apply(to_date)

    # 숫자 변환
    for col in ['등록(예탁)주식수', '반환주식수', '총발행주식수']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # NaN -> 0
    for col in ['등록(예탁)주식수', '반환주식수']:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    # 총발행주식수(행마다 같다고 가정, 없을 경우 0)
    total_issued = 0
    if '총발행주식수' in df.columns and not df['총발행주식수'].isna().all():
        # 가장 큰 값 사용(혹시 0/NaN 섞여 있을 때)
        total_issued = int(pd.to_numeric(df['총발행주식수'], errors='coerce').fillna(0).max())

    today = date.today()

    # 상태 판별: 반환일 < today → 해제완료 / 그 외 → 진행중
    def status_by_date(d):
        if d is None:
            return '진행중'  # 반환일이 없으면 진행중으로 간주
        return '해제완료' if d < today else '진행중'

    df['상태'] = df['반환일'].apply(status_by_date)

    # 진행/해제 주식수 집계 (규칙에 따라)
    # 진행중: 등록(예탁)주식수 합계
    ongoing_shares = int(df.loc[df['상태'] == '진행중', '등록(예탁)주식수'].sum()) if '등록(예탁)주식수' in df.columns else 0
    # 해제완료: 반환주식수 합계
    released_shares = int(df.loc[df['상태'] == '해제완료', '반환주식수'].sum()) if '반환주식수' in df.columns else 0

    # 비율
    def ratio(x):
        return round((x / total_issued) * 100, 2) if total_issued else 0.0

    ongoing_ratio = ratio(ongoing_shares)
    released_ratio = ratio(released_shares)

    # 잔여일 (진행중만)
    def remain_days(d, st):
        if st != '진행중' or d is None:
            return None
        return (d - today).days

    df['잔여일'] = df.apply(lambda r: remain_days(r.get('반환일'), r.get('상태')), axis=1)

    # 전체 해제 완료일(가장 늦은 반환일)
    latest_release_date = None
    if '반환일' in df.columns and not df['반환일'].isna().all():
        # 날짜들 중 가장 큰 것
        dates = [d for d in df['반환일'].tolist() if isinstance(d, date)]
        latest_release_date = max(dates) if dates else None

    # 사유별 현황 (상태별로 등록/반환 합계와 비율)
    reason_summary = []
    if '의무보유사유' in df.columns:
        g = df.groupby(['의무보유사유', '상태'], dropna=False).agg({
            '등록(예탁)주식수': 'sum',
            '반환주식수': 'sum'
        }).reset_index()

        for _, row in g.iterrows():
            state = str(row['상태']) if row['상태'] is not None else ''
            if state == '진행중':
                shares = int(row['등록(예탁)주식수'] or 0)
            else:
                shares = int(row['반환주식수'] or 0)

            reason_summary.append({
                "의무보유사유": str(row['의무보유사유']) if row['의무보유사유'] is not None else '',
                "상태": state,
                "주식수": shares,
                "비율(%)": ratio(shares)
            })

    # 개별내역(날짜/숫자 → 직렬화 가능한 타입으로)
    def to_serializable(v):
        if isinstance(v, (pd.Timestamp, datetime, date)):
            return v.isoformat()
        if pd.isna(v):
            return None
        # pandas/numpy 숫자형을 Python 기본형으로
        try:
            if float(v).is_integer():
                return int(v)
            return float(v)
        except Exception:
            return str(v)

    records = []
    for _, row in df.iterrows():
        rec = {}
        for col in df.columns:
            rec[col] = to_serializable(row[col])
        records.append(rec)

    result = {
        "총발행주식수": total_issued,
        "보호예수_진행중_주식수": ongoing_shares,
        "보호예수_진행중_비율(%)": ongoing_ratio,
        "반환_주식수": released_shares,
        "반환_주식수_비율(%)": released_ratio,
        "전체해제완료일": latest_release_date.isoformat() if latest_release_date else None,
        "사유별현황": reason_summary,
        "개별내역": records
    }
    return result


# ------------------------------
# 2) 크롤링: 종목명 -> DataFrame
# ------------------------------
def crawl_lockup_info(stock_name: str):
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)

    try:
        # Step 1: 페이지 접속
        url = "https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/company/BIP_CNTS01045V.xml&menuNo=50#"
        driver.get(url)
        time.sleep(1.5)

        # Step 2: '검색하기' 버튼 클릭
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "comN_group4"))
        ).click()
        print("[INFO] 검색 버튼 클릭 완료")
        time.sleep(0.5)

        # Step 3: 검색 팝업 iframe 전환
        WebDriverWait(driver, 10).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "iframe1"))
        )
        print("[INFO] iframe 전환 완료")
        time.sleep(0.5)

        # Step 4: 종목명 입력
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "search_string"))
        )
        search_input.clear()
        search_input.send_keys(stock_name)
        print(f"[INFO] 종목명 입력 완료: {stock_name}")
        time.sleep(0.8)

        # Step 5: 팝업 내 '검색' 버튼 클릭
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "P_group100"))
        ).click()
        print("[INFO] 팝업 내 검색 버튼 클릭 완료")
        time.sleep(0.8)

        # Step 6: 검색 결과 첫 번째 항목 클릭
        first_result = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "P_isinList_0_P_ISIN_ROW"))
        )
        first_result.click()
        print("[INFO] 첫 번째 검색 결과 클릭 완료")
        time.sleep(0.5)

        # Step 7: 메인 페이지로 복귀
        driver.switch_to.default_content()
        print("[INFO] 메인 페이지로 복귀 완료")
        time.sleep(0.5)

        # Step 8: 조회기간 '3개월' 선택
        select_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "sd1_selectbox1_input_0"))
        )
        select = Select(select_elem)
        select.select_by_visible_text("3개월")
        print("[INFO] 조회기간 '3개월' 선택 완료")
        time.sleep(0.5)

        # Step 9: '조회' 버튼 클릭
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "group64"))
        ).click()
        print("[INFO] 조회 버튼 클릭 완료")
        time.sleep(0.5)  # 데이터 로딩 대기

        # Step 10: 엑셀 다운로드 버튼 클릭
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "ExcelDownload_a"))
        ).click()
        print("[INFO] 엑셀 다운로드 버튼 클릭 완료")

        # Step 11: 최신 다운로드 .xls 찾기 (기본 Downloads)
        download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        # 다운로드 완료 대기 (최대 20초)
        latest_file = None
        deadline = time.time() + 20
        while time.time() < deadline:
            xls_files = [os.path.join(download_dir, f) for f in os.listdir(download_dir) if f.lower().endswith(".xls")]
            if xls_files:
                latest_file = max(xls_files, key=os.path.getctime)
                # 크기 0이 아닌지(다운로드 완료) 체크
                if os.path.getsize(latest_file) > 0:
                    break
            time.sleep(0.5)

        if not latest_file:
            raise FileNotFoundError("다운로드된 .xls 파일을 찾지 못했습니다.")

        print(f"[INFO] 최신 다운로드 파일: {latest_file}")

        # Step 12: HTML(.xls)로 읽어 DataFrame 변환 (인코딩: euc-kr)
        dfs = pd.read_html(latest_file, encoding="euc-kr")
        df = dfs[0]
        print("[INFO] 데이터프레임 변환 완료")
        # 컬럼명 깨끗이(공백 제거)
        df.columns = [str(c).strip() for c in df.columns]
        return df

    except Exception as e:
        print("[ERROR]", e)
        return None

    finally:
        driver.quit()


# ------------------------------
# 3) 실행 예시: 크롤링 -> JSON 출력
# ------------------------------
if __name__ == "__main__":
    df = crawl_lockup_info("아이지넷")
    if df is None or df.empty:
        print("크롤링 또는 표 파싱 실패")
    else:
        result = lockup_info_to_json(df)
        print(json.dumps(result, ensure_ascii=False, indent=2))
