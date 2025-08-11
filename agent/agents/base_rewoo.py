# agents/base_rewoo.py
from __future__ import annotations
import os
import re
import ast  # For safe evaluation of string literals
import json # For serializing results
import asyncio
from typing import Dict, List, Tuple, Any

from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI

from common.state import ReWOOState
from common.utils import OPENAI_API_KEY
from clients.mcp_adapter_client import load_mcp_tools # Import the new MCP adapter client

# Updated regex to capture the new plan format: #E = tool_name[{'arg': 'value'}]
REGEX = r"([#A-Za-z0-9_]+)\s*=\s*([a-zA-Z0-9_]+)\[(\{.*\})]"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


def _dbg(msg: str, payload: Dict[str, Any] | None = None):
    if DEBUG:
        print(f"[BaseReWOO] {msg}")
        if payload:
            try:
                # Use the same json import as the main code
                print(json.dumps(payload, ensure_ascii=False, indent=2)[:1500])
            except Exception:
                print(str(payload)[:1500])


class BaseReWOO:
    def __init__(self, name: str, planner_prompt: str, model_name: str = "gpt-4o"):
        self.name = name
        self.model = ChatOpenAI(api_key=OPENAI_API_KEY, model=model_name)
        self.planner = ChatPromptTemplate.from_messages([("user", planner_prompt)]) | self.model
        
        # Load tools using the new adapter
        try:
            mcp_tools = asyncio.run(load_mcp_tools())
        except Exception as e:
            print(f"FATAL: Could not load tools from MCP server: {e}")
            mcp_tools = []

        # Create a manual tool for the LLM
        llm_tool = Tool(
            name="LLM",
            func=self.model.invoke,
            description="Use this to extract a specific value from a previous step's JSON output. The input is the prompt.",
        )
        
        all_tools = mcp_tools + [llm_tool]
        self.tool_map = {tool.name: tool for tool in all_tools}
        
        self.graph = self._build_graph()

    # ---- Planner ----
    def _default_steps(self, task: str) -> List[Tuple[str, str, str]]:
        # Default step as a fallback.
        # It tries to parse the ticker and call the correct stock trend tool.
        from datetime import datetime
        import re

        # Attempt to extract a ticker (e.g., 005930.KS) or a Korean company name from the task string
        ticker_match = re.search(r'([0-9A-Z]+\.[A-Z]{2,}|[가-힣]+)', task)
        if not ticker_match:
            return [] # Return no steps if no ticker is found

        stock_name = ticker_match.group(1)
        target_date = datetime.now().strftime('%Y%m%d')

        tool_name = "individual_stock_trend"
        tool_input = f"{{'stock_name': '{stock_name}', 'target_date': '{target_date}'}}"
        
        return [("#E", tool_name, tool_input)]

    def get_plan(self, state: ReWOOState):
        task = state["task"]

        try:
            result = (self.planner).invoke({"task": task})
            plan_text = getattr(result, "content", str(result))
            print(f"\n>> Planner raw output for agent '{self.name}':")
            print(f"--- START PLAN ---\n{plan_text}\n--- END PLAN ---")
        except Exception as e:
            # Always print the planner error to the console for visibility
            print(f"\n>> ERROR: Planner for agent '{self.name}' failed: {e}")
            _dbg("planner error; fallback to default steps", {"err": str(e)})
            steps_3_tuple = self._default_steps(task)
            steps_4_tuple = [("Plan from default", s[0], s[1], s[2]) for s in steps_3_tuple]
            return {"steps": steps_4_tuple, "plan_string": f"[planner-error] {e}"}

        # Use the new REGEX
        matches = re.findall(REGEX, plan_text)
        _dbg("planner output", {"plan_text": plan_text, "n_matches": len(matches)})
        print("\n>> Plan Generated:")
        print(plan_text)
        
        if not matches:
            steps_3_tuple = self._default_steps(task)
        else:
            # matches is a list of (step_name, tool, tool_input_str)
            steps_3_tuple = matches

        # The rest of the system expects a 4-tuple, so we add a dummy plan description.
        steps_4_tuple = [("MCP Tool Call", s[0], s[1], s[2]) for s in steps_3_tuple]
        return {"steps": steps_4_tuple, "plan_string": plan_text}

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

        # Unpack the 4-tuple step
        _, step_name, tool_name, tool_input_str = state["steps"][step_idx - 1]

        print(f"\n>> Calling Tool: {tool_name} (step {step_idx})")
        print(f"   Input: {tool_input_str}")

        results = dict(state.get("results") or {})
        # Replace placeholders like #E1 with actual results
        for k, v in results.items():
            tool_input_str = tool_input_str.replace(k, v)

        try:
            tool_to_run = self.tool_map.get(tool_name)
            if not tool_to_run:
                raise ValueError(f"Tool '{tool_name}' not found.")

            # LLM tool is a special case that takes a string input directly
            if tool_name == "LLM":
                out = tool_to_run.invoke(tool_input_str)
            else:
                # Use ast.literal_eval to safely parse the string into a dict
                kwargs = ast.literal_eval(tool_input_str)
                if not isinstance(kwargs, dict):
                    raise TypeError("Tool input must be a dictionary.")
                
                # Invoke the tool using the standard LangChain async interface
                out = asyncio.run(tool_to_run.ainvoke(kwargs))

        except Exception as e:
            _dbg("tool execution error", {"tool": tool_name, "err": str(e)})
            out = f"[tool-error:{tool_name}] {e}"

        print(f"\n>> Tool Result ({tool_name}):")
        try:
            if isinstance(out, (dict, list)):
                print(json.dumps(out, ensure_ascii=False, indent=2))
            elif isinstance(out, str) and ('{' in out or '[' in out):
                 parsed_out = json.loads(out)
                 print(json.dumps(parsed_out, ensure_ascii=False, indent=2))
            else:
                print(out)
        except Exception:
            print(out)

        # Store the result. If it's a dict/list, store as JSON string. Otherwise, as is.
        if isinstance(out, (dict, list)):
            results[step_name] = json.dumps(out, ensure_ascii=False)
        else:
            results[step_name] = str(out)
            
        return {"results": results}

    # ---- Solver ----
    def solve(self, state: ReWOOState):
        plan = ""
        # The plan reconstruction needs to handle the new format
        for _plan, step_name, tool, tool_input in (state.get("steps") or []):
            results = dict(state.get("results") or {})
            # Replace placeholders in the input string
            for k, v in results.items():
                tool_input = tool_input.replace(k, v) # v is a JSON string here
            
            plan += f"{step_name} = {tool}[{tool_input}]\n"

        # The original solver prompt might need adjustment if the final output format changes.
        # For now, we assume the final summarization by LLM is still desired.
        solve_prompt = (
            "Solve the following task using the plan and evidence.\n"
            "The evidence is provided as a JSON string in the plan execution result.\n\n"
            f"Plan and Evidence:\n{plan}\n"
            f"Task: {state['task']}\nResponse:"
        )
        
        res = self.model.invoke(solve_prompt)
        return {"result": res.content}

    # ---- Graph wiring ----
    def _route(self, state: ReWOOState):
        return "solve" if self._get_current_task(state) is None else "tool"

    def _build_graph(self):
        # register_tools is no longer needed
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
