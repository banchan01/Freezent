from fastmcp import FastMCP
from .lockup_service import crawl_lockup_info, lockup_info_to_json
import pandas as pd


def register(mcp: FastMCP) -> None:
    """
    보호예수 관련 MCP 도구들을 서버 인스턴스에 등록한다.
    server에서 create_app() 후 register(mcp) 호출.
    """

    @mcp.tool(
        name="crawl_lockup_info",
        description=(
            "종목명을 입력하면 Seibro에서 보호예수(의무보유) 현황을 크롤링해 "
            "JSON으로 반환합니다. 예: {'stock_name': '아이지넷'}"
        ),
    )
    def crawl_lockup_info_tool(stock_name: str) -> dict:
        """
        Args:
            stock_name (str): 조회할 종목명(정확한 한글 종목명 권장)

        Returns:
            dict: lockup_info_to_json(df) 결과(JSON 직렬화 가능 딕셔너리).
                  크롤링 실패 시 RuntimeError 발생.
                  데이터가 없는 경우, 값이 0 또는 비어있는 정상 JSON 반환.
        """
        df = crawl_lockup_info(stock_name)

        # 크롤링/파싱 자체 실패 (네트워크, 웹사이트 구조 변경 등)
        if df is None:
            raise RuntimeError(f"'{stock_name}'의 보호예수 정보 크롤링 또는 표 파싱에 실패했습니다.")

        # 데이터가 없는 경우(빈 DataFrame)에도 정상 처리
        return lockup_info_to_json(df)
