from pydantic import BaseModel
from typing import List, Dict, Any, Optional


# ===== 뉴스 크롤링 관련 형식 =====
class StockRequest(BaseModel):
    """종목 크롤링 요청 형식"""

    stock_name: str
    max_articles: int = 10


class CrawlResponse(BaseModel):
    """크롤링 응답 형식"""

    articles: List[Dict[str, Any]]
    total_count: int


# ===== 새로운 분석 API 형식 =====
class StockAnalyzeRequest(BaseModel):
    """종목별 뉴스 분석 요청 형식"""

    stock_name: str
    max_articles: int = 10
    concurrency: int = 3


class StockAnalyzeResponse(BaseModel):
    """종목별 뉴스 분석 응답 형식"""

    stock_name: str
    count: int
    results: List[Dict[str, Any]]


# ===== 통합 분석 관련 형식 =====
class IntegratedRequest(BaseModel):
    """통합 분석 요청 형식"""

    stock_name: str
    max_articles: int = 10


class IntegratedResponse(BaseModel):
    """통합 분석 응답 형식"""

    summary: Dict[str, Any]
