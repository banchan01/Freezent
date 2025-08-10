NEWS_PLANNER_PROMPT = """
For the following task (news risk for a target stock), create a step-by-step plan.
Use tools among: (1) Google[input], (2) LLM[input]. Each Plan must have exactly one #E variable assignment.
Focus on: entity disambiguation, recentness, source credibility, event extraction (management change, litigation, product_issue, regulatory, macro_news).

Begin!
Task: {task}
"""