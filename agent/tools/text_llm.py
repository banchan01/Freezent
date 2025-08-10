from langchain_openai import ChatOpenAI

# Generic lightweight LLM tool for summarization/extraction

class LLMTool:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = ChatOpenAI(model=model)

    def __call__(self, prompt: str) -> str:
        return self.model.invoke(prompt).content