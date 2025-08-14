# orchestration/meta_planner.py
from __future__ import annotations
from typing import Dict

def make_domain_tasks(ticker: str, horizon: str) -> Dict[str, str]:
    """
    세 도메인 작업 문자열을 반드시 생성해 반환합니다.
    """
    news_task = (
        f"Assess news-driven risk for {ticker} over {horizon}. "
        f"Disambiguate the entity and extract events (management_change, litigation, "
        f"product_issue, regulatory, macro_news). Return concise bullets."
    )
    filing_task = (
        f"Assess filing-driven risk for {ticker} over {horizon}. "
        f"Focus on audit opinions, lawsuits, financing (CB/BW), liquidity warnings, "
        f"significant contracts, and accounting issues. Return concise bullets."
    )
    lstm_task = (
        f"Detect price anomalies for {ticker} using the LSTM model."
    )
    return {"news_task": news_task, "filing_task": filing_task, "lstm_task": lstm_task}
