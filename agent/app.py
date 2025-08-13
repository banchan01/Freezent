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
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:2000])
    except Exception:
        print(str(payload)[:2000])


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

    last = {}
    for state in app.stream(init):
        last = state  # langgraph stream yields step-wise deltas

        if "meta_plan" in state:
            _pp("meta_plan", state["meta_plan"])

        if "news" in state and state["news"]:
            _pp("news", {
                "domain": "news",
                "domain_risk_score": state["news"]["news_result"].domain_risk_score
                if state["news"]["news_result"] else None
            })

        if "filings" in state and state["filings"]:
            _pp("filings", {
                "domain": "filing",
                "domain_risk_score": state["filings"]["filing_result"].domain_risk_score
                if state["filings"]["filing_result"] else None
            })

        if "lstm" in state and state["lstm"]:
            _pp("lstm", {
                "domain": "lstm_anomaly",
                "domain_risk_score": state["lstm"]["lstm_result"].domain_risk_score
                if state["lstm"]["lstm_result"] else None
            })

        if "final" in state and "final_report" in state["final"]:
            _pp("final_report", state["final"]["final_report"])

    # 루프가 끝난 후 최종 상태의 final_report만 한 번 출력
    final_report = (last.get("final") or {}).get("final_report")
    if final_report:
        _pp("final_report", final_report)
    else:
        print("\n---")
        print("Final Report could not be generated.")


if __name__ == "__main__":
    main()
