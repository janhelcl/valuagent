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


def get_ocr_max_retries() -> int:
    """Return default max OCR retries from env, defaulting to 1 and clamped to 1..5."""
    try:
        value = int(os.getenv("OCR_MAX_RETRIES", "1"))
    except ValueError:
        value = 1
    # Clamp to a reasonable range to avoid abuse
    if value < 1:
        return 1
    if value > 5:
        return 5
    return value

