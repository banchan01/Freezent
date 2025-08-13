from fastmcp import FastMCP
from .paid_in_capital_increase_service import get_paid_in_analysis

def register(mcp: FastMCP) -> None:
    """
    제3자 배정 유상증자 분석 도구 등록
    """

    @mcp.tool(
        name="analyze_paid_in_capital_increase",
        description=(
            "기업의 corp_code를 받아 DART에서 유상증자 내역을 조회한 뒤, "
            "OpenAI Chat 모델을 사용해 투자 판단과 주가조작 위험을 분석합니다. "
            "Example: {'corp_code': '00126380'}"
        ),
    )
    def analyze_paid_in_capital_increase_tool(corp_code: str) -> dict:
        if not isinstance(corp_code, str) or not corp_code.strip() or not corp_code.isdigit():
            raise ValueError("corp_code must be a non-empty string of digits.")
        return get_paid_in_analysis(corp_code.strip())
