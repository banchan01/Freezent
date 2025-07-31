import httpx
import os
import zipfile
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional, List, Dict
from format.floating_stock_format import (
    CorpCodeResponse,
    DownloadResponse,
    CorpInfo,
    StockIdentifier,
    MajorShareholderResponse,
    FloatingStockResponse,
)

# .env 파일 로드
load_dotenv()

DART_API_KEY = os.getenv("DART_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
SAVE_PATH = r"C:\Users\kimmc\Desktop\project\freezent\dataset\corpCode.zip"
KOSPI_DATA_PATH = r"C:\Users\kimmc\Desktop\project\freezent\all_kospi_data.parquet"


async def download_corp_xml() -> DownloadResponse:
    """DART에서 기업 고유번호 XML 파일을 다운로드합니다."""
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART_API_KEY}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code != 200:
        return DownloadResponse(
            success=False,
            error="Download failed",
            status=response.status_code,
        )

    # 저장
    with open(SAVE_PATH, "wb") as f:
        f.write(response.content)

    return DownloadResponse(success=True, message="corp_code.zip saved", path=SAVE_PATH)


def parse_corp_xml(xml_path: str) -> Optional[List[Dict]]:
    """XML 파일에서 기업 정보를 파싱합니다."""
    try:
        with zipfile.ZipFile(xml_path, "r") as zip_file:
            # ZIP 파일 내의 XML 파일 찾기
            xml_files = [f for f in zip_file.namelist() if f.endswith(".xml")]
            if not xml_files:
                return None

            # 첫 번째 XML 파일 읽기
            xml_content = zip_file.read(xml_files[0])

            # XML 파싱
            root = ET.fromstring(xml_content)

            corp_list = []
            # result/list 구조로 파싱
            for corp in root.findall("list"):
                corp_code_elem = corp.find("corp_code")
                corp_name_elem = corp.find("corp_name")
                corp_eng_name_elem = corp.find("corp_eng_name")
                stock_code_elem = corp.find("stock_code")
                modify_date_elem = corp.find("modify_date")

                corp_info = {
                    "corp_code": (
                        corp_code_elem.text
                        if corp_code_elem is not None and corp_code_elem.text
                        else ""
                    ),
                    "corp_name": (
                        corp_name_elem.text
                        if corp_name_elem is not None and corp_name_elem.text
                        else ""
                    ),
                    "corp_eng_name": (
                        corp_eng_name_elem.text
                        if corp_eng_name_elem is not None and corp_eng_name_elem.text
                        else None
                    ),
                    "stock_code": (
                        stock_code_elem.text
                        if stock_code_elem is not None and stock_code_elem.text
                        else None
                    ),
                    "modify_date": (
                        modify_date_elem.text
                        if modify_date_elem is not None and modify_date_elem.text
                        else None
                    ),
                }
                corp_list.append(corp_info)

            return corp_list
    except Exception as e:
        return None


async def get_corp_code_by_name_or_code(req: StockIdentifier) -> CorpCodeResponse:
    """종목명 또는 종목코드로 고유번호를 조회합니다."""
    if not req.stock_name and not req.stock_code:
        return CorpCodeResponse(
            success=False, error="종목명 또는 종목코드를 입력해주세요."
        )

    # XML 파일 파싱
    corp_list = parse_corp_xml(SAVE_PATH)

    if not corp_list:
        # 파일이 없으면 먼저 다운로드 시도
        download_result = await download_corp_xml()
        if not download_result.success:
            return CorpCodeResponse(
                success=False,
                error="기업 정보를 다운로드할 수 없습니다.",
            )
        corp_list = parse_corp_xml(SAVE_PATH)
        if not corp_list:
            return CorpCodeResponse(
                success=False,
                error="기업 정보를 파싱할 수 없습니다.",
            )

    # 검색
    result = None
    exact_matches = []
    partial_matches = []

    for corp in corp_list:
        if (
            corp["corp_name"] and corp["stock_code"]
        ):  # 종목명과 주식코드가 모두 있는 경우만
            # 주식종목명으로 검색
            if req.stock_name:
                if corp["corp_name"] == req.stock_name:
                    exact_matches.append(corp)
                elif req.stock_name in corp["corp_name"]:
                    partial_matches.append(corp)

            # 주식코드로 검색
            elif req.stock_code:
                if corp["stock_code"] == req.stock_code:
                    exact_matches.append(corp)
                elif req.stock_code in corp["stock_code"]:
                    partial_matches.append(corp)

    # 정확한 매칭이 있으면 첫 번째 결과 사용, 없으면 부분 매칭의 첫 번째 결과 사용
    if exact_matches:
        result = exact_matches[0]
        print(f"정확한 매칭: {result['corp_name']} ({result['stock_code']})")
    elif partial_matches:
        result = partial_matches[0]
        print(f"부분 매칭: {result['corp_name']} ({result['stock_code']})")
    else:
        print(f"매칭 없음: stock_name={req.stock_name}, stock_code={req.stock_code}")

    if result:
        return CorpCodeResponse(
            success=True,
            corp_code=result["corp_code"],
            corp_name=result["corp_name"],
            corp_eng_name=result["corp_eng_name"],
            stock_code=result["stock_code"],
            modify_date=result["modify_date"],
        )
    else:
        return CorpCodeResponse(
            success=False, error="해당하는 기업을 찾을 수 없습니다."
        )


