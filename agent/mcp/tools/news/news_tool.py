# tools/news/news_tool.py

from typing import Any, Dict, List, Tuple
from fastmcp import FastMCP
from .news_service import crawl_articles_by_stock, analyze_articles


def register(mcp: FastMCP) -> None:
    """
    뉴스 크롤링 → 기사별 GPT 분석(analyze_articles만 사용) 결과를 반환하는 MCP 도구를 등록한다.
    server에서 create_app() 후 register(mcp) 호출.
    """

    @mcp.tool(
        name="analyze_stock_news",
        description=(
            "종목명을 받아 인포스탁데일리에서 관련 기사를 크롤링하고, 각 기사 본문을 analyze_articles로 "
            "GPT 분석하여 결과를 반환합니다."
            "예: {'stock_name': '삼성전자', 'max_articles': 5, 'model': 'gpt-4.1', 'concurrency': 3}"
        ),
    )
    async def analyze_stock_news_tool(
        stock_name: str,
        max_articles: int = 10,
        model: str = "gpt-4.1",
        concurrency: int = 5,
    ) -> Dict[str, Any]:
        """
        Args:
            stock_name (str): 조회할 종목명(정확한 한글 종목명 권장)
            max_articles (int): 수집할 최대 기사 수(기본 10)
            model (str): OpenAI 모델명(기본 'gpt-4.1')
            concurrency (int): analyze_articles 동시 분석 개수(기본 5)

        Returns:
            dict: {"기사목록": [ {종목명, 제목, 날짜, 본문, 링크, 분석결과}, ... ]}
        """
        s = (stock_name or "").strip()
        if not s:
            raise ValueError("stock_name은 비어있지 않은 문자열이어야 합니다.")
        if not isinstance(max_articles, int) or max_articles <= 0:
            raise ValueError("max_articles는 1 이상의 정수여야 합니다.")
        if not isinstance(concurrency, int) or concurrency <= 0:
            raise ValueError("concurrency는 1 이상의 정수여야 합니다.")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model은 비어있지 않은 문자열이어야 합니다.")

        # 1) 크롤링
        articles: List[Dict[str, Any]] = crawl_articles_by_stock(
            s, max_articles=max_articles
        )
        if not articles:
            return {"기사목록": []}

        # 2) analyze_articles 호출을 위한 입력 구성
        items = [
            {"stock_name": s, "article_content": a.get("본문", "")} for a in articles
        ]

        # 3) analyze_articles로 병렬 분석
        analyzed: List[Tuple[Dict[str, str], Dict[str, Any]]] = await analyze_articles(
            items, concurrency=concurrency, model=model
        )

        # 4) 기사에 분석결과 부착
        for i, (_, res) in enumerate(analyzed):
            articles[i]["분석결과"] = res

        return {"기사목록": articles}
