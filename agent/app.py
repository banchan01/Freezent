# app.py
from __future__ import annotations

import json
import os
from typing import Any, Dict

from orchestration.graph import build_meta_graph


def _pp(title: str, payload: Dict[str, Any] | None):
    print(f"\n=== {title} ===")
    if payload is None:
        print("(none)")
        return
    try:
        s = json.dumps(payload, ensure_ascii=False, indent=2)
        # 1) 본문은 예전처럼 2,000자까지만
        print(s[:2000])
        # 2) llm_report가 있으면 별도로 전체 출력
        try:
            if isinstance(payload, dict) and "llm_report" in payload and payload["llm_report"]:
                print("\n--- llm_report (full) ---")
                # llm_report는 원문 그대로 풀출력 (자르지 않음)
                print(payload["llm_report"])
        except Exception:
            pass
    except Exception:
        txt = str(payload)
        print(txt[:2000])
        if isinstance(payload, dict) and payload.get("llm_report"):
            print("\n--- llm_report (full) ---")
            print(payload["llm_report"])


def _as_dict(x: Any) -> Dict[str, Any]:
    """
    dict / pydantic / 네임스페이스 등 무엇이 오든 dict로 정규화
    - pydantic v2: exclude_none=False 강제
    - pydantic v1: exclude_none=False 강제
    """
    if x is None:
        return {}
    if isinstance(x, dict):
        return x
    # pydantic v2
    if hasattr(x, "model_dump") and callable(getattr(x, "model_dump")):
        try:
            return x.model_dump(exclude_none=False)
        except Exception:
            pass
    # pydantic v1
    if hasattr(x, "dict") and callable(getattr(x, "dict")):
        try:
            return x.dict(exclude_none=False)
        except Exception:
            pass
    # 일반 객체
    try:
        return dict(x.__dict__)
    except Exception:
        return {"value": x}


def main():
    app = build_meta_graph()

    init = {
        "ticker": os.getenv("TEST_TICKER", "삼성전자"),
        "horizon": os.getenv("TEST_HORIZON", "30d"),
        "task": "Assess combined risk from news & filings",
        "news_result": None,
        "filing_result": None,
        "lstm_result": None,
        "final_report": None,
    }

    print(f"TICKER={init['ticker']}  HORIZON={init['horizon']}")

    last: Dict[str, Any] = {}
    for state in app.stream(init):
        last = state  # langgraph stream yields step-wise deltas

        if "meta_plan" in state:
            _pp("meta_plan", state["meta_plan"])

        # --- NEWS ---
        if "news" in state:
            news_node = state.get("news") or {}
            news_raw = news_node.get("news_result")
            news_dict = _as_dict(news_raw)

            # 디버그: 실제 포함 키 확인
            try:
                print("[DBG][app.news] keys:", list(news_dict.keys()))
            except Exception:
                pass

            payload = {
                "domain": news_dict.get("domain", "news"),
                "domain_risk_score": news_dict.get("domain_risk_score"),
            }
            for k, v in news_dict.items():
                if k not in ("domain", "domain_risk_score"):
                    payload[k] = v
            _pp("news", payload)

        # --- FILINGS ---
        if "filings" in state:
            filings_node = state.get("filings") or {}
            filings_raw = filings_node.get("filing_result")
            filings_dict = _as_dict(filings_raw)

            try:
                print("[DBG][app.filings] keys:", list(filings_dict.keys()))
            except Exception:
                pass

            payload = {
                "domain": filings_dict.get("domain", "filing"),
                "domain_risk_score": filings_dict.get("domain_risk_score"),
            }
            for k, v in filings_dict.items():
                if k not in ("domain", "domain_risk_score"):
                    payload[k] = v
            _pp("filings", payload)

        # --- LSTM ---
        if "lstm" in state:
            lstm_node = state.get("lstm") or {}
            lstm_raw = lstm_node.get("lstm_result")
            lstm_dict = _as_dict(lstm_raw)

            try:
                print("[DBG][app.lstm] keys:", list(lstm_dict.keys()))
            except Exception:
                pass

            payload = {
                "domain": lstm_dict.get("domain", "lstm_anomaly"),
                "domain_risk_score": lstm_dict.get("domain_risk_score"),
            }
            for k, v in lstm_dict.items():
                if k not in ("domain", "domain_risk_score"):
                    payload[k] = v
            _pp("lstm", payload)

        if "final" in state and "final_report" in state["final"]:
            _pp("final_report", _as_dict(state["final"]["final_report"]))

    final_report = (last.get("final") or {}).get("final_report")
    if final_report:
        _pp("final_report", _as_dict(final_report))
    else:
        print("\n---")
        print("Final Report could not be generated.")


if __name__ == "__main__":
    main()
