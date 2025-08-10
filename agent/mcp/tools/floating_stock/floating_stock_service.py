# tools/floating_stock/floating_stock_service.py

import httpx
import os
import zipfile
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from typing import Optional, List, Dict
from pydantic import BaseModel

# =========================
# 0) Pydantic 모델 (inline)
# =========================


class StockIdentifier(BaseModel):
    """주식 식별자 모델 (종목명 또는 종목코드)"""

    stock_name: Optional[str] = None
    stock_code: Optional[str] = None


class CorpCodeRequest(BaseModel):
    """고유번호 조회 요청 모델"""

    identifier: StockIdentifier


class CorpInfo(BaseModel):
    """기업 정보 모델"""

    corp_code: str
    corp_name: str
    corp_eng_name: Optional[str] = None
    stock_code: Optional[str] = None
    modify_date: Optional[str] = None


class CorpCodeResponse(BaseModel):
    """고유번호 조회 응답 모델"""

    success: bool
    corp_code: Optional[str] = None
    corp_name: Optional[str] = None
    corp_eng_name: Optional[str] = None
    stock_code: Optional[str] = None
    modify_date: Optional[str] = None
    error: Optional[str] = None


class DownloadResponse(BaseModel):
    """다운로드 응답 모델"""

    success: bool
    message: Optional[str] = None
    path: Optional[str] = None
    error: Optional[str] = None
    status: Optional[int] = None


class MajorShareholderResponse(BaseModel):
    """최대주주 현황 API 응답 모델"""

    status: str
    message: str
    trmend_posesn_stock_qota_rt: float  # 기말 소유 주식 지분율


class FloatingStockResponse(BaseModel):
    """유동주식 비율 계산 응답 모델"""

    success: bool
    floating_ratio: Optional[float] = None  # 현재 유동주식 비율
    deviation_from_average: Optional[float] = None  # 평균 대비 차이
    is_above_average: Optional[bool] = None  # 평균보다 큰지 여부
    error: Optional[str] = None


# ========= .env / 기본 설정 =========
load_dotenv()

DART_API_KEY = os.getenv("DART_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


# =========================
# 1) 경로 해석 유틸
# =========================


def _os_default_data_dir() -> str:
    """OS별 기본 데이터 디렉토리"""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
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


def _find_repo_dataset_dir(max_up: int = 6) -> Optional[str]:
    """
    현재 파일 기준으로 위로 올라가며 'dataset' 폴더가 있으면 그 경로를 반환.
    예) .../Freezent/dataset  (네가 쓰는 경로와 매칭)
    """
    d = os.path.abspath(os.path.dirname(__file__))
    for _ in range(max_up):
        candidate = os.path.join(d, "dataset")
        if os.path.isdir(candidate):
            return candidate
        d = os.path.dirname(d)
    return None


def resolve_data_paths() -> Dict[str, str]:
    """
    CORP_XML_PATH / KOSPI_DATA_PATH을 환경변수 → 프로젝트 dataset → OS 기본 순으로 결정
    - CORP_XML_PATH: 파일 경로를 직접 지정
    - FREEZENT_DATA_DIR: 디렉토리를 지정(그 안의 corpCode.zip / all_kospi_data.parquet 사용)
    """
    corp_xml_path_env = os.getenv("CORP_XML_PATH")
    kospi_path_env = os.getenv("KOSPI_DATA_PATH")
    data_root = os.getenv("FREEZENT_DATA_DIR")
    repo_dataset = _find_repo_dataset_dir()

    if data_root:
        data_dir = data_root
    elif repo_dataset:
        data_dir = repo_dataset
    else:
        data_dir = _os_default_data_dir()

    os.makedirs(data_dir, exist_ok=True)

    corp_xml_path = corp_xml_path_env or os.path.join(data_dir, "corpCode.zip")
    kospi_data_path = kospi_path_env or os.path.join(data_dir, "all_kospi_data.parquet")

    os.makedirs(os.path.dirname(corp_xml_path), exist_ok=True)
    os.makedirs(os.path.dirname(kospi_data_path), exist_ok=True)

    return {
        "CORP_XML_PATH": corp_xml_path,
        "KOSPI_DATA_PATH": kospi_data_path,
        "DATA_DIR": data_dir,
    }


_PATHS = resolve_data_paths()
CORP_XML_PATH: str = _PATHS["CORP_XML_PATH"]
KOSPI_DATA_PATH: str = _PATHS["KOSPI_DATA_PATH"]


# =========================
# 2) 기능 구현
# =========================


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

    with open(CORP_XML_PATH, "wb") as f:
        f.write(response.content)

    return DownloadResponse(
        success=True, message="corpCode.zip saved", path=CORP_XML_PATH
    )


def parse_corp_xml(xml_path: str) -> Optional[List[Dict]]:
    """XML 파일에서 기업 정보를 파싱합니다."""
    try:
        with zipfile.ZipFile(xml_path, "r") as zip_file:
            xml_files = [f for f in zip_file.namelist() if f.endswith(".xml")]
            if not xml_files:
                return None

            xml_content = zip_file.read(xml_files[0])
            root = ET.fromstring(xml_content)

            corp_list: List[Dict] = []
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
    except Exception:
        return None


async def get_corp_code_by_name_or_code(req: StockIdentifier) -> CorpCodeResponse:
    """종목명 또는 종목코드로 고유번호를 조회합니다."""
    if not req.stock_name and not req.stock_code:
        return CorpCodeResponse(
            success=False, error="종목명 또는 종목코드를 입력해주세요."
        )

    corp_list = parse_corp_xml(CORP_XML_PATH)

    if not corp_list:
        download_result = await download_corp_xml()
        if not download_result.success:
            return CorpCodeResponse(
                success=False, error="기업 정보를 다운로드할 수 없습니다."
            )
        corp_list = parse_corp_xml(CORP_XML_PATH)
        if not corp_list:
            return CorpCodeResponse(
                success=False, error="기업 정보를 파싱할 수 없습니다."
            )

    result = None
    exact_matches: List[Dict] = []
    partial_matches: List[Dict] = []

    for corp in corp_list:
        cname = corp.get("corp_name")
        scode = corp.get("stock_code")
        if not cname or not scode:
            continue

        if req.stock_name:
            if cname == req.stock_name:
                exact_matches.append(corp)
            elif req.stock_name in cname:
                partial_matches.append(corp)
        elif req.stock_code:
            if scode == req.stock_code:
                exact_matches.append(corp)
            elif req.stock_code in scode:
                partial_matches.append(corp)

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
            corp_eng_name=result.get("corp_eng_name"),
            stock_code=result["stock_code"],
            modify_date=result.get("modify_date"),
        )
    else:
        return CorpCodeResponse(
            success=False, error="해당하는 기업을 찾을 수 없습니다."
        )


