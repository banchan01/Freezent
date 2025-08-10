from typing import Literal, Dict, Any

# Decide parallel vs sequential, and craft domain-specific tasks

def make_domain_tasks(ticker: str, horizon: str) -> Dict[str, str]:
    news_task = f"Assess news-driven risk for {ticker} over {horizon}. Return disambiguated events."
    filing_task = f"Assess filing-driven risk for {ticker} over {horizon}. Extract accounting and legal signals."
    return {"news_task": news_task, "filing_task": filing_task}