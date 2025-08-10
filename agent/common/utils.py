import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
DART_API_KEY = os.getenv("DART_API_KEY", "")
UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY", "")