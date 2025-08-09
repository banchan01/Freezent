import asyncio
import json
import math
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse
from collections import Counter, defaultdict
from datetime import datetime


# ----- 유틸: 결과 구조가 두 가지 케이스(네 프롬프트 버전별)를 모두 커버 -----
def _get_final_block(res: Dict[str, Any]) -> Dict[str, Any]:
    """
    (1) 관련성 섹션이 있는 버전: res["신뢰도 평가"]["최종 판단"]
    (2) 기존 버전: res["최종 판단"]
    둘 다 없으면 {}
    """
    if "신뢰도 평가" in res and isinstance(res["신뢰도 평가"], dict):
        return res["신뢰도 평가"].get("최종 판단", {}) or {}
    return res.get("최종 판단", {}) or {}


def _get_reasons(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    (1) 관련성 섹션이 있는 버전: res["신뢰도 평가"]["해당되는 기준과 판단 이유"]
    (2) 기존 버전: res["해당되는 기준과 판단 이유"]
    """
    if "신뢰도 평가" in res and isinstance(res["신뢰도 평가"], dict):
        return res["신뢰도 평가"].get("해당되는 기준과 판단 이유", []) or []
    return res.get("해당되는 기준과 판단 이유", []) or []


def _get_escalation(res: Dict[str, Any]) -> bool:
    fb = _get_final_block(res)
    return bool(fb.get("에스컬레이션 필요", False))


def _get_score(res: Dict[str, Any]) -> float | None:
    fb = _get_final_block(res)
    s = fb.get("신뢰도 점수", None)
    try:
        return float(s) if s is not None else None
    except Exception:
        return None


def _get_level(res: Dict[str, Any]) -> str:
    fb = _get_final_block(res)
    return str(fb.get("신뢰도 수준", ""))


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc or "unknown"
    except Exception:
        return "unknown"


# ----- 1) 기사 단위 점수 추출 -----
def extract_article_metrics(article_with_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    입력 예: { "종목명":..., "제목":..., "날짜":..., "본문":..., "링크":..., "분석결과": { ...GPT JSON... } }
    반환: 기사 단위 메트릭(리스크, Strong 카운트 등)
    """
    res = article_with_analysis.get("분석결과", {}) or {}

    score = _get_score(res)  # 0~1 (높을수록 신뢰 높음)
    level = _get_level(res)  # "높음/보통/낮음/불충분" 등
    reasons = _get_reasons(res)  # 기준별 판정 리스트
    escalation = _get_escalation(res)  # True/False

    # Strong 기준 카운트
    strong_ids = {"8", "10", "11", "12", "13"}
    strong_cnt = 0
    strong_strong = 0  # 증거 강도 = "강함" 개수
    strong_by_id = Counter()

    for r in reasons:
        cid = str(r.get("기준 번호"))
        if cid in strong_ids:
            strong_cnt += 1
            strong_by_id[cid] += 1
            if r.get("증거 강도") == "강함":
                strong_strong += 1

    metrics = {
        "종목명": article_with_analysis.get("종목명"),
        "제목": article_with_analysis.get("제목"),
        "링크": article_with_analysis.get("링크"),
        "날짜": article_with_analysis.get("날짜"),
        "출처": _domain(article_with_analysis.get("링크", "")),
        # 핵심 수치
        "score": score,  # 신뢰도 점수
        "risk": (1.0 - score) if score is not None else None,  # 리스크 점수
        "level": level,
        "escalation": escalation,
        # Strong 신호
        "strong_total": strong_cnt,
        "strong_strong": strong_strong,
        "strong_by_id": dict(strong_by_id),  # {"8": n, "10": m, ...}
        # 원문 사유(원하면 저장/로그용)
        "reasons": reasons,
    }
    return metrics


# ----- 2) 종합(가중치 없이 단순 집계 버전) -----
def aggregate_without_preprocessing(
    articles_with_analysis: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    전처리 없이 바로 기사 메트릭을 뽑고, 단순 평균/합계로 종합 결론 도출.
    - 가중치 없음(=모든 기사 동일 가중)
    - 관련성 낮음/중복/기간 필터 전혀 적용하지 않음
    """
    per_article = [extract_article_metrics(a) for a in articles_with_analysis]

    # 유효 score만 집계
    valid = [m for m in per_article if m["score"] is not None]
    if not valid:
        return {
            "종합 판단": {"등급": "불충분", "리스크점수": None, "기사수": 0},
            "기사별": per_article,
        }

    # risk 평균
    R = sum(m["risk"] for m in valid if m["risk"] is not None) / max(len(valid), 1)

    # Strong 합계
    total_strong = sum(m["strong_total"] for m in valid)
    total_strong_strong = sum(m["strong_strong"] for m in valid)

    # 출처 다양성(그냥 참고치)
    domains = {m["출처"] for m in valid if m["출처"]}
    domain_cnt = len(domains)

    # 간단한 규칙(보수적) — 필요하면 숫자 튜닝
    if total_strong >= 3 and R >= 0.6:
        grade = "경보"
    elif total_strong >= 2 and R >= 0.5:
        grade = "주의"
    elif len(valid) < 2:
        grade = "불충분"
    else:
        grade = "관찰"

    # Strong 기준별 총합
    strong_sum_by_id = defaultdict(int)
    for m in valid:
        for cid, cnt in (m["strong_by_id"] or {}).items():
            strong_sum_by_id[cid] += cnt

    return {
        "종합 판단": {
            "등급": grade,  # 경보/주의/관찰/불충분
            "리스크점수": round(R, 3),
            "기사수": len(valid),
            "출처_다양성": domain_cnt,
            "총_Strong합": total_strong,
            "총_Strong(강함)": total_strong_strong,
            "Strong_기준별_합계": dict(strong_sum_by_id),
        }
    }
