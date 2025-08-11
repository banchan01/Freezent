NEWS_PLANNER_PROMPT = """For the following task, create a single-step plan to analyze stock news.
Your goal is to call the `analyze_stock_news` tool.
This tool requires a `stock_name`. You must extract the stock ticker or company name from the task.

Available Tool:
- `analyze_stock_news[{'stock_name': '...', 'max_articles': 5}]`: Analyzes news for the given stock.

Example for task "Assess news-driven risk for 005930.KS over 30d.":
Plan:
#E = analyze_stock_news[{'stock_name': '005930.KS', 'max_articles': 5}]

Begin!
Task: {task}
"""