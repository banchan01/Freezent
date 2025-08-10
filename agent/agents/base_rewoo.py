import re
from typing import Dict
from langgraph.graph import StateGraph
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from common.state import ReWOOState

REGEX = r"Plan:\s*(.+)\s*(#E\d+)\s*=\s*(\w+)\s*\[([^\]]+)\]"

class BaseReWOO:
    def __init__(self, name: str, planner_prompt: str, model_name: str = "gpt-4o"):
        self.name = name
        self.model = ChatOpenAI(model=model_name)
        self.planner = ChatPromptTemplate.from_messages([("user", planner_prompt)]) | self.model
        self.tools: Dict[str, callable] = {}
        self.graph = self._build_graph()

    # ---- override in subclasses to register tools ----
    def register_tools(self):
        pass

    # ---- Planner ----
    def get_plan(self, state: ReWOOState):
        task = state["task"]
        result = self.planner.invoke({"task": task})
        matches = re.findall(REGEX, result.content)
        return {"steps": matches, "plan_string": result.content}

    # ---- Worker ----
    def _get_current_task(self, state: ReWOOState):
        if not state.get("results"):  # None or {}
            return 1
        if len(state["results"]) == len(state["steps"]):
            return None
        return len(state["results"]) + 1

    def tool_execution(self, state: ReWOOState):
        step_idx = self._get_current_task(state)
        _, step_name, tool, tool_input = state["steps"][step_idx - 1]
        results = dict(state.get("results") or {})
        for k, v in results.items():
            tool_input = tool_input.replace(k, v)
        if tool not in self.tools:
            raise ValueError(f"Unknown tool: {tool}")
        out = self.tools[tool](tool_input)
        results[step_name] = str(out)
        return {"results": results}

    # ---- Solver ----
    def solve(self, state: ReWOOState):
        plan = ""
        for _plan, step_name, tool, tool_input in state["steps"]:
            results = dict(state.get("results") or {})
            for k, v in results.items():
                tool_input = tool_input.replace(k, v)
                step_name = step_name.replace(k, v)
            plan += f"Plan: {_plan}\n{step_name} = {tool}[{tool_input}]\n"
        prompt = (
            "Solve the following task using the plan and evidence.\n\n" +
            plan +
            f"\nTask: {state['task']}\nResponse:"
        )
        res = self.model.invoke(prompt)
        return {"result": res.content}

    # ---- Graph wiring ----
    def _route(self, state: ReWOOState):
        return "solve" if self._get_current_task(state) is None else "tool"

    def _build_graph(self):
        self.register_tools()
        g = StateGraph(ReWOOState)
        g.add_node("plan", self.get_plan)
        g.add_node("tool", self.tool_execution)
        g.add_node("solve", self.solve)
        g.add_edge("plan", "tool")
        g.add_conditional_edges("tool", self._route)
        from langgraph.graph import START, END
        g.add_edge(START, "plan")
        g.add_edge("solve", END)
        return g.compile()

    def run(self, task: str):
        state = {"task": task, "plan_string": "", "steps": [], "results": {}, "result": ""}
        out = None
        for s in self.graph.stream(state):
            out = s
        return out