from tools.filings_api import FilingsTool
from tools.text_llm import LLMTool

class FilingsWorkers:
    def __init__(self):
        self.filings = FilingsTool()
        self.llm = LLMTool()