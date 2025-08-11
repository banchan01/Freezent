# mcp/tools/floating_stock/floating_stock_service.py
import httpx
import os
import sys
import json
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
DART_API_KEY = os.getenv("DART_API_KEY","")

# Pydantic Models
class MajorShareholderResponse(BaseModel):
    status: str
    message: str
    trmend_posesn_stock_qota_rt: float

class FloatingStockResponse(BaseModel):
    success: bool
    floating_ratio: Optional[float] = None
    deviation_from_average: Optional[float] = None
    is_above_average: Optional[bool] = None
    error: Optional[str] = None

# Environment Variables

async def get_major_shareholders(corp_code: str, year: str) -> Optional[MajorShareholderResponse]:
    """최대주주 현황을 조회합니다."""
    url = "https://opendart.fss.or.kr/api/hyslrSttus.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bsns_year": year,
        "reprt_code": "11011",  # 사업보고서
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                # DART may return an error object even with a 200 status
                if data.get("status") != "000":
                    return None
                
                total_ratio = 0.0
                # The logic to sum up ratios might need adjustment based on API response structure
                for item in data.get("list", []) or []:
                    val = item.get("trmend_posesn_stock_qota_rt")
                    if val:
                        try:
                            total_ratio += float(val)
                        except (ValueError, TypeError):
                            continue
                
                return MajorShareholderResponse(
                    status=data.get("status", ""),
                    message=data.get("message", ""),
                    trmend_posesn_stock_qota_rt=total_ratio,
                )
            return None
        except (httpx.RequestError, json.JSONDecodeError) as e:
            print(f"[floating_stock_service] Error fetching major shareholders: {e}")
            return None

async def calculate_floating_stock_ratio(corp_code: str) -> FloatingStockResponse:
    """Calculates the floating stock ratio using a given corp_code."""
    print(f"[DEBUG] corp_code: {corp_code}, DART_API_KEY: {repr(DART_API_KEY)}")

    if not corp_code:
        return FloatingStockResponse(success=False, error="corp_code must be provided.")
    if not DART_API_KEY:
        print(f"im'here: {DART_API_KEY}")
        return FloatingStockResponse(success=False, error="DART_API_KEY must be provided.")

    # Get major shareholder data for the last two years to average them
    ms_2023 = await get_major_shareholders(corp_code, "2023")
    ms_2024 = await get_major_shareholders(corp_code, "2024")

    ratios = [ms.trmend_posesn_stock_qota_rt for ms in [ms_2023, ms_2024] if ms]
    if not ratios:
        return FloatingStockResponse(success=False, error="Could not retrieve major shareholder data for the last two years.")

    try:
        avg_owner_ratio = sum(ratios) / len(ratios)
        floating_ratio = 100.0 - avg_owner_ratio
    except ZeroDivisionError:
        return FloatingStockResponse(success=False, error="Could not calculate average owner ratio.")

    # Assuming a static KOSPI average for comparison
    kospi_average = 53.0
    deviation = floating_ratio - kospi_average
    is_above = floating_ratio > kospi_average

    return FloatingStockResponse(
        success=True,
        floating_ratio=floating_ratio,
        deviation_from_average=deviation,
        is_above_average=is_above,
    )