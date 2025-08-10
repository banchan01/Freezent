# tools/biz_perf/biz_perf_tool.py

import json
from typing import Any
from fastmcp import FastMCP

from .biz_perf_service import get_biz_performance_tentative


def register(mcp: FastMCP) -> None:
    """
    사업(영업) 잠정실적(공정공시) 조회 MCP 도구를 등록한다.
    server에서 create_app() 후 register(mcp) 호출.
    """

    @mcp.tool(
        name="get_biz_performance_tentative",
        description=(
            "회사명(종목명)을 입력하면 DART에서 '영업(잠정)실적(공정공시)' 공시(I/I004)를 조회해 "
            "뷰어 페이지의 핵심 표를 파싱하여 JSON으로 반환합니다. \n"
            "- 입력: {'corp_name': '삼성바이오로직스'} (정확한 회사명 권장)\n"
            "- 처리: DART list.json을 날짜 내림차순으로 검색 → 각 공시의 뷰어(iframe) HTML 로드 → "
            "표(id='XFormD1_Form0_RepeatTable0')를 추출/정제\n"
            "- 출력: 공시별 객체 리스트. 각 객체는 다음 필드를 가짐:\n"
            "  {\n"
            "    'title': '<회사명>/<연결/별도>영업(잠정)실적(공정공시)/(YYYY.MM.DD)...',\n"
            "    'data': [\n"
            "      {\n"
            "        '구분': '매출액|영업이익|법인세비용차감전계속사업이익|당기순이익|...',\n"
            "        '세부구분': '당해실적' 등,\n"
            "        '당기실적': '숫자문자열',\n"
            "        '전기실적': '숫자문자열',\n"
            "        '전기대비증감율(%)': '+3.33' 또는 '-0.64%' 등 원문 표기,\n"
            "        '전년동기실적': '숫자문자열',\n"
            "        '전년동기대비증감율(%)': '원문 표기'\n"
            "      }, ...\n"
            "    ]\n"
            "  }\n"
            "- 여러 분기/월의 공시가 있으면 여러 개의 객체가 배열로 반환됩니다.\n"
            "- 주의: DART/뷰어 구조 변경이나 로딩 실패 시 빈 배열 또는 일부 항목 누락이 발생할 수 있습니다."
        ),
    )
    async def get_biz_performance_tentative_tool(corp_name: str) -> Any:
        """
        Args:
            corp_name (str): 회사명(종목명). 예: '삼성바이오로직스'
        Returns:
            list | dict | str: 서비스 함수가 반환한 JSON 문자열을 가능한 경우 파싱하여 반환.
                               파싱 실패 시 원본 문자열을 그대로 돌려줍니다.
        """
        raw = await get_biz_performance_tentative(corp_name)
        try:
            return json.loads(raw)
        except Exception:
            return raw
