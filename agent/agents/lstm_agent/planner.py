LSTM_PLANNER_PROMPT = """For the following task, create a step-by-step plan to predict stock price anomaly.
The plan MUST consist of a single step using the `predict_lstm_anomaly` tool.
The output format MUST be exactly: `#E1 = predict_lstm_anomaly[{{'stock_name': '...'}}]`

The input for the tool must be a dictionary-like string.

Available Tools:
- `predict_lstm_anomaly[{{'stock_name': '...'}}]`: Takes a stock name and returns the anomaly ratio based on the last month's stock prices.

Example Plan for task "삼성전자의 최근 주가 이상치 분석":
Plan:
#E1 = predict_lstm_anomaly[{{'stock_name': '삼성전자'}}]

Begin!
Task: {task}
"""