from __future__ import annotations
from common.schemas import DomainResult, FinalRiskReport, Evidence

# Simple weighted fusion (replace with your policy)

def fuse(news: DomainResult, filing: DomainResult, lstm: DomainResult, ticker: str, horizon: str) -> FinalRiskReport:
    w_news, w_filing, w_lstm = 0.4, 0.4, 0.2
    final_score = w_news * news.domain_risk_score + w_filing * filing.domain_risk_score + w_lstm * lstm.domain_risk_score

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
        
    if lstm.events:
        for event in lstm.events:
            citations.extend(event.evidence)
    if lstm.rationale:
        citations.append(Evidence(source="llm", title="LSTM 요약", snippet=lstm.rationale))

    return FinalRiskReport(
        ticker=ticker,
        horizon=horizon,
        news_score=news.domain_risk_score,
        filing_score=filing.domain_risk_score,
        lstm_score=lstm.domain_risk_score,
        final_score=final_score,
        details={"weights": {"news": w_news, "filing": w_filing, "lstm": w_lstm}},
        citations=citations,
    )

def fusion_solver_node(state):
    news_result = state["news_result"]
    filing_result = state["filing_result"]
    lstm_result = state["lstm_result"]
    ticker = state["ticker"]
    horizon = state["horizon"]
    final_report = fuse(news_result, filing_result, lstm_result, ticker, horizon)
    return {"final_report": final_report.model_dump()}
