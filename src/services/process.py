import json
import logging
from typing import Any, Dict

from fastapi import HTTPException

logger = logging.getLogger(__name__)

from src.domain.prompts.balance_sheet import balance_sheet_ocr_instructions
from src.domain.prompts.profit_and_loss import profit_and_loss_ocr_instructions
from src.domain.prompts.statement_disambiguation import (
    statement_disambiguation_instructions,
)
from src.domain.models.balance_sheet import BalanceSheet
from src.domain.models.profit_and_loss import ProfitAndLoss
from src.infrastructure.clients.genai_client import generate_json_from_pdf, generate_json_from_pdf_async
from src.shared import utils


def pick_prompt(statement_type: str) -> str:
    if statement_type == "rozvaha":
        return balance_sheet_ocr_instructions
    if statement_type in {"vzz", "ziskaztrata", "vzzcz"}:
        return profit_and_loss_ocr_instructions
    raise HTTPException(status_code=400, detail="Unsupported statement_type. Use 'rozvaha' or 'vzz'.")


def validate_payload(statement_type: str, data_dict: Dict[str, Any], tolerance: int):
    if statement_type == "rozvaha":
        return BalanceSheet.model_validate_with_tolerance(data_dict, tolerance=tolerance)
    return ProfitAndLoss.model_validate_with_tolerance(data_dict, tolerance=tolerance)


def process_pdf_bytes(pdf_bytes: bytes, statement_type: str, tolerance: int):
    prompt = pick_prompt(statement_type)
    text_response = generate_json_from_pdf(pdf_bytes, prompt)
    if not text_response:
        raise HTTPException(status_code=500, detail="Empty response from model")

    try:
        data_dict = json.loads(text_response)
    except json.JSONDecodeError:
        data_dict = utils.load_json_from_text(text_response)


    model_obj = validate_payload(statement_type, data_dict, tolerance)
    return model_obj


def disambiguate_pdf_bytes(pdf_bytes: bytes) -> dict:
    """Use the disambiguation prompt to determine which statements are present.

    Returns a dict like:
    {
        "rozvaha": bool,
        "vzz": bool,
        "datum": Optional[str],
    }
    """
    text_response = generate_json_from_pdf(
        pdf_bytes, statement_disambiguation_instructions
    )
    if not text_response:
        raise HTTPException(status_code=500, detail="Empty response from model (disambiguation)")

    try:
        data = json.loads(text_response)
    except json.JSONDecodeError:
        data = utils.load_json_from_text(text_response)

    # Normalize possible Czech keys and booleans
    rozvaha = False
    vzz = False
    datum = None

    for key, value in (data or {}).items():
        normalized_key = str(key).strip().lower()
        if normalized_key in {"rozvaha"}:
            rozvaha = bool(value)
        if normalized_key in {"výkaz_zisku_a_ztráty", "vykaz_zisku_a_ztraty", "vzz"}:
            vzz = bool(value)
        if normalized_key in {"datum", "date"} and isinstance(value, str):
            datum = value

    return {"rozvaha": rozvaha, "vzz": vzz, "datum": datum}


# Async variants
async def process_pdf_bytes_async(pdf_bytes: bytes, statement_type: str, tolerance: int):
    logger.info(f"Processing PDF for statement type: {statement_type}, tolerance: {tolerance}")
    
    prompt = pick_prompt(statement_type)
    logger.debug(f"Using prompt for {statement_type}, length: {len(prompt)} chars")
    
    text_response = await generate_json_from_pdf_async(pdf_bytes, prompt)
    if not text_response:
        logger.error("Empty response from model")
        raise HTTPException(status_code=500, detail="Empty response from model")

    logger.debug("Parsing JSON response from model")
    try:
        data_dict = json.loads(text_response)
        logger.debug(f"JSON parsed successfully, keys: {list(data_dict.keys()) if isinstance(data_dict, dict) else 'not a dict'}")
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode failed: {e}, attempting fallback parsing")
        data_dict = utils.load_json_from_text(text_response)

    logger.info(f"Validating {statement_type} data with tolerance {tolerance}")
    model_obj = validate_payload(statement_type, data_dict, tolerance)
    
    # Log some basic stats about the parsed data
    if hasattr(model_obj, 'data') and hasattr(model_obj, 'rok'):
        row_count = len(model_obj.data) if model_obj.data else 0
        logger.info(f"Successfully processed {statement_type} for year {model_obj.rok} with {row_count} rows")
    
    return model_obj


async def disambiguate_pdf_bytes_async(pdf_bytes: bytes) -> dict:
    """Async version of disambiguation using the new SDK."""
    logger.info("Starting PDF statement disambiguation")
    
    text_response = await generate_json_from_pdf_async(
        pdf_bytes, statement_disambiguation_instructions
    )
    if not text_response:
        logger.error("Empty response from disambiguation model")
        raise HTTPException(status_code=500, detail="Empty response from model (disambiguation)")

    logger.debug("Parsing disambiguation response")
    try:
        data = json.loads(text_response)
        logger.debug(f"Disambiguation JSON parsed: {data}")
    except json.JSONDecodeError as e:
        logger.warning(f"Disambiguation JSON decode failed: {e}, attempting fallback parsing")
        data = utils.load_json_from_text(text_response)

    # Normalize possible Czech keys and booleans
    rozvaha = False
    vzz = False
    datum = None

    for key, value in (data or {}).items():
        normalized_key = str(key).strip().lower()
        if normalized_key in {"rozvaha"}:
            rozvaha = bool(value)
        if normalized_key in {"výkaz_zisku_a_ztráty", "vykaz_zisku_a_ztraty", "vzz"}:
            vzz = bool(value)
        if normalized_key in {"datum", "date"} and isinstance(value, str):
            datum = value

    result = {"rozvaha": rozvaha, "vzz": vzz, "datum": datum}
    logger.info(f"Disambiguation completed: {result}")
    return result