async def get_major_shareholders(
    corp_code: str, year: str
) -> Optional[MajorShareholderResponse]:
    """최대주주 현황을 조회합니다."""
    url = "https://opendart.fss.or.kr/api/hyslrSttus.json"
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
            status = result.get("status", "") or data.get("status", "")
            message = result.get("message", "") or data.get("message", "")

            total_ratio = 0.0
            for item in data.get("list", []) or []:
                if item.get("nm") == "계":
                    val = item.get("trmend_posesn_stock_qota_rt")
                    if val:
                        try:
                            total_ratio += float(val)
                        except ValueError:
                            pass

            if total_ratio == 0.0:
                for item in data.get("list", []) or []:
                    val = item.get("trmend_posesn_stock_qota_rt")
                    if val:
                        try:
                            total_ratio += float(val)
                        except ValueError:
                            pass

            return MajorShareholderResponse(
                status=status,
                message=message,
                trmend_posesn_stock_qota_rt=total_ratio,
            )
        else:
            return None
    except Exception:
        return None


def calculate_floating_ratio(shareholders_data: MajorShareholderResponse) -> float:
    """최대주주 현황 데이터로부터 유동주식 비율을 계산합니다."""
    floating_ratio = 100.0 - shareholders_data.trmend_posesn_stock_qota_rt
    return max(0.0, floating_ratio)


async def calculate_floating_stock_ratio(req: StockIdentifier) -> FloatingStockResponse:
    """유동주식 비율을 계산합니다. (corp_code는 로컬 corpCode.xml 기반 조회)"""
    if not req.stock_name and not req.stock_code:
        return FloatingStockResponse(
            success=False, error="종목명 또는 종목코드를 입력해주세요."
        )

    # 1) 로컬 corpCode.xml 기반으로 corp_code 조회
    corp_res = await get_corp_code_by_name_or_code(req)
    if not corp_res.success or not corp_res.corp_code:
        return FloatingStockResponse(
            success=False,
            error=corp_res.error or "기업 고유번호(corp_code) 조회에 실패했습니다.",
        )

    corp_code = corp_res.corp_code

    # 2) 최대주주 현황 (2023/2024)
    ms_2023 = await get_major_shareholders(corp_code, "2023")
    ms_2024 = await get_major_shareholders(corp_code, "2024")

    r1 = ms_2023.trmend_posesn_stock_qota_rt if ms_2023 else None
    r2 = ms_2024.trmend_posesn_stock_qota_rt if ms_2024 else None

    total, cnt = 0.0, 0
    if r1 is not None:
        total += r1
        cnt += 1
    if r2 is not None:
        total += r2
        cnt += 1

    if cnt == 0:
        return FloatingStockResponse(
            success=False, error="최대주주 현황 데이터를 찾을 수 없습니다."
        )

    try:
        avg_owner_ratio = total / cnt
        floating_ratio = 100.0 - avg_owner_ratio
    except Exception as e:
        return FloatingStockResponse(
            success=False, error=f"유동주식 비율 계산 중 오류: {e}"
        )

    kospi_average = 53.0
    deviation = floating_ratio - kospi_average
    is_above = floating_ratio > kospi_average

    return FloatingStockResponse(
        success=True,
        floating_ratio=floating_ratio,
        deviation_from_average=deviation,
        is_above_average=is_above,
    )


# =========================
# 3) 메인 함수 (실험용)
# =========================
if __name__ == "__main__":
    import asyncio

    test_request = StockIdentifier(stock_name="삼성전자", stock_code="005930")

    async def main():
        result = await calculate_floating_stock_ratio(test_request)

        # Accessing the returned values
        if result.success:
            print(f"유동주식 비율: {result.floating_ratio:.2f}%")
            print(f"평균과의 차이: {result.deviation_from_average:.2f}%")
            print(f"평균 이상 여부: {result.is_above_average}")
        else:
            print(f"오류 발생: {result.error}")

    asyncio.run(main())
