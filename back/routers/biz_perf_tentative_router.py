import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from services.biz_perf_tentative_service import get_biz_performance_tentative



router = APIRouter(prefix="/biz_perf_tentative")

class PerformanceRequest(BaseModel):
    corp_name: str

@router.post("/biz_perf_tentative")
async def biz_performance_api(req: PerformanceRequest) -> JSONResponse:
    try:
        result = await get_biz_performance_tentative(req.corp_name)
        if not result:
            raise HTTPException(status_code=404, detail="해당 기업의 잠정 실적 공시를 찾을 수 없습니다.")
        return JSONResponse(content=json.loads(result), status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))