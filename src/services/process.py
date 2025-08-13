import json
from typing import Any, Dict

from fastapi import HTTPException

from src.domain.prompts.balance_sheet import balance_sheet_ocr_instructions
from src.domain.prompts.profit_and_loss import profit_and_loss_ocr_instructions
from src.domain.models.balance_sheet import BalanceSheet
from src.domain.models.profit_and_loss import ProfitAndLoss
from src.infrastructure.clients.genai_client import generate_json_from_pdf
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
