# orchestration/graph.py
from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from typing import Any, Dict

from common.state import MetaState
from orchestration.meta_planner import make_domain_tasks
from orchestration.fusion_solver import fuse

from agents.base_rewoo import BaseReWOO

# Domain-specific planners and solvers
from agents.news_rewoo.planner import NEWS_PLANNER_PROMPT
from agents.news_rewoo.solver import news_postprocess
from agents.filings_rewoo.planner import FILINGS_PLANNER_PROMPT
from agents.filings_rewoo.solver import filings_postprocess
from agents.lstm_agent.planner import LSTM_PLANNER_PROMPT
from agents.lstm_agent.solver import lstm_postprocess


# ---- Instantiate domain agents using the generic BaseReWOO ----
# The domain-specific logic is now entirely in the planner prompts and postprocess functions.
news_agent = BaseReWOO("news", NEWS_PLANNER_PROMPT)
filings_agent = BaseReWOO("filing", FILINGS_PLANNER_PROMPT)
lstm_agent = BaseReWOO("lstm", LSTM_PLANNER_PROMPT)


# ---- Helpers ----
def _safe_default_result(domain: str, note: str = "no data") -> Dict[str, Any]:
    # 각 도메인 결과의 최소 스키마를 통일해 둡니다.
    return {
        "domain": domain,
        "domain_risk_score": 0.0,
        "note": note,
    }


# ---- Meta Graph Nodes ----

def meta_plan(state: MetaState) -> Dict[str, Any]:
    tasks = make_domain_tasks(state["ticker"], state["horizon"])
    return {
        "task": f"Risk assessment for {state['ticker']} over {state['horizon']}",
        **tasks,
    }


def run_news(state: MetaState):
    """
    meta_plan에서 news_task가 비어도 안전하게 기본값을 생성해 사용합니다.
    예외가 발생하거나 툴 오류가 있어도 안전 기본값을 반환합니다.
    """
    ticker = state["ticker"]
    horizon = state["horizon"]
    news_task = state.get("news_task") or (
        f"Assess news-driven risk for {ticker} over {horizon}. "
        f"Disambiguate entity and extract events."
    )
    try:
        final_agent_state = news_agent.run(news_task)
        raw_steps = final_agent_state.get("results", {})
        domain = news_postprocess(ticker, raw_steps)

        has_score = (
            isinstance(domain, dict) and "domain_risk_score" in domain
        ) or hasattr(domain, "domain_risk_score")
        if not has_score:
            domain = _safe_default_result("news", "postprocess missing score")

    except Exception as e:
        domain = _safe_default_result("news", f"exception: {e}")
    return {"news_result": domain}


def run_filings(state: MetaState):
    """
    meta_plan에서 filing_task가 비어도 안전하게 기본값을 생성해 사용합니다.
    예외가 발생하거나 툴 오류가 있어도 안전 기본값을 반환합니다.
    """
    ticker = state["ticker"]
    horizon = state["horizon"]
    filing_task = state.get("filing_task") or (
        f"Assess filing-driven risk for {ticker} over {horizon}. "
        f"Extract accounting and legal signals."
    )
    try:
        final_agent_state = filings_agent.run(filing_task)
        raw_steps = final_agent_state.get("results", {})
        domain = filings_postprocess(ticker, raw_steps)

        has_score = (
            isinstance(domain, dict) and "domain_risk_score" in domain
        ) or hasattr(domain, "domain_risk_score")
        if not has_score:
            domain = _safe_default_result("filing", "postprocess missing score")

    except Exception as e:
        domain = _safe_default_result("filing", f"exception: {e}")
    return {"filing_result": domain}


def run_lstm(state: MetaState):
    """
    meta_plan에서 lstm_task가 비어도 안전하게 기본값을 생성해 사용합니다.
    예외가 발생하거나 툴 오류가 있어도 안전 기본값을 반환합니다.
    """
    ticker = state["ticker"]
    lstm_task = state.get("lstm_task") or (
        f"Assess lstm-anomaly-driven risk for {ticker}."
    )
    print("[DBG][run_lstm] enter. state keys:", list(state.keys()))
    print("[DBG][run_lstm] lstm_task:", lstm_task)
    try:
        final_agent_state = lstm_agent.run(lstm_task)
        # BaseReWOO 반환 상태 요약
        print("[DBG][run_lstm] final_agent_state keys:", list(final_agent_state.keys()))
        for k in ("steps", "results", "result"):
            v = final_agent_state.get(k)
            print(f"[DBG][run_lstm] final_agent_state[{k}] type:", type(v).__name__)
            if isinstance(v, dict):
                print(f"[DBG][run_lstm] final_agent_state[{k}] keys:", list(v.keys()))
            elif isinstance(v, list):
                print(f"[DBG][run_lstm] final_agent_state[{k}] len:", len(v))
 
        raw_steps = final_agent_state.get("results", {})
        domain = lstm_postprocess(ticker, raw_steps)  # ← DomainResult (pydantic) 를 존중
        # 스코어 유무만 확인 (dict or pydantic 둘 다 허용)
        has_score = (
            (isinstance(domain, dict) and "domain_risk_score" in domain) or
            hasattr(domain, "domain_risk_score")
        )
        if not has_score:
            domain = _safe_default_result("lstm_anomaly", "postprocess missing score")
    except Exception as e:
        domain = _safe_default_result("lstm_anomaly", f"exception: {e}")
    return {"lstm_result": domain}


def final_solve(state: MetaState) -> Dict[str, Any]:
    """
    news/filings 노드가 비활성(주석)이어도 안전하게 동작하도록 기본값으로 대체합니다.
    """
    news_result   = state.get("news_result",   _safe_default_result("news", "skipped"))
    filing_result = state.get("filing_result", _safe_default_result("filing", "skipped"))
    lstm_result   = state.get("lstm_result",   _safe_default_result("lstm_anomaly", "skipped"))

    report = fuse(
        news_result,
        filing_result,
        lstm_result,
        state["ticker"],
        state["horizon"],
    )
    return {"final_report": report.model_dump()}


# ---- Build Meta Graph ----

def build_meta_graph():
    g = StateGraph(MetaState)
    g.add_node("meta_plan", meta_plan)
    g.add_node("lstm", run_lstm)
    # 필요 시 아래 두 줄의 주석을 해제하면 병렬 실행됩니다.
    g.add_node("news", run_news)
    g.add_node("filings", run_filings)
    g.add_node("final", final_solve)

    g.add_edge(START, "meta_plan")
    # 병렬 실행: meta_plan -> (news, filings, lstm)
    g.add_edge("meta_plan", "lstm")
    g.add_edge("meta_plan", "news")
    g.add_edge("meta_plan", "filings")

    # 최종 수집
    g.add_edge("lstm", "final")
    g.add_edge("news", "final")
    g.add_edge("filings", "final")

    g.add_edge("final", END)
    return g.compile()
