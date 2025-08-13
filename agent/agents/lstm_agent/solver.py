# agents/lstm_agent/solver.py
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from common.schemas import DomainResult, DomainEvent, Evidence


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