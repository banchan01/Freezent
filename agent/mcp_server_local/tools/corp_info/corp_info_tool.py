# mcp/tools/corp_info/corp_info_tool.py
from fastmcp import FastMCP
from .corp_info_service import find_corp_info_by_name

def register(mcp: FastMCP) -> None:
    """
    회사 이름으로 회사 코드를 조회하는 MCP 도구를 등록합니다.
    """

    @mcp.tool(
        name="get_corp_info",
        description=(
            "Takes a company name (stock_name) and returns its corporate information, "
            "including the corp_code, from the local CORPCODE.xml file. "
            "This is a necessary first step for any other filings-related tools."
            "Example: {'stock_name': '삼성전자'}"
        ),
    )
    def get_corp_info_tool(stock_name: str) -> dict:
        """
        Args:
            stock_name (str): The exact, full company name to look up.

        Returns:
            dict: A dictionary containing 'corp_code', 'corp_name', and 'stock_code', or an 'error' key if not found.
        """
        if not isinstance(stock_name, str) or not stock_name.strip():
            raise ValueError("stock_name must be a non-empty string.")

        return find_corp_info_by_name(stock_name)
