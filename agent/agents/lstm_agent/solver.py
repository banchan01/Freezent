# agents/lstm_agent/solver.py
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from common.schemas import DomainResult, DomainEvent, Evidence
from langchain_openai import ChatOpenAI
from common.utils import OPENAI_API_KEY
 
def _build_llm_report(ticker: str, raw_steps: Dict[str, Any]) -> str:
    """
    raw_steps(#E1, #E2 ...)을 LLM에 요약/해석 요청해 리포트를 생성.
    실패해도 빈 문자열 반환.
    """
    try:
        model = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o-mini", temperature=0.2)
        # steps를 과하게 길게 보내지 않도록 캡
        steps_preview = json.dumps(raw_steps, ensure_ascii=False, default=str)
        if len(steps_preview) > 6000:
            steps_preview = steps_preview[:6000] + " ... (truncated)"
        prompt = (
            f"You are an equity risk analyst. Analyze these tool steps for ticker '{ticker}'.\n"
            f"Steps(JSON):\n{steps_preview}\n\n"
            "Instructions:\n"
            "- Summarize the signals (what they indicate and why).\n"
            "- Note any conflicts or uncertainties.\n"
            "- Provide a one-sentence verdict on LSTM-anomaly risk.\n"
            "Return a concise markdown report (no code blocks)."
        )
        res = model.invoke(prompt)
        txt = getattr(res, "content", str(res)).strip()
        return txt[:5000]
    except Exception as e:
        return f"[llm_report_error] {e}"

def lstm_postprocess(ticker: str, raw_steps: Dict[str, Any]) -> DomainResult:
    """
    Processes the output from the LSTM anomaly detection tool,
    and formats it into a DomainResult.
    """
    anomaly_ratio = 0.0
    raw_output = None

    # Extract anomaly_ratio from the tool's output
    for _, step_output in (raw_steps or {}).items():
        output_dict = None
        if isinstance(step_output, dict):
            output_dict = step_output
        elif isinstance(step_output, str):
            try:
                output_dict = json.loads(step_output)
            except (json.JSONDecodeError, TypeError):
                continue
        
        if output_dict and 'anomaly_ratio' in output_dict:
            try:
                anomaly_ratio = float(output_dict['anomaly_ratio'])
                raw_output = output_dict
                break # Found it, no need to check other steps
            except (ValueError, TypeError):
                continue

    # Create Evidence
    evidence = Evidence(
        source="lstm_model",
        title="LSTM Anomaly Detection",
        url=None,
        snippet=f"Anomaly ratio: {anomaly_ratio:.4f}",
        published_at=None,
        raw=raw_output,
        confidence=0.8  # High confidence as it's a model output
    )

    # Create DomainEvent
    event = DomainEvent(
        ticker=ticker,
        event_type="price_anomaly",
        severity=anomaly_ratio,
        confidence=0.8,
        timestamp=datetime.utcnow(),
        evidence=[evidence]
    )

    rationale = f"LSTM model detected a price anomaly score of {anomaly_ratio:.4f} for {ticker}."

    return DomainResult(
        domain="lstm_anomaly",
        ticker=ticker,
        events=[event],
        domain_risk_score=anomaly_ratio,
        rationale=rationale,
    )