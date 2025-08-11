# agents/news_rewoo/solver.py
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from common.schemas import DomainResult, DomainEvent, Evidence


def _parse_date(date_str: str | None) -> datetime | None:
    """'YY.MM.DD' 형식의 문자열을 datetime으로 변환 시도"""
    if not date_str:
        return None
    try:
        # YY.MM.DD 형식을 datetime 객체로 변환
        return datetime.strptime(f"20{date_str}", "%Y.%m.%d")
    except (ValueError, TypeError):
        return None


def news_postprocess(ticker: str, raw_steps: Dict[str, str]) -> DomainResult:
    """
    MCP 'analyze_stock_news' 도구의 JSON 출력물을 파싱하여 DomainResult를 생성합니다.
    - 각 기사 항목을 Evidence로 변환합니다.
    - 각 기사의 '분석결과'를 사용하여 DomainEvent를 생성합니다.
    - 전체 위험 점수는 모든 이벤트의 심각도(severity) 중 최대값으로 결정합니다.
    """
    all_events: List[DomainEvent] = []
    all_evidences: List[Evidence] = []
    max_severity = 0.0

    # BaseReWOO의 결과는 '#E' 단계에 JSON 문자열로 저장됩니다.
    payload_str = (raw_steps or {}).get("#E", "{}")

    try:
        data = json.loads(payload_str)
        articles = data.get("기사목록", []) if isinstance(data, dict) else []

        for article in articles:
            analysis = article.get("분석결과", {})
            
            # 1. 각 기사에 대한 Evidence 생성
            evidence = Evidence(
                source="news",
                title=article.get("제목"),
                url=article.get("링크"),
                snippet=(article.get("본문") or "")[:500],
                published_at=_parse_date(article.get("날짜")),
                raw=article,
                confidence=analysis.get("신뢰도", 0.7) if isinstance(analysis, dict) else 0.5,
            )
            all_evidences.append(evidence)

            # 2. 각 기사의 분석 결과로 DomainEvent 생성
            # (분석결과 필드에 is_negative_event, severity 등이 있다고 가정)
            if isinstance(analysis, dict) and analysis.get("is_negative_event"):
                severity = float(analysis.get("severity", 0.5))
                event = DomainEvent(
                    ticker=ticker,
                    event_type=analysis.get("event_type", "unknown_news"),
                    severity=severity,
                    confidence=analysis.get("confidence", 0.6),
                    timestamp=_parse_date(article.get("날짜")) or datetime.utcnow(),
                    evidence=[evidence],  # 현재 기사를 증거로 연결
                    summary=analysis.get("summary", "요약 정보 없음."),
                )
                all_events.append(event)
                if severity > max_severity:
                    max_severity = severity

    except (json.JSONDecodeError, TypeError) as e:
        return DomainResult(
            domain="news",
            ticker=ticker,
            events=[],
            domain_risk_score=0.1,
            rationale=f"뉴스 분석 도구 결과 파싱 실패: {e}",
        )

    # 부정적 이벤트가 없으면, 중립 이벤트를 생성
    if not all_events:
        all_events.append(
            DomainEvent(
                ticker=ticker,
                event_type="no_significant_news",
                severity=0.1,
                confidence=0.8,
                timestamp=datetime.utcnow(),
                evidence=all_evidences, # 찾은 모든 기사를 증거로 첨부
                summary="분석된 기사에서 특별한 부정적 이벤트가 발견되지 않았습니다.",
            )
        )
        max_severity = 0.1

    return DomainResult(
        domain="news",
        ticker=ticker,
        events=all_events,
        domain_risk_score=max_severity,
        rationale="위험 점수는 MCP 뉴스 분석 결과의 최대 심각도입니다.",
    )
