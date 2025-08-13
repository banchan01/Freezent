from __future__ import annotations
from common.schemas import DomainResult, FinalRiskReport, Evidence

# Simple weighted fusion (replace with your policy)

def fuse(news: DomainResult, filing: DomainResult, ticker: str, horizon: str) -> FinalRiskReport:
    w_news, w_filing = 0.4, 0.6
    final_score = w_news * news.domain_risk_score + w_filing * filing.domain_risk_score

    # 각 도메인의 Evidence와 요약(rationale)을 Citations로 구성
    citations = []
    if news.events:
        for event in news.events:
            citations.extend(event.evidence)
    if news.rationale:


        citations.append(Evidence(source="llm", title="뉴스 요약", snippet=news.rationale))

    if filing.events:
        for event in filing.events:
            citations.extend(event.evidence)
    if filing.rationale:
        citations.append(Evidence(source="llm", title="공시 요약", snippet=filing.rationale))

    return FinalRiskReport(
        ticker=ticker,
        horizon=horizon,
        news_score=news.domain_risk_score,
        filing_score=filing.domain_risk_score,
        final_score=final_score,
        details={"weights": {"news": w_news, "filing": w_filing}},
        citations=citations,
    )

def fusion_solver_node(state):
    news_result = state["news_result"]
    filing_result = state["filing_result"]
    ticker = state["ticker"]
    horizon = state["horizon"]
    final_report = fuse(news_result, filing_result, ticker, horizon)
    return {"final_report": final_report.model_dump()}