async def get_major_shareholders(
    corp_code: str, year: str
) -> Optional[MajorShareholderResponse]:
    """최대주주 현황을 조회합니다."""
    url = f"https://opendart.fss.or.kr/api/hyslrSttus.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bsns_year": year,
        "reprt_code": "11011",  # 사업보고서
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            result = data.get("result", {})

            # DART API 응답 구조에서 필요한 필드들 추출
            data["status"] = result.get("status", "")
            data["message"] = result.get("message", "")

            # trmend_posesn_stock_qota_rt 값 추출
            total_ratio = 0.0
            for item in data.get("list", []):
                if item.get("nm") == "계":
                    val = item.get("trmend_posesn_stock_qota_rt")
                    if val:
                        try:
                            total_ratio += float(val)
                        except ValueError:
                            pass
            # 만약 '계'가 하나도 없으면 전체 행 합산
            if total_ratio == 0.0:
                for item in data.get("list", []):
                    val = item.get("trmend_posesn_stock_qota_rt")
                    if val:
                        try:
                            total_ratio += float(val)
                        except ValueError:
                            pass

            data["trmend_posesn_stock_qota_rt"] = total_ratio
            return MajorShareholderResponse(**data)
        else:
            return None
    except Exception as e:
        return None


def calculate_floating_ratio(shareholders_data: MajorShareholderResponse) -> float:
    """최대주주 현황 데이터로부터 유동주식 비율을 계산합니다."""
    # 유동주식 비율 = 100% - 최대주주 지분율
    floating_ratio = 100.0 - shareholders_data.trmend_posesn_stock_qota_rt

    return max(0.0, floating_ratio)  # 음수가 되지 않도록


async def calculate_floating_stock_ratio(
    req: StockIdentifier,
) -> FloatingStockResponse:
    """유동주식 비율을 계산합니다."""
    if not req.stock_name and not req.stock_code:
        return FloatingStockResponse(
            success=False, error="종목명 또는 종목코드를 입력해주세요."
        )

    # 1. 고유번호 조회 (API 호출)
    async with httpx.AsyncClient() as client:
        corp_code_response = await client.post(
            f"{API_BASE_URL}/floating_stocks/get_corp_code",
            json={"stock_name": req.stock_name, "stock_code": req.stock_code},
        )

        if corp_code_response.status_code != 200:
            return FloatingStockResponse(
                success=False, error="고유번호 조회에 실패했습니다."
            )

        corp_code_result = corp_code_response.json()
        print(corp_code_result)
        if not corp_code_result.get("success"):
            return FloatingStockResponse(
                success=False,
                error=corp_code_result.get("error", "고유번호 조회에 실패했습니다."),
            )

    # 2023년 데이터 조회
    shareholders_2023 = await get_major_shareholders(
        corp_code_result.get("corp_code"), str(2023)
    )
    trmend_posesn_2023 = None
    if shareholders_2023:
        trmend_posesn_2023 = shareholders_2023.trmend_posesn_stock_qota_rt

    # 2024년 데이터 조회
    shareholders_2024 = await get_major_shareholders(
        corp_code_result.get("corp_code"), str(2024)
    )
    trmend_posesn_2024 = None
    if shareholders_2024:
        trmend_posesn_2024 = shareholders_2024.trmend_posesn_stock_qota_rt

    # 3. 최근 2년 평균 최대주주 지분율 계산
    total_ratio = 0
    count = 0

    if trmend_posesn_2023 is not None:
        total_ratio += trmend_posesn_2023
        count += 1

    if trmend_posesn_2024 is not None:
        total_ratio += trmend_posesn_2024
        count += 1

    if count == 0:
        return FloatingStockResponse(
            success=False, error="최대주주 현황 데이터를 찾을 수 없습니다."
        )
    else:
        try:
            average_trmend_posesn = total_ratio / count
        except ZeroDivisionError:
            return FloatingStockResponse(
                success=False, error="평균 계산 중 오류가 발생했습니다."
            )
    # 4. 유동주식 비율 계산 (100% - 최대주주 지분율)
    try:
        average_floating_ratio = 100.0 - average_trmend_posesn
    except Exception as e:
        return FloatingStockResponse(
            success=False, error=f"유동주식 비율 계산 중 오류가 발생했습니다: {str(e)}"
        )

    # 5. KOSPI 평균과의 차이 계산
    try:
        kospi_average = 53.0
        deviation_from_average = average_floating_ratio - kospi_average
        is_above_average = average_floating_ratio > kospi_average
    except Exception as e:
        return FloatingStockResponse(
            success=False, error=f"KOSPI 평균 비교 중 오류가 발생했습니다: {str(e)}"
        )

    return FloatingStockResponse(
        success=True,
        floating_ratio=average_floating_ratio,
        deviation_from_average=deviation_from_average,
        is_above_average=is_above_average,
    )
