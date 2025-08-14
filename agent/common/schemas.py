# common/schemas.py
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


EventType = Literal[
    "management_change",
    "litigation",
    "financing",
    "accounting_issue",
    "macro_news",
    "product_issue",
    "supply_chain",
    "regulatory",
    "price_anomaly",
    "unknown_news",
    "no_significant_news",  # Explicitly handle the case of no significant news
]


class Evidence(BaseModel):
    source: Literal["news", "filing", "llm", "lstm_model"]
    title: Optional[str] = None
    url: Optional[HttpUrl] = None
    snippet: Optional[str] = None
    published_at: Optional[datetime] = None
    raw: Optional[Dict[str, Any]] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class DomainEvent(BaseModel):
    ticker: str
    event_type: EventType
    severity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: Optional[datetime] = None
    evidence: List[Evidence] = []
    

class DomainResult(BaseModel):
    domain: Literal["news", "filing", "lstm_anomaly"]
    ticker: str
    events: List[DomainEvent] = []
    domain_risk_score: float = Field(ge=0.0, le=1.0)
    rationale: str
    llm_report: Optional[str] = None

class FinalRiskReport(BaseModel):
    ticker: str
    horizon: Optional[str] = None
    news_score: float
    filing_score: float
    lstm_score: float
    final_score: float
    method: str = "weighted_fusion:v1"
    details: Dict[str, Any] = {}
    citations: List[Evidence] = []
    llm_report: Optional[str] = None
