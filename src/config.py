import os
from dotenv import load_dotenv

load_dotenv()

def get_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing GOOGLE_API_KEY/GENAI_API_KEY")
    return key

def get_model() -> str:
    return os.getenv("GENAI_MODEL", "gemini-2.5-pro")
