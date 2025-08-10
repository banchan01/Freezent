from tools.news_search import NewsSearchTool
from tools.text_llm import LLMTool

class NewsWorkers:
    def __init__(self):
        self.google = NewsSearchTool()
        self.llm = LLMTool()