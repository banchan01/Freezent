# agents/filings_rewoo/solver.py
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from common.schemas import DomainResult, DomainEvent, Evidence
from langchain_openai import ChatOpenAI
from common.utils import OPENAI_API_KEY

def _build_llm_report_filings(ticker: str, raw_steps: Dict[str, Any]) -> str:
    try:
        model = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o-mini", temperature=0.2)
        steps_preview = json.dumps(raw_steps, ensure_ascii=False, default=str)
        if len(steps_preview) > 6000:
            steps_preview = steps_preview[:6000] + " ... (truncated)"
        prompt = (
            f"Analyze the filings-derived evidence for '{ticker}'.\n"
            f"Steps(JSON):\n{steps_preview}\n\n"
            "Instructions:\n"
            "- Highlight accounting/legal signals (restatements, going concern, covenants, related parties, etc.).\n"
            "- Summarize risk implications in plain language.\n"
            "- Provide a one-sentence verdict on filings-driven risk.\n"
            "Return a concise markdown report (no code blocks)."
        )
        res = model.invoke(prompt)
        return getattr(res, "content", str(res)).strip()[:5000]
    except Exception as e:
        return f"[llm_report_error] {e}"

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _extract_counts_and_hints(raw_steps: Dict[str, str]) -> Dict[str, Any]:
    """
    MCP 도구 응답은 BaseReWOO에서 문자열로 들어오므로,
    - JSON 파싱을 시도하고 {"ok": True, "data": {...}} 형태에서 핵심 필드를 추출합니다.
    - PaidInAnalyze/BizChangeAnalyze: data.filings_count, data.summary
    - ListPaidIn/ListBizReports: data.total, data.items[...rpt_nm]
    """
    total_list = 0
    total_analyzed = 0
    titles: List[str] = []
    summaries: List[str] = []

    for _, s in (raw_steps or {}).items():
        try:
            obj = json.loads(s) if isinstance(s, str) else s
        except Exception:
            obj = None

        if not isinstance(obj, dict):
            continue

        data = obj.get("data") if "data" in obj else None
        if not isinstance(data, dict):
            continue

        # Analyze 류
        if "filings_count" in data:
            try:
                total_analyzed += int(data.get("filings_count") or 0)
            except Exception:
                pass
        if isinstance(data.get("summary"), str):
            summaries.append(data["summary"])

        # List 류
        if isinstance(data.get("total"), int):
            total_list += data["total"]
        if isinstance(data.get("items"), list):
            for it in data["items"]:
                if isinstance(it, dict):
                    nm = it.get("rpt_nm") or it.get("report_nm")
                    if isinstance(nm, str):
                        titles.append(nm)

    return {
        "total_list": total_list,
        "total_analyzed": total_analyzed,
        "titles": titles,
        "summaries": summaries,
    }


def _score_from_filings(stats: Dict[str, Any]) -> float:
    """
    매우 단순한 휴리스틱:
    - 공시 건수(total_list)와 분석 건수(total_analyzed)에 비례해 기본 리스크를 올림
    - 특정 키워드(유상증자/전환사채/감사의견/한정/소송/회계) 포함 시 가중
    """
    base = 0.25
    tl = int(stats.get("total_list") or 0)
    ta = int(stats.get("total_analyzed") or 0)

    # 건수 기반 증가 (상한 클램프)
    base += min(0.30, 0.03 * tl)
    base += min(0.25, 0.05 * ta)

    text = " ".join(stats.get("titles", []) + stats.get("summaries", []))
    boosts = 0.0
    # 키워드 (간단 예시)
    if any(k in text for k in ["유상증자", "제3자배정", "CB", "BW", "전환사채"]):
        boosts += 0.10
    if any(k in text for k in ["감사의견", "의견거절", "한정", "검토의견"]):
        boosts += 0.15
    if any(k in text for k in ["소송", "분쟁", "규제", "제재"]):
        boosts += 0.10
    if any(k in text for k in ["회계", "부정", "부실", "정정공시"]):
        boosts += 0.10

    return _clamp01(base + boosts)


def filings_postprocess(ticker: str, raw_steps: Dict[str, Any]) -> DomainResult:
    stats = _extract_counts_and_hints(raw_steps)
    score = _score_from_filings(stats)

    # Evidence 구성 (첫 요약/첫 타이틀만 일부 노출)
    snippet = ""
    if stats.get("summaries"):
        snippet = str(stats["summaries"][0])[:500]
    elif stats.get("titles"):
        snippet = str(stats["titles"][0])[:200]

    evidence = Evidence(
        source="filing",
        title=None,
        url=None,
        snippet=snippet or "no-filing-evidence",
        published_at=None,
        raw=stats,  # 요약된 통계/힌트를 raw로 남김
        confidence=0.7 if snippet else 0.5,
    )

    # 최소 1건 이벤트 생성 (회계/재무 성격이 강하므로 accounting_issue 기본)
    events = [
        DomainEvent(
            ticker=ticker,
            event_type="accounting_issue",
            severity=score,
            confidence=0.7 if snippet else 0.5,
            timestamp=datetime.utcnow(),
            evidence=[evidence],
        )
    ]

    rationale = " ".join(stats.get("summaries", []))
    if not rationale:
        rationale = "No significant summary from filings."
    llm_report = _build_llm_report_filings(ticker, raw_steps)
    return DomainResult(
        domain="filing",
        ticker=ticker,
        events=events,
        domain_risk_score=score,
        rationale=rationale,  # 요약 정보를 rationale에 담아 전달
        llm_report=llm_report,
    )
