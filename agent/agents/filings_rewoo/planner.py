FILINGS_PLANNER_PROMPT = """For the following task, create a step-by-step plan to analyze filings risk.
The input for each tool must be a dictionary-like string.
Assign the output of each step to a variable like #E1, #E2, etc.

Today's date is {today_str}.

Available Tools:
- `get_corp_info[{{'stock_name': '...'}}]`: (MANDATORY FIRST STEP) Retrieves the company's unique code (`corp_code`).
- `get_floating_stock_ratio[{{'corp_code': '...'}}]`: Calculates the floating stock ratio. Requires `corp_code`.
- `get_biz_performance_tentative[{{'corp_name': '...'}}]`: Retrieves and parses the company's provisional business performance announcements.
- `individual_stock_trend[{{'stock_name': '...', 'target_date': '...'}}]`: Analyzes individual stock price trends up to a target date. **The `target_date` MUST be in YYYYMMDD format.** If the task mentions a relative date (e.g., "a month ago", "30 days ago"), you must calculate the exact date based on today's date ({today_str}) and format it as YYYYMMDD.
- `crawl_lockup_info[{{'stock_name': '...'}}]`: Crawls lock-up (mandatory holding) information from Seibro.
- `analyze_paid_in_capital_increase[{{'corp_code': '...'}}]`: Uses DART `piicDecsn` data (paid-in capital increase, incl. third-party allocation) and an internal Chat model to produce an expert assessment on investment stance and potential market manipulation risk. **Requires `corp_code`.** Returns a JSON-like object containing the raw `piic` list and the model's `analysis`.
- `LLM['...']`: Use this to extract a specific value from a previous step's JSON output or to analyze a previous step's result.

**IMPORTANT**: 
- To get the `corp_code` for other tools, you MUST use `get_corp_info` first, then use the `LLM` tool to extract the `corp_code` value from its result. When using a variable (e.g., #E2) as an input, do NOT put it in quotes.
- Whenever you call `get_biz_performance_tentative` and assign it to #En, you MUST add the VERY NEXT step as `#E(n+1) = LLM['...']` that analyzes ONLY `#En` and returns strict JSON (e.g., sharp QoQ/YoY shifts and any corrections/정정 with reasons if present). Do not reference other steps in this LLM step.
- To analyze paid-in capital increases, call `analyze_paid_in_capital_increase` **after** obtaining `corp_code`. If the task requires synthesizing multiple signals (e.g., floating stock ratio + paid-in analysis), add a final `LLM['...']` step that combines ONLY the relevant #E variables and returns a concise JSON summary of risks.

Example Plan for task "삼성전자의 최근 유동주식비율 및 영업(잠정)실적변화 분석":
Plan:
#E1 = get_corp_info[{{'stock_name': '삼성전자'}}]
#E2 = LLM['From the JSON in #E1, extract just the value of the "corp_code" field.']
#E3 = get_floating_stock_ratio[{{'corp_code': #E2}}]
#E4 = get_biz_performance_tentative[{{'corp_name': '삼성전자'}}]
#E5 = LLM['Analyze ONLY #E4 and return strict JSON with (1) sharp shifts (e.g., QoQ≥20%, YoY≥30%), (2) any corrections/정정 and reason text if present, (3) brief summary.']

Example Plan for task "삼성전자의 유상증자 공시 기반 투자/조작 위험 분석":
Plan:
#E1 = get_corp_info[{{'stock_name': '삼성전자'}}]
#E2 = LLM['From the JSON in #E1, extract just the value of the "corp_code" field.']
#E3 = analyze_paid_in_capital_increase[{{'corp_code': #E2}}]
#E4 = LLM['Summarize ONLY #E3 into strict JSON with (1) key risk drivers from paid-in capital increases, (2) any manipulation red flags (e.g., repeated unusual purposes, mismatched funding needs, short-selling context), and (3) an overall risk rating (LOW/MEDIUM/HIGH).']

Begin!
Task: {task}
"""
