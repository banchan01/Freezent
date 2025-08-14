# mcp/tools/lockup/lockup_tool.py
from fastmcp import FastMCP
from .lockup_service import crawl_lockup_info, lockup_info_to_json
import pandas as pd

def register(mcp: FastMCP) -> None:
    """
    보호예수 관련 MCP 도구 등록
    """
    @mcp.tool(
        name="crawl_lockup_info",
        description="종목명을 입력하면 Seibro에서 보호예수(의무보유) 현황을 크롤링해 JSON으로 반환합니다. 예: {'stock_name': '삼성바이오로직스'}",
    )
    async def crawl_lockup_info_tool(stock_name: str) -> dict:
        """
        Args:
            stock_name: 정확한 한글 종목명 권장
        Returns:
            dict(JSON): 실패 시에도 예외를 던지지 않고 error/note 필드를 포함한 JSON을 반환
        """
        df = crawl_lockup_info(stock_name)

        # 크롤링 자체 실패
        if df is None:
            return {
                "domain": "lockup_info",
                "stock_name": stock_name,
                "data": [],
                "error": "크롤링 또는 표 파싱 실패",
            }

        # 데이터 없음(빈 DF)도 정상 응답
        if isinstance(df, pd.DataFrame) and df.empty:
            return {
                "domain": "lockup_info",
                "stock_name": stock_name,
                "data": [],
                "note": "no data",
            }

        # 정상 DF → JSON
        payload = lockup_info_to_json(df)
        payload.update({"domain": "lockup_info", "stock_name": stock_name})
        return payload
