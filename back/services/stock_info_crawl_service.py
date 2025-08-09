import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException
import os
import pandas as pd
import numpy as np
import json


# 다운로드 폴더 경로 (크롬 기본값)
DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")

# ========= calendar helpers (함수 밖에 정의) =========
CAL_START_XPATH = "//div[contains(@class,'cal-box') and contains(@class,'start')]"
CAL_END_XPATH   = "//div[contains(@class,'cal-box') and contains(@class,'end')]"

def get_calendar(wait, kind: str):
    """kind: 'start' or 'end'"""
    xp = CAL_START_XPATH if kind == 'start' else CAL_END_XPATH
    return wait.until(EC.presence_of_element_located((By.XPATH, xp)))

def get_cur_year_month(driver, wait, kind: str):
    root = get_calendar(wait, kind)
    ysel = root.find_element(By.CSS_SELECTOR, ".cal-select-year")
    msel = root.find_element(By.CSS_SELECTOR, ".cal-select-month")
    # option:checked 대신 value 직접 읽기(리렌더링/스테일 회피)
    y = int(driver.execute_script("return arguments[0].value;", ysel))
    m = int(driver.execute_script("return arguments[0].value;", msel))
    return y, m

def click_cal_btn(driver, wait, kind: str, sel: str):
    root = get_calendar(wait, kind)
    btn = root.find_element(By.CSS_SELECTOR, sel)
    driver.execute_script("arguments[0].click();", btn)

def set_calendar_by_arrows(driver, wait, kind: str, year: int, month: int, day: int):
    """달력 화살표만 사용해서 연/월/일 맞추기"""
    # 1) 연도
    for _ in range(40):
        cy, cm = get_cur_year_month(driver, wait, kind)
        if cy == year:
            break
        click_cal_btn(driver, wait, kind, ".cal-btn-nextY" if cy < year else ".cal-btn-prevY")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".cal-body")))
        time.sleep(0.1)

    # 2) 월
    for _ in range(24):
        cy, cm = get_cur_year_month(driver, wait, kind)
        if cm == month:
            break
        click_cal_btn(driver, wait, kind, ".cal-btn-nextM" if cm < month else ".cal-btn-prevM")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".cal-body")))
        time.sleep(0.1)

    # 3) 일 (현재 월 칸만: td:not(.other))
    root = get_calendar(wait, kind)
    dstr = str(int(day))  # '01' -> '1'
    try:
        link = root.find_element(By.CSS_SELECTOR, f".cal-body table td:not(.other) a[data-calendar-date='{dstr}']")
        driver.execute_script("arguments[0].click();", link)
    except NoSuchElementException:
        cell = root.find_element(
            By.XPATH,
            f".//table/tbody//td[not(contains(@class,'other')) and normalize-space(text())='{dstr}']"
        )
        driver.execute_script("arguments[0].click();", cell)
    time.sleep(0.2)


# 최신 다운로드 파일 찾기
def get_latest_file(dir_path):
    files = [os.path.join(dir_path, f) for f in os.listdir(dir_path)]
    latest_file = max(files, key=os.path.getctime)
    return latest_file


# === df 분석 함수  ===
def _to_num(x):
    if pd.isna(x): return np.nan
    if isinstance(x, (int, float)): return x
    s = str(x).strip().replace(",", "")
    try: return float(s)
    except: return np.nan

def _to_pct(x):
    if pd.isna(x): return np.nan
    s = str(x).strip().replace("%","").replace(",", "")
    try: return float(s)
    except: return np.nan

