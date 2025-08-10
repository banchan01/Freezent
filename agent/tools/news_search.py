# tools/news_search.py
from __future__ import annotations

import json
import os
import traceback
from typing import Any, Dict

from langchain_tavily import TavilySearch

DEBUG = os.getenv("DEBUG", "false").lower() == "true"


def _dbg(msg: str, payload: Dict[str, Any] | None = None):
    if DEBUG:
        print(f"[news_search] {msg}")
        if payload is not None:
            try:
                print(json.dumps(payload, ensure_ascii=False, indent=2)[:1200])
            except Exception:
                print(str(payload)[:1200])


class NewsSearchTool:
    """
    Tavily를 감싼 안전 래퍼:
      - 항상 JSON 문자열(str)을 반환하므로 ReWOO가 그대로 evidence로 사용 가능
      - 실패해도 {"results": []} 형태로 fallback
      - DEBUG=true면 간단한 로그 출력
    """

    def __init__(self, max_results: int = 5):
        self.search = TavilySearch(max_results=max_results)

    def __call__(self, query: str) -> str:
        try:
            _dbg("invoke", {"query": query})
            res = self.search.invoke(query)  # LC tool -> list[dict] or dict
            # 결과를 표준 구조로 정리
            payload = {
                "ok": True,
                "query": query,
                "results": res if isinstance(res, list) else [res],
            }
            _dbg("success", {"n_results": len(payload["results"])})
            return json.dumps(payload, ensure_ascii=False)
        except Exception as e:
            _dbg("error", {"err": str(e), "trace": traceback.format_exc()})
            fallback = {
                "ok": False,
                "query": query,
                "results": [],
                "error": str(e),
            }
            # 실패해도 문자열 JSON 반환
            return json.dumps(fallback, ensure_ascii=False)
