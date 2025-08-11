NEWS_PLANNER_PROMPT = """For the following task, create a single-step plan to analyze stock news.
You have one tool: `analyze_stock_news`. The input for this tool must be a dictionary-like string.
The plan must assign the tool's output to the variable #E.

Example for task "삼성전자":
Plan:
#E = analyze_stock_news[{'stock_name': '삼성전자'}]

Begin!
Task: {task}
"""