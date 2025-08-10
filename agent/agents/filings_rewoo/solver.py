from common.schemas import DomainResult, DomainEvent, Evidence
from typing import List, Dict, Any

def filings_postprocess(ticker: str, raw_steps: Dict[str, str]) -> DomainResult:
    # TODO: parse filings outputs and compute domain_risk_score
    events: List[DomainEvent] = []
    ev = Evidence(source="filing", title=None, url=None, snippet=str(raw_steps), confidence=0.7)
    events.append(DomainEvent(ticker=ticker, event_type="accounting_issue", severity=0.5, confidence=0.7, evidence=[ev]))
    return DomainResult(domain="filing", ticker=ticker, events=events, domain_risk_score=0.6, rationale="heuristic v0")