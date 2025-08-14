# stock_info_service.py
import os
import time
import json
import glob
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager


# =============================================================================
# 다운로드 기본 경로 (환경변수 우선)
#   - STOCK_INFO_DOWNLOAD_DIR 이 설정되어 있으면 그 값을 사용
#   - 없으면 OS 별 기본값 사용 (서버/컨테이너 친화적)
# =============================================================================
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


# =============================================================================
# 크롬 옵션(headless + 다운로드 고정) 구성
#   - 요청별 전용 하위 폴더(prefix로 타임스탬프 붙임)
#   - 절대경로 필수
# =============================================================================
def _build_chrome_options(download_dir: str) -> Options:
    opts = webdriver.ChromeOptions()
    # 서버/CI 친화 옵션
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


# =============================================================================
# 캘린더 헬퍼 (원본 유지)
# =============================================================================
CAL_START_XPATH = "//div[contains(@class,'cal-box') and contains(@class,'start')]"
CAL_END_XPATH = "//div[contains(@class,'cal-box') and contains(@class,'end')]"


def get_calendar(wait: WebDriverWait, kind: str):
    """kind: 'start' or 'end'"""
    xp = CAL_START_XPATH if kind == "start" else CAL_END_XPATH
    return wait.until(EC.presence_of_element_located((By.XPATH, xp)))


def get_cur_year_month(driver, wait: WebDriverWait, kind: str):
    root = get_calendar(wait, kind)
    ysel = root.find_element(By.CSS_SELECTOR, ".cal-select-year")
    msel = root.find_element(By.CSS_SELECTOR, ".cal-select-month")
    # option:checked 대신 value 직접 읽기(리렌더링/스테일 회피)
    y = int(driver.execute_script("return arguments[0].value;", ysel))
    m = int(driver.execute_script("return arguments[0].value;", msel))
    return y, m


def click_cal_btn(driver, wait: WebDriverWait, kind: str, sel: str):
    root = get_calendar(wait, kind)
    btn = root.find_element(By.CSS_SELECTOR, sel)
    driver.execute_script("arguments[0].click();", btn)


def set_calendar_by_arrows(
    driver, wait: WebDriverWait, kind: str, year: int, month: int, day: int
):
    """달력 화살표만 사용해서 연/월/일 맞추기"""
    # 1) 연도
    for _ in range(40):
        cy, cm = get_cur_year_month(driver, wait, kind)
        if cy == year:
            break
        click_cal_btn(
            driver, wait, kind, ".cal-btn-nextY" if cy < year else ".cal-btn-prevY"
        )
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".cal-body")))
        time.sleep(0.1)

    # 2) 월
    for _ in range(24):
        cy, cm = get_cur_year_month(driver, wait, kind)
        if cm == month:
            break
        click_cal_btn(
            driver, wait, kind, ".cal-btn-nextM" if cm < month else ".cal-btn-prevM"
        )
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".cal-body")))
        time.sleep(0.1)

    # 3) 일 (현재 월 칸만: td:not(.other))
    root = get_calendar(wait, kind)
    dstr = str(int(day))  # '01' -> '1'
    try:
        link = root.find_element(
            By.CSS_SELECTOR,
            f".cal-body table td:not(.other) a[data-calendar-date='{dstr}']",
        )
        driver.execute_script("arguments[0].click();", link)
    except NoSuchElementException:
        cell = root.find_element(
            By.XPATH,
            f".//table/tbody//td[not(contains(@class,'other')) and normalize-space(text())='{dstr}']",
        )
        driver.execute_script("arguments[0].click();", cell)
    time.sleep(0.2)


# =============================================================================
# 다운로드 보조: 특정 폴더에 새 CSV가 내려올 때까지 기다리고 경로 반환
#   - .crdownload 파일이 사라질 때까지 대기
#   - timeout 초과 시 예외
# =============================================================================
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


# =============================================================================
# 숫자/퍼센트 파서 + 분석 함수 (원본 유지)
# =============================================================================
def _to_num(x):
    if pd.isna(x):
        return np.nan
    if isinstance(x, (int, float)):
        return x
    s = str(x).strip().replace(",", "")
    try:
        return float(s)
    except:
        return np.nan


def _to_pct(x):
    if pd.isna(x):
        return np.nan
    s = str(x).strip().replace("%", "").replace(",", "")
    try:
        return float(s)
    except:
        return np.nan


