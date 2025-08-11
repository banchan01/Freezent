# mcp/tools/floating_stock/floating_stock_tool.py
from fastmcp import FastMCP
from .floating_stock_service import calculate_floating_stock_ratio

def register(mcp: FastMCP) -> None:
    """
    유동주식비율 분석 MCP 도구를 서버 인스턴스에 등록한다.
    """

    @mcp.tool(
        name="get_floating_stock_ratio",
        description=(
            "Takes a company's unique corporate code (corp_code) and calculates its floating stock ratio "
            "based on the latest available public filings. "
            "Example: {'corp_code': '00126380'}"
        ),
    )
    def get_floating_stock_ratio_tool(corp_code: str) -> dict:
        """
        Args:
            corp_code (str): The unique corporate code from DART.

        Returns:
            dict: A dictionary with the floating stock ratio and other metrics.
        """
        if not isinstance(corp_code, str) or not corp_code.strip() or not corp_code.isdigit():
            raise ValueError("corp_code must be a non-empty string of digits.")

        # The service function is async, but MCP tool can be sync
        # FastMCP will handle the event loop.
        return calculate_floating_stock_ratio(corp_code)