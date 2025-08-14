# app.py
from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from orchestration.graph import build_meta_graph


# ---------------------------
# Utilities
# ---------------------------
def _as_dict(x: Any) -> Dict[str, Any]:
    """
    dict / pydantic / 네임스페이스 등 무엇이 오든 dict로 정규화
    - pydantic v2: exclude_none=False 강제
    - pydantic v1: exclude_none=False 강제
    """
    if x is None:
        return {}
    if isinstance(x, dict):
        return x
    # pydantic v2
    if hasattr(x, "model_dump") and callable(getattr(x, "model_dump")):
        try:
            return x.model_dump(exclude_none=False)
        except Exception:
            pass
    # pydantic v1
    if hasattr(x, "dict") and callable(getattr(x, "dict")):
        try:
            return x.dict(exclude_none=False)
        except Exception:
            pass
    # 일반 객체
    try:
        return dict(x.__dict__)
    except Exception:
        return {"value": x}


# ---------------------------
# FastAPI Schemas
# ---------------------------
class AnalyzeRequest(BaseModel):
    company: str = Field(..., description="회사명(예: 삼성전자)")
    horizon: Optional[str] = Field(default="30d", description="리스크 평가 기간(예: 30d)")

class FinalReportEnvelope(BaseModel):
    final_report: Dict[str, Any] = Field(..., description="최종 보고서 원문(JSON)")


# ---------------------------
# App
# ---------------------------
app = FastAPI(title="Market Manipulation Detector API", version="1.0.0")


def run_pipeline(company: str, horizon: str = "30d") -> Dict[str, Any]:
    """
    LangGraph 파이프라인을 실행하고 final_report(dict)를 반환합니다.
    final_report를 못 구하면 HTTPException을 발생시킵니다.
    """
    graph_app = build_meta_graph()

    init = {
        "ticker": company,                 # ← 입력값 반영 (회사명 또는 티커명)
        "horizon": horizon or "30d",
        "task": "Assess combined risk from news & filings",
        "news_result": None,
        "filing_result": None,
        "lstm_result": None,
        "final_report": None,
    }

    last: Dict[str, Any] = {}
    try:
        # LangGraph는 stream으로 단계별 state를 넘겨줍니다.
        for state in graph_app.stream(init):
            last = state
    except Exception as e:
        # 그래프 내부 예외를 포착하여 502로 변환
        raise HTTPException(status_code=502, detail=f"Pipeline execution failed: {repr(e)}")

    final_report = (last.get("final") or {}).get("final_report")
    if not final_report:
        raise HTTPException(status_code=502, detail="Final Report could not be generated.")

    # dict로 정규화하여 반환
    return _as_dict(final_report)


# ---------------------------
# Routes
# ---------------------------
@app.post("/analyze", response_model=FinalReportEnvelope, summary="회사명 기반 최종 리스크 보고서 생성")
def analyze(req: AnalyzeRequest):
    """
    회사명을 입력으로 받아 News/Filings/LSTM 도메인 결과를 종합한 최종 보고서만 반환합니다.
    """
    company = (req.company or "").strip()
    if not company:
        raise HTTPException(status_code=400, detail="company(회사명)은 필수입니다.")

    final_dict = run_pipeline(company=company, horizon=req.horizon or "30d")
    # API 계약: 최종 보고서만 감싸서 반환
    return JSONResponse(content={"final_report": final_dict})


@app.get("/healthz", summary="헬스 체크")
def healthz():
    return {"status": "ok"}


# ---------------------------
# Local run (optional)
# ---------------------------
if __name__ == "__main__":
    # 로컬 실행 시:
    # uvicorn app:app --reload --host 0.0.0.0 --port 8000
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
