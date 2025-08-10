# agents/base_rewoo.py
from __future__ import annotations
import os
import re
from typing import Dict, List, Tuple, Any

from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate
from common.state import ReWOOState
from common.utils import OPENAI_API_KEY
REGEX = r"Plan:\s*(.+)\s*(#E\d+)\s*=\s*([A-Za-z0-9_]+)\[([^\]]+)\]"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


def _dbg(msg: str, payload: Dict[str, Any] | None = None):
    if DEBUG:
        print(f"[BaseReWOO] {msg}")
        if payload:
            try:
                import json
                print(json.dumps(payload, ensure_ascii=False, indent=2)[:1500])
            except Exception:
                print(str(payload)[:1500])


class BaseReWOO:
    def __init__(self, name: str, planner_prompt: str, model_name: str = "gpt-4o"):
        self.name = name
        self.tools: Dict[str, callable] = {}

        # ✅ 런타임에 환경변수 읽기 (모듈 임포트 타이밍 문제 회피)
        self._use_mock = os.getenv("MOCK_LLM", "false").lower() == "true"

        if self._use_mock:
            # 프롬프트 파이프라인은 형식만 유지 (LLM 미호출)
            self.planner = ChatPromptTemplate.from_messages([("user", planner_prompt)])
            self.model = None
        else:
            # ✅ 지연 import: MOCK이 아닐 때만 OpenAI 클라이언트 로드
            from langchain_openai import ChatOpenAI
            self.model = ChatOpenAI(api_key=OPENAI_API_KEY, model=model_name)
            self.planner = ChatPromptTemplate.from_messages([("user", planner_prompt)]) | self.model

        self.graph = self._build_graph()

    def register_tools(self):
        pass

    # ---- Mock helpers ----
    def _mock_plan_text(self, task: str) -> str:
        return (
            f"Plan: search relevant sources for the task\n"
            f"#E1 = Google[{task}]\n"
            f"Plan: summarize and structure the findings\n"
            f"#E2 = LLM[#E1]\n"
        )

    def _mock_solve(self, task: str, plan: str, evidence: Dict[str, str]) -> str:
        bullets = "\n".join(f"- {k}: {str(v)[:120]}" for k, v in (evidence or {}).items())
        return (
            "Summary (mock):\n"
            f"Task: {task}\n\n"
            "Plan used:\n"
            f"{plan}\n"
            "Evidence snippets:\n"
            f"{bullets or '- (no evidence)'}\n"
            "Conclusion: This is a mock response used for offline/dev mode."
        )

    # ---- Planner ----
    def _default_steps(self, task: str) -> List[Tuple[str, str, str, str]]:
        return [("Minimal plan: search then solve", "#E1", "Google", task)]

    def get_plan(self, state: ReWOOState):
        task = state["task"]

        if self._use_mock:
            plan_text = self._mock_plan_text(task)
            matches = re.findall(REGEX, plan_text)
            _dbg("mock planner", {"plan_text": plan_text, "n_matches": len(matches)})
            steps = matches if matches else self._default_steps(task)
            return {"steps": steps, "plan_string": plan_text}

        try:
            result = (self.planner).invoke({"task": task})
            plan_text = getattr(result, "content", str(result))
        except Exception as e:
            _dbg("planner error; fallback to default steps", {"err": str(e)})
            steps = self._default_steps(task)
            return {"steps": steps, "plan_string": f"[planner-error] {e}"}

        matches = re.findall(REGEX, plan_text)
        _dbg("planner output", {"plan_text": plan_text, "n_matches": len(matches)})
        if not matches:
            steps = self._default_steps(task)
            return {"steps": steps, "plan_string": plan_text}
        return {"steps": matches, "plan_string": plan_text}

    # ---- Worker ----
    def _get_current_task(self, state: ReWOOState):
        if not state.get("steps"):
            return None
        if not state.get("results"):
            return 1
        if len(state["results"]) >= len(state["steps"]):
            return None
        return len(state["results"]) + 1

    def tool_execution(self, state: ReWOOState):
        step_idx = self._get_current_task(state)
        if step_idx is None:
            return {"results": state.get("results", {})}

        if step_idx < 1 or step_idx > len(state.get("steps", [])):
            _dbg("tool_execution index out of range; skipping to solve", {
                "step_idx": step_idx,
                "len_steps": len(state.get("steps", [])),
            })
            return {"results": state.get("results", {})}

        _, step_name, tool, tool_input = state["steps"][step_idx - 1]

        results = dict(state.get("results") or {})
        for k, v in results.items():
            tool_input = tool_input.replace(k, v)

        if tool not in self.tools:
            _dbg("unknown tool; skipping", {"tool": tool})
            results[step_name] = f"[error] unknown tool: {tool}"
            return {"results": results}

        try:
            out = self.tools[tool](tool_input)
        except Exception as e:
            _dbg("tool execution error", {"tool": tool, "err": str(e)})
            out = f"[tool-error:{tool}] {e}"

        results[step_name] = str(out)
        return {"results": results}

    # ---- Solver ----
    def solve(self, state: ReWOOState):
        plan = ""
        for _plan, step_name, tool, tool_input in (state.get("steps") or []):
            results = dict(state.get("results") or {})
            for k, v in results.items():
                tool_input = tool_input.replace(k, v)
                step_name = step_name.replace(k, v)
            plan += f"Plan: {_plan}\n{step_name} = {tool}[{tool_input}]\n"

        if self._use_mock:
            return {"result": self._mock_solve(state["task"], plan, state.get("results") or {})}

        # 실제 LLM 경로
        res = self.model.invoke(
            "Solve the following task using the plan and evidence.\n\n"
            + plan
            + f"\nTask: {state['task']}\nResponse:"
        )
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
        g.add_edge(START, "plan")
        g.add_edge("solve", END)
        return g.compile()

    def run(self, task: str):
        state: ReWOOState = {
            "task": task,
            "plan_string": "",
            "steps": [],
            "results": {},
            "result": "",
        }
        out = None
        for s in self.graph.stream(state):
            out = s
        return out
