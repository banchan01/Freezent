# orchestration/fusion_solver.py
from __future__ import annotations

import os
import json
from typing import Any, Dict, List

from common.schemas import DomainResult, FinalRiskReport, Evidence
from langchain_openai import ChatOpenAI
from common.utils import OPENAI_API_KEY


# ------------- helpers -------------
def _as_dict(x: Any) -> Dict[str, Any]:
    """dict/pydantic/객체 무엇이 오든 dict로 정규화 (None 필드도 보존)."""
    if x is None:
        return {}
    if isinstance(x, dict):
        return x
    if hasattr(x, "model_dump") and callable(getattr(x, "model_dump")):
        try:
            return x.model_dump(exclude_none=False)
        except Exception:
            pass
    if hasattr(x, "dict") and callable(getattr(x, "dict")):
        try:
            return x.dict(exclude_none=False)
        except Exception:
            pass
    try:
        return dict(x.__dict__)  # 마지막 방어
    except Exception:
        return {"value": str(x)}


def _preview_json(d: Dict[str, Any], max_chars: int = 6000) -> str:
    """LLM 프롬프트에 넣기 위해 JSON 문자열로 요약(길이 제한)."""
    try:
        s = json.dumps(d, ensure_ascii=False, default=str)
    except Exception:
        s = str(d)
    if len(s) > max_chars:
        return s[:max_chars] + " ... (truncated)"
    return s


def _build_final_llm_report_with_llm(
    news: DomainResult,
    filing: DomainResult,
    lstm: DomainResult,
    weights: Dict[str, float],
    final_score: float,
    ticker: str,
    horizon: str | None,
) -> str:
    """
    실제 LLM(gpt-4o-mini 기본) 호출로 최종 리포트 텍스트 생성.
    - 각 도메인 DomainResult의 dict 스냅샷(키 보존)과 가중치/점수/기간을 함께 전달
    - 실패 시 진단 문자열 반환
    """
    try:
        model_name = os.getenv("FINAL_LLM_MODEL", "gpt-4o-mini")
        temperature = float(os.getenv("FINAL_LLM_TEMPERATURE", "0.2"))

        model = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            model=model_name,
            temperature=temperature,
        )

        news_d = _as_dict(news)
        filing_d = _as_dict(filing)
        lstm_d = _as_dict(lstm)

        # 프롬프트(지시문은 간결/명확하게)
        prompt = (
            "You are a senior equity risk analyst. Write a concise, decision-grade final risk summary.\n\n"
            f"Company: {ticker}\n"
            f"Horizon: {horizon or 'N/A'}\n"
            f"Weights: {json.dumps(weights, ensure_ascii=False)}\n"
            f"Final Score: {final_score:.4f}\n\n"
            "Each domain below includes: score, events, rationale, and (if present) its own llm_report.\n"
            "Your tasks:\n"
            "1) Synthesize the domain insights into a single coherent narrative.\n"
            "2) Highlight the most material drivers and any conflicts/uncertainties.\n"
            "3) Provide 1–2 actionable implications.\n"
            "4) End with a one-sentence verdict (LOW/MODERATE/ELEVATED) consistent with the scores.\n\n"
            "Return a short markdown report (no code blocks). Use clear section headers.\n\n"
            "=== News Domain ===\n"
            f"{_preview_json(news_d)}\n\n"
            "=== Filings Domain ===\n"
            f"{_preview_json(filing_d)}\n\n"
            "=== LSTM Anomaly Domain ===\n"
            f"{_preview_json(lstm_d)}\n"
        )

        res = model.invoke(prompt)
        txt = getattr(res, "content", None)
        if not txt or not str(txt).strip():
            return "[final_llm_report] empty content from LLM"
        return str(txt).strip()[:8000]

    except Exception as e:
        # 호출 실패해도 최종 보고서는 생성되어야 하니 오류 메모를 반환
        return f"[final_llm_report_error] {e}"


# ------------- fusion logic -------------
def fuse(
    news: DomainResult,
    filing: DomainResult,
    lstm: DomainResult,
    ticker: str,
    horizon: str,
) -> FinalRiskReport:
    # 가중치/최종 점수 계산
    w_news, w_filing, w_lstm = 0.4, 0.4, 0.2
    weights = {"news": w_news, "filing": w_filing, "lstm": w_lstm}
    final_score = (
        w_news * news.domain_risk_score
        + w_filing * filing.domain_risk_score
        + w_lstm * lstm.domain_risk_score
    )

    # Citations 구성 (이전 로직 유지)
    citations: List[Evidence] = []
    if getattr(news, "events", None):
        for event in news.events:
            citations.extend(event.evidence)
    if getattr(news, "rationale", None):
        citations.append(Evidence(source="llm", title="뉴스 요약", snippet=news.rationale))

    if getattr(filing, "events", None):
        for event in filing.events:
            citations.extend(event.evidence)
    if getattr(filing, "rationale", None):
        citations.append(Evidence(source="llm", title="공시 요약", snippet=filing.rationale))

    if getattr(lstm, "events", None):
        for event in lstm.events:
            citations.extend(event.evidence)
    if getattr(lstm, "rationale", None):
        citations.append(Evidence(source="llm", title="LSTM 요약", snippet=lstm.rationale))

    # 🔥 실제 LLM 호출로 최종 llm_report 생성
    final_llm_report = _build_final_llm_report_with_llm(
        news=news,
        filing=filing,
        lstm=lstm,
        weights=weights,
        final_score=final_score,
        ticker=ticker,
        horizon=horizon,
    )

    return FinalRiskReport(
        ticker=ticker,
        horizon=horizon,
        news_score=news.domain_risk_score,
        filing_score=filing.domain_risk_score,
        lstm_score=lstm.domain_risk_score,
        final_score=final_score,
        method="weighted_fusion:v1",
        details={"weights": weights},
        citations=citations,
        llm_report=final_llm_report,
    )


def fusion_solver_node(state):
    news_result = state["news_result"]
    filing_result = state["filing_result"]
    lstm_result = state["lstm_result"]
    ticker = state["ticker"]
    horizon = state["horizon"]
    final_report = fuse(news_result, filing_result, lstm_result, ticker, horizon)
    # None 필드도 보존해서 app.py에서 llm_report가 꼭 보이도록 함
    return {"final_report": final_report.model_dump(exclude_none=False)}
