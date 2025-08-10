from common.schemas import DomainResult, FinalRiskReport, Evidence

# Simple weighted fusion (replace with your policy)

def fuse(news: DomainResult, filing: DomainResult, ticker: str, horizon: str) -> FinalRiskReport:
    w_news, w_filing = 0.4, 0.6
    final = w_news * news.domain_risk_score + w_filing * filing.domain_risk_score
    citations = []
    for evs in [news.events, filing.events]:
        for e in evs:
            citations.extend(e.evidence)
    return FinalRiskReport(
        ticker=ticker,
        horizon=horizon,
        news_score=news.domain_risk_score,
        filing_score=filing.domain_risk_score,
        final_score=final,
        details={"weights": {"news": w_news, "filing": w_filing}},
        citations=citations,
    )