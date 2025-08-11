# mcp/tools/lockup/lockup_service.py
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
#    (원본 그대로)
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

    # 컬럼 표준화
    df = df.rename(columns={c: c.strip() for c in df.columns})

    # 날짜 변환
    def to_date(s):
        try:
            return pd.to_datetime(s, format="%Y%m%d", errors="coerce").date()
        except Exception:
            try:
                return pd.to_datetime(s, errors="coerce").date()
            except Exception:
                return None

    if "등록(예탁)일" in df.columns:
        df["등록(예탁)일"] = df["등록(예탁)일"].apply(to_date)
    if "반환일" in df.columns:
        df["반환일"] = df["반환일"].apply(to_date)

    # 숫자 변환
    for col in ["등록(예탁)주식수", "반환주식수", "총발행주식수"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # NaN -> 0
    for col in ["등록(예탁)주식수", "반환주식수"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    # 총발행주식수 (최대값 사용)
    total_issued = 0
    if "총발행주식수" in df.columns and not df["총발행주식수"].isna().all():
        total_issued = int(
            pd.to_numeric(df["총발행주식수"], errors="coerce").fillna(0).max()
        )

    today = date.today()

    # 상태 판별
    def status_by_date(d):
        if d is None:
            return "진행중"
        return "해제완료" if d < today else "진행중"

    df["상태"] = df["반환일"].apply(status_by_date)

    # 집계
    ongoing_shares = (
        int(df.loc[df["상태"] == "진행중", "등록(예탁)주식수"].sum())
        if "등록(예탁)주식수" in df.columns
        else 0
    )
    released_shares = (
        int(df.loc[df["상태"] == "해제완료", "반환주식수"].sum())
        if "반환주식수" in df.columns
        else 0
    )

    def ratio(x):
        return round((x / total_issued) * 100, 2) if total_issued else 0.0

    ongoing_ratio = ratio(ongoing_shares)
    released_ratio = ratio(released_shares)

    # 잔여일
    def remain_days(d, st):
        if st != "진행중" or d is None:
            return None
        return (d - today).days

    df["잔여일"] = df.apply(
        lambda r: remain_days(r.get("반환일"), r.get("상태")), axis=1
    )

    # 전체 해제 완료일
    latest_release_date = None
    if "반환일" in df.columns and not df["반환일"].isna().all():
        dates = [d for d in df["반환일"].tolist() if isinstance(d, date)]
        latest_release_date = max(dates) if dates else None

    # 사유별 현황
    reason_summary = []
    if "의무보유사유" in df.columns:
        g = (
            df.groupby(["의무보유사유", "상태"], dropna=False)
            .agg({"등록(예탁)주식수": "sum", "반환주식수": "sum"})
            .reset_index()
        )

        for _, row in g.iterrows():
            state = str(row["상태"]) if row["상태"] is not None else ""
            if state == "진행중":
                shares = int(row["등록(예탁)주식수"] or 0)
            else:
                shares = int(row["반환주식수"] or 0)

            reason_summary.append(
                {
                    "의무보유사유": (
                        str(row["의무보유사유"])
                        if row["의무보유사유"] is not None
                        else ""
                    ),
                    "상태": state,
                    "주식수": shares,
                    "비율(%)": ratio(shares),
                }
            )

    # 직렬화
    def to_serializable(v):
        if isinstance(v, (pd.Timestamp, datetime, date)):
            return v.isoformat()
        if pd.isna(v):
            return None
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
        "전체해제완료일": (
            latest_release_date.isoformat() if latest_release_date else None
        ),
        "사유별현황": reason_summary,
        "개별내역": records,
    }
    return result


# ------------------------------
# 2) 크롤링: 종목명 -> DataFrame
#    (headless + 다운로드 경로 고정 버전)
# ------------------------------
def crawl_lockup_info(stock_name: str):
    """
    서버/컨테이너 환경에서도 안정적으로 동작하도록
    - headless 크롬
    - 고정 다운로드 경로(SEIBRO_DOWNLOAD_DIR 또는 OS별 기본)
    를 사용한다.
    """
    # ---- 다운로드 경로 결정
    download_dir = os.environ.get("SEIBRO_DOWNLOAD_DIR")
    if not download_dir:
        if os.name == "nt":
            # Windows
            base = os.environ.get("TEMP", r"C:\Temp")
            download_dir = os.path.join(base, "seibro_downloads")
        else:
            # Linux/macOS
            download_dir = "/tmp/seibro_downloads"
    os.makedirs(download_dir, exist_ok=True)

    # ---- 크롬 옵션
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")  # 서버/CI 환경 권장
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    prefs = {
        "download.default_directory": download_dir,  # 절대경로 필수
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "plugins.always_open_pdf_externally": True,
    }
    options.add_experimental_option("prefs", prefs)

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
        time.sleep(0.5)

        # Step 3: 검색 팝업 iframe 전환
        WebDriverWait(driver, 10).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "iframe1"))
        )
        time.sleep(0.5)

        # Step 4: 종목명 입력
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "search_string"))
        )
        search_input.clear()
        search_input.send_keys(stock_name)
        time.sleep(0.8)

        # Step 5: 팝업 내 '검색' 버튼 클릭
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "P_group100"))
        ).click()
        time.sleep(0.8)

        # Step 6: 검색 결과 첫 번째 항목 클릭
        first_result = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "P_isinList_0_P_ISIN_ROW"))
        )
        first_result.click()
        time.sleep(0.5)

        # Step 7: 메인 페이지로 복귀
        driver.switch_to.default_content()
        time.sleep(0.5)

        # Step 8: 조회기간 '3개월' 선택
        select_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "sd1_selectbox1_input_0"))
        )
        select = Select(select_elem)
        select.select_by_visible_text("3개월")
        time.sleep(0.5)

        # Step 9: '조회' 버튼 클릭
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "group64"))
        ).click()
        time.sleep(0.8)  # 데이터 로딩 대기

        # Step 10: 엑셀 다운로드 버튼 클릭
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "ExcelDownload_a"))
        ).click()

        # Step 11: 최신 다운로드 .xls 찾기 (고정 경로)
        latest_file = None
        deadline = time.time() + 30  # 최대 30초 대기
        while time.time() < deadline:
            xls_files = [
                os.path.join(download_dir, f)
                for f in os.listdir(download_dir)
                if f.lower().endswith(".xls") and not f.endswith(".crdownload")
            ]
            if xls_files:
                candidate = max(xls_files, key=os.path.getctime)
                # 크기 0 아닌지(다운로드 완료) 체크
                if os.path.getsize(candidate) > 0:
                    latest_file = candidate
                    break
            time.sleep(0.5)

        if not latest_file:
            raise FileNotFoundError(
                f"다운로드된 .xls 파일을 찾지 못했습니다. (dir={download_dir})"
            )

        # Step 12: HTML(.xls)로 읽어 DataFrame 변환
        try:
            dfs = pd.read_html(latest_file, encoding="euc-kr")
        except TypeError:
            # 일부 pandas 버전에선 encoding 인자를 받지 않음 → 바이너리로 열어 우회
            with open(latest_file, "rb") as f:
                dfs = pd.read_html(f)

        if not dfs:
            raise ValueError("다운로드 파일에서 표를 찾지 못했습니다.")

        df = dfs[0]
        df.columns = [str(c).strip() for c in df.columns]
        return df

    except Exception as e:
        print("[ERROR]", e)
        return None

    finally:
        driver.quit()


# ------------------------------
# 3) 단독 실행 테스트(선택)
# ------------------------------
if __name__ == "__main__":
    df = crawl_lockup_info("아이지넷")
    if df is None or df.empty:
        print("크롤링 또는 표 파싱 실패")
    else:
        result = lockup_info_to_json(df)
        print(json.dumps(result, ensure_ascii=False, indent=2))
