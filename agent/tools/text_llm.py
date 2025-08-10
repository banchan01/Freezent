# tools/text_llm.py
from __future__ import annotations
import os
import traceback

USE_MOCK_LLM = os.getenv("MOCK_LLM", "false").lower() == "true"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


def _dbg(msg: str):
    if DEBUG:
        print(f"[llm_tool] {msg}")


class LLMTool:
    def __init__(self, model: str = "gpt-4o-mini"):
        self._use_mock = USE_MOCK_LLM
        if not self._use_mock:
            from langchain_openai import ChatOpenAI
            self.model = ChatOpenAI(model=model)
        else:
            self.model = None

    def __call__(self, prompt: str) -> str:
        if self._use_mock:
            return "[LLMTool:mock] summary suppressed in MOCK_LLM mode."
        try:
            _dbg(f"invoke len={len(prompt)}")
            return self.model.invoke(prompt).content
        except Exception as e:
            _dbg(f"error: {e}\n{traceback.format_exc()}")
            return "[LLMTool] 요약 실패(임시 메시지). 추후 재시도 바랍니다."
