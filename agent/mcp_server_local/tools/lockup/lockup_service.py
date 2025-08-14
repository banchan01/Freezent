# mcp/tools/lockup/lockup_service.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
import time
import os
from datetime import datetime, date
import pandas as pd


# ------------------------------
# 1) 보호예수 분석: DataFrame -> JSON(dict)
# ------------------------------
def lockup_info_to_json(df: pd.DataFrame):
    df = df.rename(columns={c: c.strip() for c in df.columns})

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

    for col in ["등록(예탁)주식수", "반환주식수", "총발행주식수"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["등록(예탁)주식수", "반환주식수"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    total_issued = 0
    if "총발행주식수" in df.columns and not df["총발행주식수"].isna().all():
        total_issued = int(pd.to_numeric(df["총발행주식수"], errors="coerce").fillna(0).max())

    today = date.today()

    def status_by_date(d):
        if d is None:
            return "진행중"
        return "해제완료" if d < today else "진행중"

    if "반환일" in df.columns:
        df["상태"] = df["반환일"].apply(status_by_date)
    else:
        df["상태"] = "진행중"

    ongoing_shares = int(df.loc[df["상태"] == "진행중", "등록(예탁)주식수"].sum()) if "등록(예탁)주식수" in df.columns else 0
    released_shares = int(df.loc[df["상태"] == "해제완료", "반환주식수"].sum()) if "반환주식수" in df.columns else 0

    def ratio(x):
        return round((x / total_issued) * 100, 2) if total_issued else 0.0

    ongoing_ratio = ratio(ongoing_shares)
    released_ratio = ratio(released_shares)

    def remain_days(d, st):
        if st != "진행중" or d is None:
            return None
        return (d - today).days

    if "반환일" in df.columns:
        df["잔여일"] = df.apply(lambda r: remain_days(r.get("반환일"), r.get("상태")), axis=1)
    else:
        df["잔여일"] = None

    latest_release_date = None
    if "반환일" in df.columns and not df["반환일"].isna().all():
        dates = [d for d in df["반환일"].tolist() if isinstance(d, date)]
        latest_release_date = max(dates) if dates else None

    reason_summary = []
    if "의무보유사유" in df.columns:
        g = (
            df.groupby(["의무보유사유", "상태"], dropna=False)
            .agg({"등록(예탁)주식수": "sum", "반환주식수": "sum"})
            .reset_index()
        )
        for _, row in g.iterrows():
            state = str(row["상태"]) if row["상태"] is not None else ""
            shares = int(row["등록(예탁)주식수"] or 0) if state == "진행중" else int(row["반환주식수"] or 0)
            reason_summary.append(
                {
                    "의무보유사유": (str(row["의무보유사유"]) if row["의무보유사유"] is not None else ""),
                    "상태": state,
                    "주식수": shares,
                    "비율(%)": ratio(shares),
                }
            )

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
        records.append({col: to_serializable(row[col]) for col in df.columns})

    return {
        "총발행주식수": total_issued,
        "보호예수_진행중_주식수": ongoing_shares,
        "보호예수_진행중_비율(%)": ongoing_ratio,
        "반환_주식수": released_shares,
        "반환_주식수_비율(%)": released_ratio,
        "전체해제완료일": (latest_release_date.isoformat() if latest_release_date else None),
        "사유별현황": reason_summary,
        "개별내역": records,
    }


# ------------------------------
# 2) 크롤링: 종목명 -> DataFrame (안정화/재시도)
# ------------------------------
def crawl_lockup_info(stock_name: str) -> pd.DataFrame | None:
    """
    Headless Chrome로 Seibro 보호예수 정보를 크롤링해 DataFrame 반환.
    - 실패 시 None, 데이터 없음이면 빈 DataFrame
    """
    download_dir = os.environ.get("SEIBRO_DOWNLOAD_DIR") or ("/tmp/seibro_downloads" if os.name != "nt" else os.path.join(os.environ.get("TEMP", r"C:\Temp"), "seibro_downloads"))
    os.makedirs(download_dir, exist_ok=True)

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "plugins.always_open_pdf_externally": True,
    })

    driver = webdriver.Chrome(options=options)
    try:
        url = "https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/company/BIP_CNTS01045V.xml&menuNo=50#"
        driver.get(url)

        wait = WebDriverWait(driver, 15)

        # 검색하기 버튼
        wait.until(EC.element_to_be_clickable((By.ID, "comN_group4"))).click()

        # 팝업 iframe 전환
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "iframe1")))

        # 종목명 입력 + 검색
        search_input = wait.until(EC.presence_of_element_located((By.ID, "search_string")))
        search_input.clear()
        search_input.send_keys(stock_name)
        wait.until(EC.element_to_be_clickable((By.ID, "P_group100"))).click()

        # 첫 번째 결과 클릭 (stale 대비 재시도)
        for _ in range(3):
            try:
                first = wait.until(EC.element_to_be_clickable((By.ID, "P_isinList_0_P_ISIN_ROW")))
                first.click()
                break
            except (StaleElementReferenceException, TimeoutException):
                time.sleep(0.5)
        else:
            return None  # 결과 클릭 실패

        # 메인으로 복귀
        driver.switch_to.default_content()

        # 조회기간 3개월
        select_elem = wait.until(EC.presence_of_element_located((By.ID, "sd1_selectbox1_input_0")))
        Select(select_elem).select_by_visible_text("3개월")

        # 조회 버튼
        wait.until(EC.element_to_be_clickable((By.ID, "group64"))).click()

        # 데이터 로딩 대기
        time.sleep(1.2)

        # "조회된 데이터가 없습니다" 체크
        try:
            no_data_xpath = "//*[@id='grid1_body_tbody']/tr/td[contains(text(), '조회된 데이터가 없습니다.')]"
            if driver.find_element(By.XPATH, no_data_xpath).is_displayed():
                return pd.DataFrame()
        except NoSuchElementException:
            pass

        # 엑셀 다운로드
        wait.until(EC.element_to_be_clickable((By.ID, "ExcelDownload_a"))).click()

        # 최신 .xls 대기
        latest_file = None
        deadline = time.time() + 30
        while time.time() < deadline:
            xls_files = [
                os.path.join(download_dir, f)
                for f in os.listdir(download_dir)
                if f.lower().endswith(".xls") and not f.endswith(".crdownload")
            ]
            if xls_files:
                candidate = max(xls_files, key=os.path.getctime)
                if os.path.getsize(candidate) > 0:
                    latest_file = candidate
                    break
            time.sleep(0.5)

        if not latest_file:
            return None

        # .xls → DataFrame
        try:
            dfs = pd.read_html(latest_file, encoding="euc-kr")
        except TypeError:
            with open(latest_file, "rb") as f:
                dfs = pd.read_html(f)
        if not dfs:
            return None

        df = dfs[0]
        df.columns = [str(c).strip() for c in df.columns]
        return df

    except Exception:
        return None
    finally:
        driver.quit()
