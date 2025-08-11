import os
import json
import requests
import httpx
import zipfile
import xml.etree.ElementTree as ET
import time
import pandas as pd
from fastapi import HTTPException
from typing import Optional, List, Dict
from pydantic import BaseModel
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

# =========================
# .env 로드
# =========================
load_dotenv()
API_KEY = os.getenv("DART_API_KEY")
BASE_URL = "https://opendart.fss.or.kr/api/list.json"


# =========================
# Pydantic 모델
# =========================
class StockIdentifier(BaseModel):
    stock_name: Optional[str] = None
    stock_code: Optional[str] = None


class CorpCodeResponse(BaseModel):
    success: bool
    corp_code: Optional[str] = None
    corp_name: Optional[str] = None
    error: Optional[str] = None


# =========================
# XML 경로 설정
# =========================
def _os_default_data_dir() -> str:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(
            r"~\\AppData\\Local"
        )
        return os.path.join(base, "Freezent", "data")
    elif os.sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~/Library/Application Support"), "Freezent", "data"
        )
    else:
        xdg = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share"
        )
        return os.path.join(xdg, "Freezent", "data")


def resolve_data_paths() -> Dict[str, str]:
    data_dir = _os_default_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    corp_xml_path = os.path.join(data_dir, "corpCode.zip")
    return {"CORP_XML_PATH": corp_xml_path}


_PATHS = resolve_data_paths()
CORP_XML_PATH = _PATHS["CORP_XML_PATH"]


# =========================
# corp_code 조회 로직
# =========================
async def download_corp_xml() -> bool:
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={API_KEY}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        return False
    with open(CORP_XML_PATH, "wb") as f:
        f.write(resp.content)
    return True


def parse_corp_xml(xml_path: str) -> Optional[List[Dict]]:
    try:
        with zipfile.ZipFile(xml_path, "r") as zf:
            xml_files = [f for f in zf.namelist() if f.endswith(".xml")]
            if not xml_files:
                return None
            xml_content = zf.read(xml_files[0])
            root = ET.fromstring(xml_content)
            corp_list = []
            for corp in root.findall("list"):
                corp_info = {
                    "corp_code": corp.findtext("corp_code", ""),
                    "corp_name": corp.findtext("corp_name", ""),
                    "stock_code": corp.findtext("stock_code", None),
                }
                corp_list.append(corp_info)
            return corp_list
    except Exception:
        return None


async def get_corp_code_by_name_or_code(req: StockIdentifier) -> CorpCodeResponse:
    if not req.stock_name and not req.stock_code:
        return CorpCodeResponse(success=False, error="종목명 또는 종목코드 입력 필요")

    corp_list = parse_corp_xml(CORP_XML_PATH)
    if not corp_list:
        ok = await download_corp_xml()
        if not ok:
            return CorpCodeResponse(success=False, error="XML 다운로드 실패")
        corp_list = parse_corp_xml(CORP_XML_PATH)
        if not corp_list:
            return CorpCodeResponse(success=False, error="XML 파싱 실패")

    for corp in corp_list:
        if req.stock_name and corp["corp_name"] == req.stock_name:
            return CorpCodeResponse(
                success=True, corp_code=corp["corp_code"], corp_name=corp["corp_name"]
            )
        if req.stock_code and corp["stock_code"] == req.stock_code:
            return CorpCodeResponse(
                success=True, corp_code=corp["corp_code"], corp_name=corp["corp_name"]
            )

    return CorpCodeResponse(success=False, error="기업 찾을 수 없음")


def show_me_the_html(rcp_no: str) -> str:
    # 셀레니움 설정
    options = Options()
    options.add_argument("--headless")  # 창 없이 실행
    driver = webdriver.Chrome(options=options)

    # 접수번호로 뷰어 페이지 접근
    url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}"
    driver.get(url)

    time.sleep(3)  # JavaScript 로딩 대기

    # 렌더링된 HTML 소스 가져오기
    html = driver.page_source
    src = extract_iframe_src(html)
    absolute_src = f"https://dart.fss.or.kr{src}"
    driver.get(absolute_src)

    time.sleep(3)
    final_html = driver.page_source
    driver.quit()
    return final_html


def extract_iframe_src(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # id가 'ifrm'인 iframe 태그 찾기
    iframe = soup.find("iframe", id="ifrm")

    if iframe and iframe.has_attr("src"):
        return iframe["src"]
    else:
        return None


def parse_financial_table(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string.strip() if soup.title else "No Title"
    # 테이블 선택
    table = soup.find("table", {"id": "XFormD1_Form0_RepeatTable0"})
    rows = table.find_all("tr")

    current_main_category = None
    parsed_data = []

    for row in rows:
        cols = row.find_all("td")
        spans = [col.get_text(strip=True) for col in cols]

        if (
            len(spans) != 7
            or "※" in spans[0]
            or spans[0].startswith("2.")
            or spans[0].startswith("3.")
            or spans[0].startswith("4.")
        ):
            continue

        if spans[0] != "-":
            current_main_category = spans[0]
        parsed_data.append(
            {
                "구분": current_main_category,
                "세부구분": spans[1],
                "당기실적": spans[2],
                "전기실적": spans[3],
                "전기대비증감율(%)": spans[4],
                "전년동기실적": spans[5],
                "전년동기대비증감율(%)": spans[6],
            }
        )

    final_json = {"title": title, "data": parsed_data}
    return final_json


async def get_biz_performance_tentative(corp_name: str) -> str:
    corp_res = await get_corp_code_by_name_or_code(
        StockIdentifier(stock_name=corp_name)
    )
    if not corp_res.success or not corp_res.corp_code:
        raise HTTPException(
            status_code=404, detail=f"기업 고유번호 조회 실패: {corp_res.error}"
        )

    corp_code = corp_res.corp_code
    params = {
        "crtfc_key": API_KEY,
        "corp_code": corp_code,
        "bgn_de": "20230101",
        "end_de": "20250731",
        "pblntf_ty": "I",
        "pblntf_detail_ty": "I004",
        "sort": "date",
        "sort_mth": "desc",
        "page_no": "1",
        "page_count": "100",
    }

    try:
        resp = requests.get(BASE_URL, params=params, timeout=15)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"DART 요청 실패: {e}")

    keyword = "영업(잠정)실적(공정공시)"
    results = []

    if resp.status_code == 200:
        data = resp.json()
        if data.get("status") == "000":
            for item in data.get("list", []):
                if keyword in item.get("report_nm", ""):
                    html = show_me_the_html(item["rcept_no"])
                    parsed_data_json = parse_financial_table(html)
                    results.append(parsed_data_json)
            return json.dumps(results, indent=2, ensure_ascii=False)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"DART API 오류: {data.get('status')} - {data.get('message')}",
            )
    else:
        raise HTTPException(
            status_code=502, detail=f"HTTP 요청 실패: {resp.status_code}"
        )


# =========================
# 테스트 main
# =========================
if __name__ == "__main__":
    import asyncio

    test_corp_name = "삼성바이오로직스"

    async def main():
        try:
            result = await get_biz_performance_tentative(test_corp_name)
            print(f"[{test_corp_name}] 조회 결과:\n{result}")
        except Exception as e:
            print("오류:", e)

    asyncio.run(main())
