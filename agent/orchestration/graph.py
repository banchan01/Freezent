from langgraph.graph import StateGraph, START, END
from common.state import MetaState
from orchestration.meta_planner import make_domain_tasks
from orchestration.fusion_solver import fuse

from agents.base_rewoo import BaseReWOO
from agents.news_rewoo.planner import NEWS_PLANNER_PROMPT
from agents.news_rewoo.workers import NewsWorkers
from agents.news_rewoo.solver import news_postprocess

from agents.filings_rewoo.planner import FILINGS_PLANNER_PROMPT
from agents.filings_rewoo.workers import FilingsWorkers
from agents.filings_rewoo.solver import filings_postprocess

# ---- Concrete ReWOO subclasses to register domain tools ----

class NewsReWOO(BaseReWOO):
    def register_tools(self):
        workers = NewsWorkers()
        self.tools = {
            "Google": workers.google,
            "LLM": workers.llm,
        }

class FilingsReWOO(BaseReWOO):
    def register_tools(self):
        workers = FilingsWorkers()
        self.tools = {
            "Filings": lambda q: workers.filings.search_filings(q, ""),
            "LLM": workers.llm,
        }

news_agent = NewsReWOO("news", NEWS_PLANNER_PROMPT)
filings_agent = FilingsReWOO("filing", FILINGS_PLANNER_PROMPT)

# ---- Meta Graph Nodes ----

def meta_plan(state: MetaState):
    tasks = make_domain_tasks(state["ticker"], state["horizon"])
    return {"task": f"Risk assessment for {state['ticker']} over {state['horizon']}", **tasks}

def run_news(state: MetaState):
    out = news_agent.run(state["news_task"])  # stream result dict
    # Convert to DomainResult
    domain = news_postprocess(state["ticker"], out.get("tool", {}).get("results", {})) if out else None
    return {"news_result": domain}

def run_filings(state: MetaState):
    out = filings_agent.run(state["filing_task"])  # stream result dict
    domain = filings_postprocess(state["ticker"], out.get("tool", {}).get("results", {})) if out else None
    return {"filing_result": domain}

def final_solve(state: MetaState):
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
    # Run two domains sequentially. You can parallelize with separate orchestrator if desired.
    g.add_edge("meta_plan", "news")
    g.add_edge("news", "filings")
    g.add_edge("filings", "final")
    g.add_edge("final", END)
    return g.compile()