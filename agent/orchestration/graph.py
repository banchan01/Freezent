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


# ---- Instantiate domain agents using the generic BaseReWOO ----
# The domain-specific logic is now entirely in the planner prompts and postprocess functions.
news_agent = BaseReWOO("news", NEWS_PLANNER_PROMPT)
filings_agent = BaseReWOO("filing", FILINGS_PLANNER_PROMPT)


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
    """
    ticker = state["ticker"]
    horizon = state["horizon"]
    news_task = state.get("news_task") or (
        f"Assess news-driven risk for {ticker} over {horizon}. "
        f"Disambiguate entity and extract events."
    )
    # Run the agent and get the final state
    final_agent_state = news_agent.run(news_task)
    # Extract results from the 'tool' node's output
    raw_steps = final_agent_state.get("results", {})
    domain = news_postprocess(ticker, raw_steps)
    return {"news_result": domain}

def run_filings(state: MetaState):
    """
    meta_plan에서 filing_task가 비어도 안전하게 기본값을 생성해 사용합니다.
    """
    ticker = state["ticker"]
    horizon = state["horizon"]
    filing_task = state.get("filing_task") or (
        f"Assess filing-driven risk for {ticker} over {horizon}. "
        f"Extract accounting and legal signals."
    )
    # Run the agent and get the final state
    final_agent_state = filings_agent.run(filing_task)
    # Extract results from the 'tool' node's output
    raw_steps = final_agent_state.get("results", {})
    domain = filings_postprocess(ticker, raw_steps)
    return {"filing_result": domain}


def final_solve(state: MetaState) -> Dict[str, Any]:
    report = fuse(state["news_result"], state["filing_result"], state["ticker"], state["horizon"])
    return {"final_report": report.model_dump()}


# ---- Build Meta Graph ----

def build_meta_graph():
    g = StateGraph(MetaState)
    g.add_node("meta_plan", meta_plan)
    g.add_node("news", run_news)
    g.add_node("filings", run_filings)
    g.add_node("final", final_solve)

    g.add_edge(START, "meta_plan")
    # news, filings 병렬 실행
    g.add_edge("meta_plan", "news")
    g.add_edge("meta_plan", "filings")
    g.add_edge("news", "final")
    g.add_edge("filings", "final")
    g.add_edge("final", END)
    return g.compile()