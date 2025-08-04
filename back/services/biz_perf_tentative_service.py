import requests
import time
import pandas as pd
import json
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from fastapi import HTTPException

load_dotenv()

API_KEY = os.getenv("DART_API_KEY", "e6c728753731f2eb29391d2ee89fd2d59f82d7b7")
BASE_URL = os.getenv("DART_API", "https://opendart.fss.or.kr/api/list.json")

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
    
def parse_financial_table(html:str) -> dict:
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
        
        if len(spans) != 7 or "※" in spans[0] or spans[0].startswith("2.") or spans[0].startswith("3.") or spans[0].startswith("4."):
            continue

        if spans[0] != "-":
            current_main_category = spans[0]
        parsed_data.append({
            "구분": current_main_category,
            "세부구분": spans[1],
            "당기실적": spans[2],
            "전기실적": spans[3],
            "전기대비증감율(%)": spans[4],
            "전년동기실적": spans[5],
            "전년동기대비증감율(%)": spans[6],
        })
    
    final_json = {
        "title": title,
        "data": parsed_data
    }
    return final_json

async def get_biz_performance_tentative(corp_name: str) -> str:
    #########################################
    # corp_name 으로 corp_code 가져오는 로직필요  #
    #########################################

    params = {
        "crtfc_key": API_KEY,
        "corp_code": "00877059",   # 삼성바이오로직스 (DART 고유번호 참고)
        "bgn_de": "20230101",
        "end_de": "20250731",
        "pblntf_ty": "I",          # 거래소공시
        "pblntf_detail_ty": "I004",
        "sort": "date",
        "sort_mth": "desc",
        "page_no": "1",
        "page_count": "100"
    }

    # API 요청
    response = requests.get(BASE_URL, params=params)

    keyword = "영업(잠정)실적(공정공시)"
    results = []

    # 결과 확인
    if response.status_code == 200:
        data = response.json()
        if data['status'] == '000':
            for item in data.get("list", []):
                if keyword in item['report_nm']:
                    html = show_me_the_html(item['rcept_no'])
                    parsed_data_json = parse_financial_table(html)
                    results.append(parsed_data_json)
            return json.dumps(results, indent=2, ensure_ascii=False)
                    
        else:
            raise HTTPException(status_code=400, detail=f"DART API 오류 코드: {data['status']} - {data.get('message')}")
    else:
        raise HTTPException(status_code=502, detail=f"HTTP 요청 실패: {response.status_code}")


