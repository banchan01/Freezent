from common.schemas import DomainResult, DomainEvent, Evidence
from typing import List, Dict, Any

# Convert raw tool outputs -> structured DomainResult

def news_postprocess(ticker: str, raw_steps: Dict[str, str]) -> DomainResult:
    # TODO: parse tool outputs and compute domain_risk_score
    events: List[DomainEvent] = []
    ev = Evidence(source="news", title=None, url=None, snippet=str(raw_steps), confidence=0.5)
    events.append(DomainEvent(ticker=ticker, event_type="macro_news", severity=0.3, confidence=0.6, evidence=[ev]))
    return DomainResult(domain="news", ticker=ticker, events=events, domain_risk_score=0.4, rationale="heuristic v0")