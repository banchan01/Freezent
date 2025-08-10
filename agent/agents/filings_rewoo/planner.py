FILINGS_PLANNER_PROMPT = """
For the following task (filing risk for a target stock), create a step-by-step plan.
Use tools among: (1) Filings[input], (2) LLM[input]. Each Plan must have exactly one #E variable assignment.
Focus on: audit opinion changes, lawsuits, financing (CB/BW), liquidity warnings, significant contracts, accounting issues.

Begin!
Task: {task}
"""