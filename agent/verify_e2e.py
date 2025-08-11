# verify_e2e.py
from __future__ import annotations

import json
import os
import sys

from orchestration.graph import build_meta_graph


def run_once(ticker: str, horizon: str) -> dict:
    app = build_meta_graph()
    init = {
        "ticker": ticker,
        "horizon": horizon,
        "task": "Assess combined risk from news & filings",
        "news_result": None,
        "filing_result": None,
        "final_report": None,
    }
    last = {}
    for s in app.stream(init):
        last = s
    return (last.get("final") or {}).get("final_report") or {}


def main():
    ticker = os.getenv("TEST_TICKER", "삼성전자")
    horizon = os.getenv("TEST_HORIZON", "30d")

    mode = "HTTP" if os.getenv("USE_MCP", "false").lower() == "true" else "MOCK"
    print(f"[verify_e2e] USE_MCP={mode}  TICKER={ticker}  HORIZON={horizon}")

    result = run_once(ticker, horizon)

    # 간단한 유효성 검사
    required_keys = ["ticker", "final_score", "news_score", "filing_score"]
    missing = [k for k in required_keys if k not in result]
    if missing:
        print(f"[verify_e2e] ❌ Missing keys in final_report: {missing}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    if not (0.0 <= float(result["final_score"]) <= 1.0):
        print(f"[verify_e2e] ❌ final_score out of range: {result['final_score']}")
        sys.exit(1)

    print("[verify_e2e] ✅ E2E OK")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
