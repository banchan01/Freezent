from langchain_community.tools.tavily_search import TavilySearchResults
from typing import Any, List

# Wrap Tavily as our search tool (you can swap with DDG/SerpAPI)

class NewsSearchTool:
    def __init__(self):
        self.search = TavilySearchResults(max_results=5)

    def __call__(self, query: str) -> List[Any]:
        return self.search.invoke(query)