# agents/news_rewoo/workers.py
from __future__ import annotations

from tools.news_search import NewsSearchTool
from tools.text_llm import LLMTool


class NewsWorkers:
    """
    - Google: Tavily 기반 뉴스 검색(항상 JSON 문자열 반환)
    - LLM: 요약/추출(실패 시 안전한 안내 문자열 반환)
    """
    def __init__(self):
        self.google = NewsSearchTool(max_results=5)
        self.llm = LLMTool()
