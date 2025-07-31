from fastapi import APIRouter
from typing import Optional
from services.floating_stock_service import (
    download_corp_xml,
    get_corp_code_by_name_or_code,
    get_major_shareholders,
    calculate_floating_stock_ratio,
)
from format.floating_stock_format import (
    StockIdentifier,
    CorpCodeRequest,
    CorpCodeResponse,
    DownloadResponse,
    FloatingStockResponse,
)

router = APIRouter(prefix="/floating_stocks")


# xml 파일 다운로드
@router.get("/download_corp_number", response_model=DownloadResponse)
async def download_corp_number():
    return await download_corp_xml()


# 종목명 또는 종목코드로 고유번호를 조회
@router.post("/get_corp_code", response_model=CorpCodeResponse)
async def get_corp_code(req: StockIdentifier):
    return await get_corp_code_by_name_or_code(req)


# 최대주주 현황 조회
@router.get("/get_major_shareholders/{corp_code}/{year}")
async def get_major_shareholders_api(corp_code: str, year: str):
    return await get_major_shareholders(corp_code, year)


# 유동주식 비율, 평균에서 차이 출력력
@router.post("/calculate_floating_ratio", response_model=FloatingStockResponse)
async def calculate_floating_ratio(req: StockIdentifier):
    return await calculate_floating_stock_ratio(req)
