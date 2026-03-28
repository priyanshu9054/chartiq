from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

LLM_CONFIG = {
    "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    "api_key": os.getenv("OPENAI_API_KEY", "YOUR_API_KEY"),
    "model": "gpt-4.1-mini",
}

def get_llm_client():
    return OpenAI(base_url=LLM_CONFIG["base_url"], api_key=LLM_CONFIG["api_key"])
