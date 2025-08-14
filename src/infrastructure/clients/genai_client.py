from typing import Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


def generate_json_from_pdf(pdf_bytes: bytes, prompt: str, model: Optional[str] = None, api_key: Optional[str] = None) -> str:
    """Synchronous wrapper around async function for backward compatibility."""
    return asyncio.run(generate_json_from_pdf_async(pdf_bytes, prompt, model, api_key))


async def generate_json_from_pdf_async(pdf_bytes: bytes, prompt: str, model: Optional[str] = None, api_key: Optional[str] = None) -> str:
    """Async version using the new Google GenAI SDK."""
    from google import genai
    from google.genai import types
    from src.infrastructure import config

    api_key = api_key or config.get_api_key()
    model = model or config.get_model()
    
    pdf_size_kb = len(pdf_bytes) / 1024
    logger.info(f"Starting async OCR request - Model: {model}, PDF size: {pdf_size_kb:.1f}KB")
    
    try:
        client = genai.Client(api_key=api_key)
        logger.debug("GenAI client created successfully")
        
        response = await client.aio.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        
        response_text = response.text or ""
        response_chars = len(response_text)
        logger.info(f"OCR request completed - Response length: {response_chars} chars")
        logger.debug(f"Response preview: {response_text[:200]}...")
        
        return response_text
        
    except Exception as e:
        logger.error(f"OCR request failed: {str(e)}", exc_info=True)
        raise