def analyze_individual_stock_df(df: pd.DataFrame) -> dict:
    # 필수 컬럼 체크
    for c in ["일자", "종가", "등락률", "거래량"]:
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

    avg_vol_5d = float(last5["거래량"].mean())
    avg_vol_all = float(d["거래량"].mean())
    avg_ret_5d = float(last5["등락률"].mean())
    avg_ret_all = float(d["등락률"].mean())

    vol_change_pct = (
        None
        if (np.isnan(avg_vol_all) or avg_vol_all == 0)
        else round((avg_vol_5d - avg_vol_all) / avg_vol_all * 100, 2)
    )
    ret_change_pp = (
        None
        if (np.isnan(avg_ret_5d) or np.isnan(avg_ret_all))
        else round(avg_ret_5d - avg_ret_all, 2)
    )

    last = d.iloc[-1]
    last_day_ret = float(last["등락률"])
    last_day_vol = float(last["거래량"])
    high_vol_last_day = (not np.isnan(last_day_vol)) and (
        avg_vol_5d and last_day_vol >= 1.5 * avg_vol_5d
    )

    up_days_5d = int((last5["등락률"] > 0).sum())
    down_days_5d = int((last5["등락률"] < 0).sum())

    # run-up: 처음 창 vs 최근 5일
    first5 = d.head(5) if len(d) >= 10 else d.head(max(1, len(d) // 2))
    runup_pct = None
    if first5["종가"].notna().any() and last5["종가"].notna().any():
        base = first5["종가"].mean()
        cur = last5["종가"].mean()
        if base and not np.isnan(base):
            runup_pct = round((cur / base - 1) * 100, 2)

    dump_signal = bool(
        high_vol_last_day and (not np.isnan(last_day_ret)) and last_day_ret <= -3.0
    )
    volume_spike = bool(avg_vol_all and avg_vol_5d >= 1.5 * avg_vol_all)
    momentum_jump = bool(ret_change_pp is not None and ret_change_pp >= 1.0)

    return {
        "기간요약": {
            "시작일": (
                str(d["일자"].iloc[0].date()) if pd.notna(d["일자"].iloc[0]) else None
            ),
            "종료일": (
                str(d["일자"].iloc[-1].date()) if pd.notna(d["일자"].iloc[-1]) else None
            ),
            "거래일수": int(len(d)),
        },
        "주요지표": {
            "최근5일_평균거래량": (
                int(round(avg_vol_5d)) if not np.isnan(avg_vol_5d) else None
            ),
            "전체기간_평균거래량": (
                int(round(avg_vol_all)) if not np.isnan(avg_vol_all) else None
            ),
            "거래량변화율_vs전체_((최근5일평균-전체평균)/전체평균)*100%": vol_change_pct,  # %
            "최근5일_평균등락률": (
                round(avg_ret_5d, 2) if not np.isnan(avg_ret_5d) else None
            ),
            "전체기간_평균등락률": (
                round(avg_ret_all, 2) if not np.isnan(avg_ret_all) else None
            ),
            "등락률변화_pp_vs전체_(최근5일평균-전체평균)_pp": ret_change_pp,  # percentage points
            "최근5일_상승일수": up_days_5d,
            "최근5일_하락일수": down_days_5d,
            "런업비율_vs초기구간_((최근5일평균종가-초기5일평균종가)/초기5일평균종가)*100%": runup_pct,  # %
            "최종거래일_등락률": (
                round(last_day_ret, 2) if not np.isnan(last_day_ret) else None
            ),
            "최종거래일_거래량": (
                int(last_day_vol) if not np.isnan(last_day_vol) else None
            ),
        },
        "신호": {
            "최근5일_거래량급증_vs전체_(최근5일평균>=1.5*전체평균)": volume_spike,
            "최근5일_모멘텀점프_vs전체_(등락률변화>=1.0pp)": momentum_jump,
            "최종거래일_덤핑신호": dump_signal,
        },
    }


# =============================================================================
# 메인 크롤링 + 분석 함수
#   - 기존 individual_stock_trend()를 서버/컨테이너 친화적으로 개선
#   - 요청별 다운로드 폴더를 만들어 충돌/오검출 방지
# =============================================================================
def individual_stock_trend(stock_name: str, target_date: str) -> dict:
    """
    [주식] -> [종목시세] -> [개별종목 시세 추이]
    종목 검색 → 첫 행 선택 → 달력 열기 → cal-start=2020-05-25 → cal-end=target_date → CSV 다운로드 → 분석
    """
    if not isinstance(stock_name, str) or not stock_name.strip():
        raise ValueError("stock_name은 비어있지 않은 문자열이어야 합니다.")
    if not (
        isinstance(target_date, str) and len(target_date) == 8 and target_date.isdigit()
    ):
        raise ValueError("target_date는 'YYYYMMDD' 형식의 문자열이어야 합니다.")

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
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.cal-btn-range1m"))
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

        # 18) 분석(JSON) 반환
        out = analyze_individual_stock_df(df)
        return out

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    # 로컬 테스트용
    result = individual_stock_trend("삼성전자", "20250810")
    print("\n=== 최종 반환 결과 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
