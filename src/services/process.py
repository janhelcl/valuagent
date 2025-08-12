import json
from typing import Any, Dict

from fastapi import HTTPException

from src import prompts, schemas, utils
from src.clients.genai_client import generate_json_from_pdf


def pick_prompt(statement_type: str) -> str:
    if statement_type == "rozvaha":
        return prompts.balance_sheet_ocr_instructions
    if statement_type in {"vzz", "ziskaztrata", "vzzcz"}:
        return prompts.profit_and_loss_ocr_instructions
    raise HTTPException(status_code=400, detail="Unsupported statement_type. Use 'rozvaha' or 'vzz'.")


def validate_payload(statement_type: str, data_dict: Dict[str, Any], tolerance: int):
    if statement_type == "rozvaha":
        return schemas.BalanceSheet.model_validate_with_tolerance(data_dict, tolerance=tolerance)
    return schemas.ProfitAndLoss.model_validate_with_tolerance(data_dict, tolerance=tolerance)


def process_pdf_bytes(pdf_bytes: bytes, statement_type: str, year: int, tolerance: int):
    prompt = pick_prompt(statement_type)
    text_response = generate_json_from_pdf(pdf_bytes, prompt)
    if not text_response:
        raise HTTPException(status_code=500, detail="Empty response from model")

    try:
        data_dict = json.loads(text_response)
    except json.JSONDecodeError:
        data_dict = utils.load_json_from_text(text_response)

    data_dict.setdefault("rok", year)
    model_obj = validate_payload(statement_type, data_dict, tolerance)
    return model_obj
