from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time
import os
import glob
from bs4 import BeautifulSoup

# 설정
CHROMEDRIVER_PATH = (
    "C:/Users/kimmc/Desktop/project/kb_ai/chromedriver-win64/chromedriver.exe"
)
DOWNLOAD_PATH = os.path.abspath("C:/Users/kimmc/Desktop/project/kb_ai/dataset")

# MIN_DATE ~ 오늘날짜 까지
MIN_DATE = datetime.strptime("20050101", "%Y%m%d")

# 크롬 옵션
options = webdriver.ChromeOptions()
options.add_experimental_option(
    "prefs",
    {
        "download.default_directory": DOWNLOAD_PATH,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    },
)
options.add_argument("--start-maximized")

# 드라이버 실행
driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
wait = WebDriverWait(driver, 10)

# 사이트 열기
driver.get("http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201")

# 메뉴 클릭
wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "주식"))).click()
time.sleep(0.3)
wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "종목시세"))).click()
time.sleep(0.3)
wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "전종목 시세"))).click()
time.sleep(0.3)

# KOSPI 선택
wait.until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, 'label[for="mktId_0_1"]'))
).click()
time.sleep(0.3)


def move_to_target_month_year(target_year: int, target_month: int):
    for _ in range(1000):
        try:
            # 현재 달력에서 선택된 연도와 월을 파싱
            soup = BeautifulSoup(driver.page_source, "html.parser")
            current_year = int(
                soup.select_one("select.cal-select-year option[selected]").get("value")
            )
            current_month = int(
                soup.select_one("select.cal-select-month option[selected]").get("value")
            )

            # 목표 연도와 월에 도달하면 종료
            if current_year == target_year and current_month == target_month:
                print(f"[INFO] 목표 연/월 도달: {current_year}년 {current_month}월")
                break

            # 현재가 목표보다 미래이면 이전 달로 이동
            wait.until(
                EC.element_to_be_clickable((By.CLASS_NAME, "cal-btn-prevM"))
            ).click()
            time.sleep(0.2)

        except Exception as e:
            print(f"[ERROR] 달력 이동 중 오류: {e}")
            break


# 달력 열기
wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "cal-btn-open"))).click()
time.sleep(0.3)
move_to_target_month_year(2007, 7)


# 현재 달력에서 선택 가능한 날짜들을 역순으로 가져옴


def get_valid_days():
    soup = BeautifulSoup(driver.page_source, "html.parser")
    calendar = soup.select_one("table.cal-monthly-table tbody")
    if not calendar:
        return []
    valid = []
    for a in reversed(calendar.select("a[data-calendar-date]")):
        td = a.find_parent("td")
        if "other" in td.get("class", []):
            continue
        if "sun" in td.get("class", []) or "sat" in td.get("class", []):
            continue
        valid.append(a["data-calendar-date"].zfill(2))
    return valid


# 현재 달력의 년도 / 달 가져옴
def get_current_year_month():
    soup = BeautifulSoup(driver.page_source, "html.parser")
    year = soup.select_one("select.cal-select-year option[selected]").get("value")
    month = (
        soup.select_one("select.cal-select-month option[selected]")
        .get("value")
        .zfill(2)
    )
    return year, month


# 연/월 폴더에 맞게 저장 & 이름 변경
def wait_and_rename_downloaded_file(filename, timeout=15):
    print(f"[WAIT] '{filename}'로 이름 변경 대기 중...")

    # 연월 폴더 만들기
    yyyymm = filename.replace("kospi_", "")[:6]
    subdir = os.path.join(DOWNLOAD_PATH, yyyymm)
    os.makedirs(subdir, exist_ok=True)

    start = time.time()
    while time.time() - start < timeout:
        files = glob.glob(os.path.join(DOWNLOAD_PATH, "*.csv"))
        files = [
            f
            for f in files
            if not f.endswith(".crdownload")
            and not os.path.basename(f).startswith("kospi_")
        ]
        if len(files) == 1:
            try:
                dst_path = os.path.join(subdir, filename)
                os.rename(files[0], dst_path)
                print(f"[RENAME] {dst_path}")
                return True
            except Exception as e:
                print(f"[ERROR] 이름 변경 실패: {e}")
                return False
        time.sleep(0.3)

    print("[ERROR] 새 파일을 찾지 못함 (timeout)")
    return False


# 해당 날짜 csv파일 다운
def process_date(day_str):
    try:
        # 현재 연/월 가져오기
        year, month = get_current_year_month()
        yyyymmdd = f"{year}{month}{day_str}"

        # 최소 날짜 확인
        if datetime.strptime(yyyymmdd, "%Y%m%d") < MIN_DATE:
            print(f"[DONE] {yyyymmdd}은 최소 날짜 이전 → 종료")
            driver.quit()
            exit()

        # 날짜 클릭
        wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, f'//a[@data-calendar-date="{int(day_str)}"]')
            )
        ).click()
        time.sleep(0.3)

        # 조회
        wait.until(EC.element_to_be_clickable((By.ID, "jsSearchButton"))).click()
        time.sleep(0.7)

        # 다운로드
        wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, "CI-MDI-UNIT-DOWNLOAD"))
        ).click()
        time.sleep(0.3)
        wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[@data-type='csv']/a"))
        ).click()

        # 파일 이름 변경
        if wait_and_rename_downloaded_file(f"kospi_{yyyymmdd}.csv"):
            print(f"[SUCCESS] {yyyymmdd} 완료")
        else:
            print(f"[FAIL] {yyyymmdd} 저장 실패")

        # 달력 다시 열기
        time.sleep(0.7)
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "cal-btn-open"))).click()
        time.sleep(0.3)

    except Exception as e:
        print(f"[ERROR] {day_str} 처리 실패: {e}")
        try:
            time.sleep(1.5)
            wait.until(
                EC.element_to_be_clickable((By.CLASS_NAME, "cal-btn-open"))
            ).click()
            time.sleep(0.5)
        except:
            pass


# 메인 반복 로직
while True:
    valid_days = get_valid_days()

    if valid_days:
        for day in valid_days:
            process_date(day)

        # 달 이동
        try:
            wait.until(
                EC.element_to_be_clickable((By.CLASS_NAME, "cal-btn-prevM"))
            ).click()
            time.sleep(0.3)
        except Exception as e:
            print("[종료] 이전 달 이동 실패")
            break
    else:
        try:
            # 혹시라도 날짜 없을 경우 → 달력 다시 열고 이전 달 이동
            wait.until(
                EC.element_to_be_clickable((By.CLASS_NAME, "cal-btn-open"))
            ).click()
            time.sleep(0.5)
            wait.until(
                EC.element_to_be_clickable((By.CLASS_NAME, "cal-btn-prevM"))
            ).click()
            time.sleep(1.2)
        except:
            print("[종료] 더 이상 이전 달 없음")
            break

print("[ALL DONE]")
