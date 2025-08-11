# mcp/tools/stock_info/stock_info_tool.py

from fastmcp import FastMCP
from .stock_info_service import individual_stock_trend as fetch_stock_trend


def register(mcp: FastMCP) -> None:
    """
    개별 종목 시세 추이 분석 MCP 도구를 서버 인스턴스에 등록한다.
    server에서 create_app() 후 register(mcp) 호출.
    """

    @mcp.tool(
        name="individual_stock_trend",
        description=(
            "KRX '개별종목 시세 추이'에서 지정한 종료일(YYYYMMDD)까지 데이터를 내려받아 "
            "최근 5일과 전체 기간의 지표·변화를 분석해 JSON으로 반환합니다. "
            "예: {'stock_name': '삼성전자', 'target_date': '20250810'}"
        ),
    )
    def individual_stock_trend(stock_name: str, target_date: str) -> dict:
        """
        Args:
            stock_name (str): 조회할 종목명(정확한 한글 종목명 권장)
            target_date (str): 조회 종료일, 'YYYYMMDD' 형식 (예: '20250810')

        Returns:
            dict: individual_stock_trend(stock_name, target_date) 결과(JSON 직렬화 가능 딕셔너리).
        """
        s = (stock_name or "").strip()
        if not s:
            raise ValueError("stock_name은 비어있지 않은 문자열이어야 합니다.")
        t = (target_date or "").strip()
        if len(t) != 8 or not t.isdigit():
            raise ValueError("target_date는 'YYYYMMDD' 형식의 문자열이어야 합니다.")

        return fetch_stock_trend(s, t)
