# agents/base_rewoo.py
from __future__ import annotations

import os
import re
import json
import asyncio
from typing import Dict, List, Tuple, Any

from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI

from common.state import ReWOOState
from common.utils import OPENAI_API_KEY
from clients.mcp_adapter_client import load_mcp_tools

# ──────────────────────────────────────────────────────────────────────────────
# Config / Utils
# ──────────────────────────────────────────────────────────────────────────────

# "#E1 = tool_name[ ... ]" 대괄호 내부가 문자열이든 dict든 모두 매칭
REGEX = r"([#A-Za-z0-9_]+)\s*=\s*([a-zA-Z0-9_]+)\[(.*?)\]"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

def _dbg(msg: str, payload: Dict[str, Any] | None = None):
    if DEBUG:
        print(f"[BaseReWOO] {msg}")
        if payload is not None:
            try:
                print(json.dumps(payload, ensure_ascii=False, indent=2)[:1500])
            except Exception:
                print(str(payload)[:1500])

# #E1, #E2 ... 참조 치환용
REF_PAT = re.compile(r"#E\d+")
# 8자리 숫자 corp_code
CORP_CODE_PAT = re.compile(r"\b\d{8}\b")

def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)

def _maybe_json_loads(v: Any) -> Any:
    """문자열이면 JSON 파싱을 시도하고, 안 되면 원본 반환."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v

def _resolve_placeholders_to_json_literal(s: str, results: dict) -> str:
    """
    문자열 s 안의 #E? 토큰을 results 값(파이썬 객체)으로 치환하여
    JSON 리터럴 문자열을 만든다.
    """
    def _sub(m):
        key = m.group(0)  # '#E2'
        if key not in results:
            raise ValueError(f"Unresolved reference: {key}")
        val_loaded = _maybe_json_loads(results[key])
        return _json_dumps(val_loaded)
    return REF_PAT.sub(_sub, s)

def _strip_wrapping_quotes(s: str) -> str:
    """
    LLM[' ... '] 처럼 전달되는 경우, 양끝의 같은 종류 따옴표를 벗긴다.
    (문자열 내부 따옴표는 건드리지 않음)
    """
    s = s.strip()
    if len(s) >= 2 and ((s[0] == s[-1]) and s[0] in ("'", '"')):
        return s[1:-1]
    return s

def _postprocess_corp_code(text: str, fallback_json: Any | None = None) -> str:
    """
    LLM이 반환한 텍스트에서 8자리 숫자만 추출.
    실패하면 fallback_json(dict)에서 corp_code 키를 찾는 폴백 수행.
    """
    if isinstance(text, str):
        m = CORP_CODE_PAT.search(text)
        if m:
            return m.group(0)
    if isinstance(fallback_json, dict):
        v = fallback_json.get("corp_code")
        if isinstance(v, str) and CORP_CODE_PAT.fullmatch(v):
            return v
    raise ValueError(f"corp_code not found in LLM output: {text}")

# ──────────────────────────────────────────────────────────────────────────────
# BaseReWOO
# ──────────────────────────────────────────────────────────────────────────────

class BaseReWOO:
    def __init__(self, name: str, planner_prompt: str, model_name: str = "gpt-4o"):
        self.name = name
        self.model = ChatOpenAI(api_key=OPENAI_API_KEY, model=model_name)
        self.planner = ChatPromptTemplate.from_messages([("user", planner_prompt)]) | self.model

        # MCP 서버에서 도구 로드
        try:
            mcp_tools = asyncio.run(load_mcp_tools())
        except Exception as e:
            print(f"FATAL: Could not load tools from MCP server: {e}")
            mcp_tools = []

        # LLM을 '도구'로 노출 (문자열 프롬프트를 받아 추출/후처리에 사용)
        llm_tool = Tool(
            name="LLM",
            func=self.model.invoke,  # 입력: str (프롬프트), 출력: AIMessage
            description="Use this to extract a specific value from previous step outputs. Input is the prompt string.",
        )

        all_tools = mcp_tools + [llm_tool]
        self.tool_map = {tool.name: tool for tool in all_tools}

        self.graph = self._build_graph()

    # ── Planner ────────────────────────────────────────────────────────────────
    def _default_steps(self, task: str) -> List[Tuple[str, str, str]]:
        """
        Fallback: task에서 주식명/티커를 추출하여 개별 종목 추세 도구를 1스텝 호출
        """
        from datetime import datetime
        import re as _re

        m = _re.search(r'([0-9A-Z]+\.[A-Z]{2,}|[가-힣]+)', task)
        if not m:
            return []
        stock_name = m.group(1)
        target_date = datetime.now().strftime('%Y%m%d')
        tool_name = "individual_stock_trend"
        tool_input = f"{{'stock_name': '{stock_name}', 'target_date': '{target_date}'}}"
        return [("#E", tool_name, tool_input)]

    def get_plan(self, state: ReWOOState):
        task = state["task"]
        try:
            result = self.planner.invoke({"task": task})
            plan_text = getattr(result, "content", str(result))
        except Exception as e:
            print(f"\n>> ERROR: Planner for agent '{self.name}' failed: {e}")
            _dbg("planner error; fallback to default steps", {"err": str(e)})
            steps_3_tuple = self._default_steps(task)
            steps_4_tuple = [("Plan from default", s[0], s[1], s[2]) for s in steps_3_tuple]
            return {"steps": steps_4_tuple, "plan_string": f"[planner-error] {e}"}

        matches = re.findall(REGEX, plan_text, flags=re.S)
        _dbg("planner output", {"plan_text": plan_text, "n_matches": len(matches)})
        print("\n>> Plan Generated:")
        print(plan_text)

        steps_3_tuple = matches if matches else self._default_steps(task)
        steps_4_tuple = [("MCP Tool Call", s[0], s[1], s[2]) for s in steps_3_tuple]
        return {"steps": steps_4_tuple, "plan_string": plan_text}

    # ── Worker ────────────────────────────────────────────────────────────────
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

        # Unpack the 4-tuple: (plan_desc, step_name, tool_name, tool_input_str)
        _, step_name, tool_name, tool_input_str = state["steps"][step_idx - 1]
        print(f"\n>> Calling Tool: {tool_name} (step {step_idx})")
        print(f"   Input: {tool_input_str}")

        results = dict(state.get("results") or {})

        try:
            tool = self.tool_map.get(tool_name)
            if not tool:
                raise ValueError(f"Tool '{tool_name}' not found.")

            # ── LLM 스텝 ───────────────────────────────────────────────────────
            if tool_name == "LLM":
                # 대괄호 안 문자열을 껍데기 제거 후, #E? 참조를 JSON literal로 주입
                llm_prompt_raw = _strip_wrapping_quotes(tool_input_str)
                llm_prompt_resolved = _resolve_placeholders_to_json_literal(llm_prompt_raw, results)

                # 정확도 향상을 위해 '숫자만' 요청 추가 (필요 시 제거 가능)
                llm_prompt_resolved += "\n\nReturn only the 8-digit corp_code (digits only), no extra text."

                out_msg = tool.invoke(llm_prompt_resolved)  # ChatOpenAI.invoke -> AIMessage
                out_text = getattr(out_msg, "content", str(out_msg))

                # 폴백용: 프롬프트에 등장한 마지막 참조(#E1 등)를 JSON으로 로드해서 전달
                fallback_obj = None
                refs = REF_PAT.findall(llm_prompt_raw)
                if refs:
                    fallback_obj = _maybe_json_loads(results.get(refs[-1]))

                corp_code = _postprocess_corp_code(out_text, fallback_json=fallback_obj)
                results[step_name] = corp_code  # '#E2'에는 오직 '00126380' 같은 원자값만 저장
                out = corp_code

            # ── 일반 도구 ────────────────────────────────────────────────────
            else:
                # 1) #E? 참조를 실제 값(JSON literal)로 치환
                resolved = _resolve_placeholders_to_json_literal(tool_input_str, results)
                # 2) Planner가 단따옴표를 줄 수 있음 → JSON 표준화
                normalized = resolved.replace("'", '"')

                # 3) JSON 파싱
                try:
                    kwargs = json.loads(normalized)

                except Exception as e:
                    raise ValueError(f"Invalid tool input: {tool_input_str} -> {normalized}. Error: {e}")

                if not isinstance(kwargs, dict):
                    raise TypeError("Tool input must be a dictionary.")

                # (선택) 특정 도구 입력 검증 강화
                if tool_name == "get_floating_stock_ratio":
                    cc = kwargs.get("corp_code")
                    if not (isinstance(cc, str) and CORP_CODE_PAT.fullmatch(cc)):
                        raise ValueError("corp_code must be a non-empty string of 8 digits")

                # 4) 호출 (sync 우선, 실패 시 ainvoke 폴백)
                try:
                    out = tool.invoke(kwargs)
                except Exception:
                    try:
                        import anyio
                        out = anyio.run(tool.ainvoke, kwargs)
                    except Exception as e2:
                        raise e2

                # 결과는 가능한 한 '파이썬 객체' 그대로 저장
                results[step_name] = out

        except Exception as e:
            _dbg("tool execution error", {"tool": tool_name, "err": str(e)})
            out = f"[tool-error:{tool_name}] {e}"
            results[step_name] = out  # 오류도 그대로 저장해 Solver가 근거로 보게 함

        # 보기 좋게 출력
        print(f"\n>> Tool Result ({tool_name}):")
        try:
            if isinstance(out, (dict, list)):
                print(json.dumps(out, ensure_ascii=False, indent=2))
            elif isinstance(out, str) and ('{' in out or '[' in out):
                try:
                    parsed_out = json.loads(out)
                    print(json.dumps(parsed_out, ensure_ascii=False, indent=2))
                except Exception:
                    print(out)
            else:
                print(out)
        except Exception:
            print(out)

        return {"results": results}

    # ── Solver ────────────────────────────────────────────────────────────────
    def solve(self, state: ReWOOState):
        plan_display = ""
        for _plan, step_name, tool, tool_input in (state.get("steps") or []):
            # 표시용으로 결과 값을 repr로 주입해서 가독성 향상
            resolved_display_input = tool_input
            results = dict(state.get("results") or {})
            for k, v in results.items():
                resolved_display_input = resolved_display_input.replace(k, repr(_maybe_json_loads(v)))
            plan_display += f"{step_name} = {tool}[{resolved_display_input}]\n"

        solve_prompt = (
            "Solve the following task using the plan and evidence.\n"
            "The evidence is provided below.\n\n"
            f"Plan and Evidence:\n{plan_display}\n"
            f"Task: {state['task']}\nResponse:"
        )
        res = self.model.invoke(solve_prompt)
        return {"result": getattr(res, "content", str(res))}

    # ── Graph wiring ──────────────────────────────────────────────────────────
    def _route(self, state: ReWOOState):
        return "solve" if self._get_current_task(state) is None else "tool"

    def _build_graph(self):
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
