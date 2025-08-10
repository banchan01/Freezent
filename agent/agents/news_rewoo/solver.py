# agents/news_rewoo/solver.py
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from common.schemas import DomainResult, DomainEvent, Evidence


_NEG_KEYWORDS = [
    "소송", "기소", "검찰", "규제", "제재", "리콜", "화재", "폭발", "해킹",
    "부정", "부실", "회계", "적자", "감사", "벌금", "과징금", "파산", "채무",
    "인수 무산", "디폴트", "연체", "판매중단", "리스트럭쳐링", "사기", "담합",
]
_POS_KEYWORDS = [
    "수주", "계약", "실적 개선", "호실적", "흑자전환", "완화", "해제",
]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _score_from_text(text: str) -> float:
    """
    매우 단순한 휴리스틱:
    - 부정 키워드당 +0.08
    - 긍정 키워드당 -0.04
    - 기본값 0.30, 0~1로 클램프
    """
    if not text:
        return 0.30
    neg = sum(1 for k in _NEG_KEYWORDS if k in text)
    pos = sum(1 for k in _POS_KEYWORDS if k in text)
    raw = 0.30 + 0.08 * neg - 0.04 * pos
    return _clamp01(raw)


def news_postprocess(ticker: str, raw_steps: Dict[str, str]) -> DomainResult:
    """
    BaseReWOO의 tool 결과는 문자열로 들어올 수 있으므로 안전하게 처리:
    - JSON으로 보이면 파싱해서 snippet/evidence.raw에 넣음
    - 아니면 원문 문자열을 snippet으로 저장
    """
    evidences: List[Evidence] = []
    merged_snippets: List[str] = []

    for step_name, payload_str in (raw_steps or {}).items():
        snippet = ""
        raw_json: Dict[str, Any] | None = None
        try:
            raw = json.loads(payload_str)
            if isinstance(raw, dict):
                raw_json = raw
                # Tavily 형식 대비(있다면)
                if "results" in raw and isinstance(raw["results"], list) and raw["results"]:
                    first = raw["results"][0]
                    snippet = str(first.get("content") or first.get("snippet") or "")[:500]
                else:
                    snippet = payload_str[:500]
            else:
                snippet = str(raw)[:500]
        except Exception:
            snippet = (payload_str or "")[:500]

        merged_snippets.append(snippet)
        evidences.append(
            Evidence(
                source="news",
                title=None,
                url=None,
                snippet=snippet,
                published_at=None,
                raw=raw_json,
                confidence=0.5,
            )
        )

    # 점수 산출(모든 스니펫을 이어붙여 간단 스코어)
    full_text = "\n".join(merged_snippets)
    score = _score_from_text(full_text)

    # 이벤트: 최소 1건 보장
    if not evidences:
        evidences = [
            Evidence(
                source="news",
                snippet="no-news-evidence",
                confidence=0.4,
            )
        ]
    events = [
        DomainEvent(
            ticker=ticker,
            event_type="macro_news",
            severity=score,              # 간단히 점수 = severity
            confidence=0.6 if merged_snippets else 0.4,
            timestamp=datetime.utcnow(),
            evidence=evidences,
        )
    ]

    return DomainResult(
        domain="news",
        ticker=ticker,
        events=events,
        domain_risk_score=score,
        rationale="heuristic(news): keyword-based scoring with safe defaults",
    )
