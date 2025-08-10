from typing import List, Dict, TypedDict, Any

class ReWOOState(TypedDict):
    task: str
    plan_string: str
    steps: List
    results: Dict[str, str]
    result: str

class MetaState(TypedDict):
    ticker: str
    horizon: str
    task: str
    news_result: Any
    filing_result: Any
    final_report: Any