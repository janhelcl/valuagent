from typing import Optional


def generate_json_from_pdf(pdf_bytes: bytes, prompt: str, model: Optional[str] = None, api_key: Optional[str] = None) -> str:
    from google import genai
    from google.genai import types
    from src.infrastructure import config

    api_key = api_key or config.get_api_key()
    model = model or config.get_model()

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            prompt,
        ],
        config={
            "response_mime_type": "application/json",
        },
    )
    return response.text or ""


