FILINGS_PLANNER_PROMPT = """For the following task, create a step-by-step plan to analyze filings risk.
The input for each tool must be a dictionary-like string.
Assign the output of each step to a variable like #E1, #E2, etc.

Available Tools:
`get_corp_info[{{'stock_name': '...'}}]`: (MANDATORY FIRST STEP) Retrieves the company's unique code 
(`corp_code`).
- `get_floating_stock_ratio[{{'corp_code': '...'}}]`: Calculates the floating stock ratio. Requires
`corp_code`.
`get_biz_performance_tentative[{{'corp_name': '...'}}]`: Retrieves and parses the company's provisional 
business performance announcements.
- `individual_stock_trend[{{'stock_name': '...', 'target_date': '...'}}]`: Analyzes individual stock price
trends up to a target date (YYYYMMDD).
- `crawl_lockup_info[{{'stock_name': '...'}}]`: Crawls lock-up (mandatory holding) information from
Seibro.
- `LLM['...']`: Use this to extract a specific value from a previous step's JSON output.

**IMPORTANT**: To get the `corp_code` for other tools, you MUST use `get_corp_info` first, then use the
`LLM` tool to extract the `corp_code` value from its result. When using a variable (e.g., #E2) as an
input, do NOT put it in quotes.

Example Plan for task "삼성전자의 최근 유동주식비율 분석":
Plan:
#E1 = get_corp_info[{{'stock_name': '삼성전자'}}]
#E2 = LLM['From the JSON in #E1, extract just the value of the "corp_code" field.']
#E3 = get_floating_stock_ratio[{{'corp_code': #E2}}]

Begin!
Task: {task}
"""