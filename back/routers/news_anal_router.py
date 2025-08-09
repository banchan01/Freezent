from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import asyncio

from services.news_crawl_service import crawl_articles_by_stock
from services.news_analyze_service import analyze_articles, analyze_article
from services.news_integrate_service import aggregate_without_preprocessing
from format.news_anal_format import (
    StockRequest,
    CrawlResponse,
    StockAnalyzeRequest,
    StockAnalyzeResponse,
    IntegratedRequest,
    IntegratedResponse,
)

router = APIRouter(prefix="/news")


# ===== 1. 크롤링 API =====
@router.post("/crawl", response_model=CrawlResponse)
async def crawl_articles(request: StockRequest):
    """
    특정 종목에 대한 뉴스 기사 10개개를 크롤링합니다.
    """
    try:
        articles = crawl_articles_by_stock(
            request.stock_name, max_articles=request.max_articles
        )

        return CrawlResponse(articles=articles, total_count=len(articles))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"크롤링 실패: {str(e)}")


# ===== 2. 종목별 뉴스 분석 API =====
@router.post("/analyze", response_model=StockAnalyzeResponse)
async def analyze_stock_news(request: StockAnalyzeRequest):
    """
    주어진 종목에 대해 뉴스 크롤링 후, 병렬 GPT 분석 결과를 반환
    """
    try:
        # 1) 뉴스 크롤링
        articles = crawl_articles_by_stock(
            request.stock_name, max_articles=request.max_articles
        )
        if not articles:
            return StockAnalyzeResponse(
                stock_name=request.stock_name, count=0, results=[]
            )

        # 2) 병렬 분석 입력 데이터 구성
        items: List[Dict[str, str]] = [
            {"stock_name": a["종목명"], "article_content": a["본문"], "id": a["링크"]}
            for a in articles
            if a.get("본문")
        ]
        if not items:
            return StockAnalyzeResponse(
                stock_name=request.stock_name, count=0, results=[]
            )

        # 3) GPT 병렬 분석 실행
        analyzed: List[Tuple[Dict[str, str], Dict[str, Any]]] = await analyze_articles(
            items, concurrency=request.concurrency
        )

        # 4) 기사 메타데이터 + 분석결과 합치기
        results: List[Dict[str, Any]] = []
        for item, analysis in analyzed:
            orig = next((a for a in articles if a["링크"] == item["id"]), None)
            if orig:
                results.append({**orig, "분석결과": analysis})

        return StockAnalyzeResponse(
            stock_name=request.stock_name, count=len(results), results=results
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 실패: {e}")


# ===== 3. 통합 분석 API =====
@router.post("/integrate", response_model=IntegratedResponse)
async def integrate_analysis(request: IntegratedRequest):
    """
    전체 파이프라인을 실행합니다:
    1. 크롤링 → 2. GPT 분석 → 3. 결과 종합
    """
    try:
        # 1단계: 크롤링
        articles = crawl_articles_by_stock(
            request.stock_name, max_articles=request.max_articles
        )

        if not articles:
            raise HTTPException(
                status_code=404,
                detail=f"'{request.stock_name}' 관련 기사를 찾을 수 없습니다.",
            )

        # 2단계: GPT 분석용 입력 데이터 준비
        items = [
            {
                "stock_name": art["종목명"],
                "article_content": art["본문"],
                "id": art["링크"],
            }
            for art in articles
            if art.get("본문")
        ]

        # 3단계: GPT 분석
        results = await analyze_articles(items, concurrency=5)

        # 4단계: 분석 결과와 원본 기사 결합
        final_results = []
        for item, analysis in results:
            orig = next((a for a in articles if a["링크"] == item["id"]), {})
            final_results.append({**orig, "분석결과": analysis})

        # 5단계: 결과 종합
        integrated_result = aggregate_without_preprocessing(final_results)

        return IntegratedResponse(summary=integrated_result["종합 판단"])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통합 분석 실패: {str(e)}")