def analyze_individual_stock_df(df: pd.DataFrame) -> dict:
    # 필수 컬럼 체크
    for c in ["일자","종가","등락률","거래량"]:
        if c not in df.columns:
            raise ValueError(f"필수 컬럼 누락: {c}")

    d = df.copy()
    d["일자"] = pd.to_datetime(d["일자"], errors="coerce")
    d["종가"] = d["종가"].apply(_to_num)
    d["거래량"] = d["거래량"].apply(_to_num)
    d["등락률"] = d["등락률"].apply(_to_pct)
    d = d.sort_values("일자").reset_index(drop=True)

    if len(d) < 5:
        raise ValueError("데이터가 5거래일 미만입니다.")

    last5 = d.tail(5)

    avg_vol_5d  = float(last5["거래량"].mean())
    avg_vol_all = float(d["거래량"].mean())
    avg_ret_5d  = float(last5["등락률"].mean())
    avg_ret_all = float(d["등락률"].mean())

    vol_change_pct = None if (np.isnan(avg_vol_all) or avg_vol_all == 0) else round((avg_vol_5d-avg_vol_all)/avg_vol_all*100, 2)
    ret_change_pp  = None if (np.isnan(avg_ret_5d) or np.isnan(avg_ret_all)) else round(avg_ret_5d-avg_ret_all, 2)

    last = d.iloc[-1]
    last_day_ret = float(last["등락률"])
    last_day_vol = float(last["거래량"])
    high_vol_last_day = (not np.isnan(last_day_vol)) and (avg_vol_5d and last_day_vol >= 1.5*avg_vol_5d)

    up_days_5d = int((last5["등락률"] > 0).sum())
    down_days_5d = int((last5["등락률"] < 0).sum())

    # run-up: 처음 창 vs 최근 5일
    first5 = d.head(5) if len(d) >= 10 else d.head(max(1, len(d)//2))
    runup_pct = None
    if first5["종가"].notna().any() and last5["종가"].notna().any():
        base = first5["종가"].mean()
        cur  = last5["종가"].mean()
        if base and not np.isnan(base):
            runup_pct = round((cur/base - 1)*100, 2)

    dump_signal   = bool(high_vol_last_day and (not np.isnan(last_day_ret)) and last_day_ret <= -3.0)
    volume_spike  = bool(avg_vol_all and avg_vol_5d >= 1.5*avg_vol_all)
    momentum_jump = bool(ret_change_pp is not None and ret_change_pp >= 1.0)

    return {
        "기간요약": {
            "시작일": str(d["일자"].iloc[0].date()) if pd.notna(d["일자"].iloc[0]) else None,
            "종료일": str(d["일자"].iloc[-1].date()) if pd.notna(d["일자"].iloc[-1]) else None,
            "거래일수": int(len(d))
        },
        "주요지표": {
            "최근5일_평균거래량": int(round(avg_vol_5d)) if not np.isnan(avg_vol_5d) else None,
            "전체기간_평균거래량": int(round(avg_vol_all)) if not np.isnan(avg_vol_all) else None,
            "거래량변화율_vs전체_((최근5일평균-전체평균)/전체평균)*100%": vol_change_pct,      # %
            "최근5일_평균등락률": round(avg_ret_5d, 2) if not np.isnan(avg_ret_5d) else None,
            "전체기간_평균등락률": round(avg_ret_all, 2) if not np.isnan(avg_ret_all) else None,
            "등락률변화_pp_vs전체_(최근5일평균-전체평균)_pp": ret_change_pp,        # percentage points
            "최근5일_상승일수": up_days_5d,
            "최근5일_하락일수": down_days_5d,
            "런업비율_vs초기구간_((최근5일평균종가-초기5일평균종가)/초기5일평균종가)*100%": runup_pct,       # %
            "최종거래일_등락률": round(last_day_ret, 2) if not np.isnan(last_day_ret) else None,
            "최종거래일_거래량": int(last_day_vol) if not np.isnan(last_day_vol) else None
        },
        "신호": {
            "최근5일_거래량급증_vs전체_(최근5일평균>=1.5*전체평균)": volume_spike,
            "최근5일_모멘텀점프_vs전체_(등락률변화>=1.0pp)": momentum_jump,
            "최종거래일_덤핑신호": dump_signal
        }
    }


# ========= main flow =========
def individual_stock_trend(stock_name: str, target_date: str):
    """
    [주식] -> [종목시세] -> [개별종목 시세 추이]
    종목 검색 → 첫 행 선택 → 달력 열기 → cal-start=2020-05-25 → cal-end=target_date
    """
    opts = Options()
    opts.add_argument("--start-maximized")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    wait = WebDriverWait(driver, 10)

    # 1) 페이지 진입
    driver.get("http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201")

    # 2) 주식 클릭
    wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "주식"))).click()

    # 3) 종목시세 클릭
    wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "종목시세"))).click()

    # 4) 개별종목 시세 추이 클릭
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[data-menu-id="MDC0201020103"]'))).click()

    # 5) 0.8초 대기
    time.sleep(0.8)

    # 6) 종목 검색 팝업 버튼 클릭
    wait.until(EC.element_to_be_clickable((By.ID, "btnisuCd_finder_stkisu0_0"))).click()

    # 7) 검색창에 종목명 입력
    search_input = wait.until(EC.presence_of_element_located((By.ID, "searchText__finder_stkisu0_0")))
    search_input.clear()
    search_input.send_keys(stock_name)
    time.sleep(2)

    # 8) 조회 버튼 클릭
    wait.until(EC.element_to_be_clickable((By.ID, "searchBtn__finder_stkisu0_0"))).click()
    time.sleep(2.5)

    # 9) 결과 테이블 첫 번째 행 클릭
    first_row = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#jsGrid__finder_stkisu0_0 tbody tr.jsRow')))
    first_row.click()

    # 10) 달력 열기 버튼 클릭
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.cal-btn-open'))).click()

    # 11) 달력 설정: cal-start 먼저 2020-05-25, 그다음 cal-end = target_date
    set_calendar_by_arrows(driver, wait, 'start', 2020, 5, 25)
    tgt_y = int(target_date[:4]); tgt_m = int(target_date[4:6]); tgt_d = int(target_date[6:8])
    set_calendar_by_arrows(driver, wait, 'end', tgt_y, tgt_m, tgt_d)


    # 12) 달력 확인 버튼 클릭
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.cal-btn-confirm.cal-btn-apply'))).click()


    # 13) "1개월" 버튼 클릭
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.cal-btn-range1m'))).click()

    # 14) 조회 버튼 클릭
    wait.until(EC.element_to_be_clickable((By.ID, 'jsSearchButton'))).click()
    time.sleep(0.5)

    # 15) 다운로드 버튼 클릭
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.CI-MDI-UNIT-DOWNLOAD'))).click()

    # 16) CSV 다운로드 클릭
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[data-type="csv"] a'))).click()
    
    # 17) 최신 CSV 파일 DataFrame으로 불러오기
    latest_csv = get_latest_file(DOWNLOAD_DIR)
    df = pd.read_csv(latest_csv, encoding="euc-kr")  # KRX CSV는 euc-kr 인코딩
    
    # === 18) 분석(JSON) ===
    out = analyze_individual_stock_df(df)

    return out


if __name__ == "__main__":
    result = individual_stock_trend("삼성전자", "20250810")
    print("\n=== 최종 반환 결과 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))

