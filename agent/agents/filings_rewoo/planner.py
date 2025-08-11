FILINGS_PLANNER_PROMPT = """For the following task, create a step-by-step plan to analyze filings risk.
The input for each tool must be a dictionary-like string.
Assign the output of each step to a variable like #E1, #E2, etc.

Available Tools:
- `stock_info[{{'stock_name': '...'}}]`: Retrieves basic stock information, including the company code (`corp_code`).
- `PaidInAnalyze[{{'corp_code': '...', 'bgn_de': '...', 'end_de': '...'}}]`: Analyzes risks related to financing (e.g., paid-in capital increases).
- `BizChangeAnalyze[{{'corp_code': '...', 'bgn_de': '...', 'end_de': '...'}}]`: Analyzes risks related to business performance changes.
- `LLM['...']`: A general-purpose language model to extract specific information from the JSON output of a previous step. Use it to get values needed for subsequent steps.

**IMPORTANT**: When using a variable from a previous step (e.g., #E1) as an input, do NOT put it in quotes.

Example Plan for task "삼성전자의 최근 유상증자 리스크 분석":
Plan:
#E1 = stock_info[{{'stock_name': '삼성전자'}}]
#E2 = LLM['From the JSON in #E1, extract just the value of the \'corp_code\' field.']
#E3 = PaidInAnalyze[{{'corp_code': #E2, 'bgn_de': '20240101', 'end_de': '20241231'}}]

Begin!
Task: {task}
"""