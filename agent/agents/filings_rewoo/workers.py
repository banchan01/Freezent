# agents/filings_rewoo/workers.py
from __future__ import annotations

from typing import Dict, Any
from clients.mcp_client import MCPClient
from tools.text_llm import LLMTool


def _parse_query_to_dict(query: str) -> Dict[str, Any]:
    """
    "k1=v1;k2=v2" 형태의 쿼리 문자열을 dict로 변환합니다.
    공백/빈 토큰은 무시합니다.
    """
    if not query:
        return {}
    parts = [kv for kv in query.split(";") if kv]
    out: Dict[str, Any] = {}
    for kv in parts:
        if "=" in kv:
            k, v = kv.split("=", 1)
            out[k.strip()] = v.strip()
    return out


class FilingsWorkers:
    """
    Filings 도메인의 Worker 모듈.
    - MCPClient를 통해 원격 MCP 서버의 도구(ListPaidIn, ListBizReports)를 호출합니다.
    - LLMTool은 여전히 로컬에서 사용 가능합니다(요약 후처리 등).
    """

    def __init__(self, mcp: MCPClient):
        self.llm = LLMTool()
        self.mcp = mcp

    # ---- MCP tool proxies ----
    def list_paid_in(self, query: str) -> Dict[str, Any]:
        """
        제3자배정유상증자(예시) 목록을 반환.
        query 예: "corp_code=00126380;bgn_de=20240101;end_de=20241231;pblntf_detail_ty=A003"
        """
        payload = _parse_query_to_dict(query)
        return self.mcp.invoke("ListPaidIn", **payload)

    def list_biz_reports(self, query: str) -> Dict[str, Any]:
        """
        영업/정기보고 등 목록을 반환.
        query 예: "corp_code=00126380;bgn_de=20240101;end_de=20241231;pblntf_ty=A"
        """
        payload = _parse_query_to_dict(query)
        return self.mcp.invoke("ListBizReports", **payload)

    def analyze_paid_in_capital_increase(self, query: str) -> Dict[str, Any]:
        """
        유상증자 관련 공시를 수집·요약·점수화(LLM-in-the-loop).
        query 예: "corp_code=00126380;bgn_de=20240101;end_de=20241231;prompt_version=v1"
        """
        payload = _parse_query_to_dict(query)
        return self.mcp.invoke("AnalyzePaidInCapitalIncrease", **payload)

    def analyze_business_change(self, query: str) -> Dict[str, Any]:
        """
        영업(매출/주요부문) 변화 관련 공시를 수집·요약·점수화(LLM-in-the-loop).
        query 예: "corp_code=00126380;bgn_de=20240101;end_de=20241231;prompt_version=v1"
        """
        payload = _parse_query_to_dict(query)
        return self.mcp.invoke("AnalyzeBusinessChange", **payload)
