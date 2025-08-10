# orchestration/graph.py
from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from typing import Any, Dict

from common.state import MetaState
from orchestration.meta_planner import make_domain_tasks
from orchestration.fusion_solver import fuse

from agents.base_rewoo import BaseReWOO

# News domain
from agents.news_rewoo.planner import NEWS_PLANNER_PROMPT
from agents.news_rewoo.workers import NewsWorkers
from agents.news_rewoo.solver import news_postprocess

# Filings domain
from agents.filings_rewoo.planner import FILINGS_PLANNER_PROMPT
from agents.filings_rewoo.workers import FilingsWorkers
from agents.filings_rewoo.solver import filings_postprocess

# MCP client builder
from clients.mcp_client import build_mcp_client


# ---- Concrete ReWOO subclasses to register domain tools ----

class NewsReWOO(BaseReWOO):
    def register_tools(self):
        workers = NewsWorkers()
        self.tools = {
            "Google": workers.google,  # Tavily wrapper
            "LLM": workers.llm,
        }


class FilingsReWOO(BaseReWOO):
    """
    MCPClient를 내부에 주입(inject)하여 원격 MCP 도구를 등록합니다.
    """
    def __init__(self, name: str, planner_prompt: str):
        self._mcp = build_mcp_client()  # USE_MCP=false -> Mock, true -> HTTP
        super().__init__(name, planner_prompt)

    def register_tools(self):
        workers = FilingsWorkers(self._mcp)
        self.tools = {
            # MCP remote tools
            "ListPaidIn": workers.list_paid_in,
            "ListBizReports": workers.list_biz_reports,
            "PaidInAnalyze": workers.paid_in_analyze,
            "BizChangeAnalyze": workers.biz_change_analyze,
            # Local LLM is still available if needed
            "LLM": workers.llm,
        }


# ---- Instantiate domain agents ----
news_agent = NewsReWOO("news", NEWS_PLANNER_PROMPT)
filings_agent = FilingsReWOO("filing", FILINGS_PLANNER_PROMPT)


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
    out = news_agent.run(news_task)  # stream result dict
    raw_steps = {}
    if out and "tool" in out and "results" in out["tool"]:
        raw_steps = out["tool"]["results"]  # Dict[str, str]
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
    out = filings_agent.run(filing_task)
    raw_steps = {}
    if out and "tool" in out and "results" in out["tool"]:
        raw_steps = out["tool"]["results"]
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
    # 순차 실행(필요 시 병렬화 가능)
    g.add_edge("meta_plan", "news")
    g.add_edge("news", "filings")
    g.add_edge("filings", "final")
    g.add_edge("final", END)
    return g.compile()
