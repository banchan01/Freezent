from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime

EventType = Literal[
    "management_change", "litigation", "financing", "accounting_issue",
    "macro_news", "product_issue", "supply_chain", "regulatory",
]

class Evidence(BaseModel):
    source: Literal["news", "filing", "llm"]
    title: Optional[str] = None
    url: Optional[HttpUrl] = None
    snippet: Optional[str] = None
    published_at: Optional[datetime] = None
    raw: Optional[Dict[str, Any]] = None
    confidence: float = 0.5

class DomainEvent(BaseModel):
    ticker: str
    event_type: EventType
    severity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: Optional[datetime] = None
    evidence: List[Evidence] = []

class DomainResult(BaseModel):
    domain: Literal["news", "filing"]
    ticker: str
    events: List[DomainEvent]
    domain_risk_score: float = Field(ge=0.0, le=1.0)
    rationale: str

class FinalRiskReport(BaseModel):
    ticker: str
    horizon: Optional[str] = None
    news_score: float
    filing_score: float
    final_score: float
    method: str = "weighted_fusion:v1"
    details: Dict[str, Any] = {}
    citations: List[Evidence] = []