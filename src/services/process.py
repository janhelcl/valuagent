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
from src.domain.models.balance_sheet import BalanceSheet, BalanceSheetRow
from src.domain.models.profit_and_loss import ProfitAndLoss, ProfitAndLossRow
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


def _format_validation_error(error_msg: str, statement_type: str, tolerance: int | None = None) -> list[str]:
    """Convert technical validation error text into a list of short Czech messages.

    The returned list is suitable for presenting to finance users (e.g., in Excel).
    """
    from src.shared import utils
    import re

    # Load row names for the given statement
    if statement_type == "rozvaha":
        row_names = utils.load_balance_sheet_row_names()
        statement_label = "Rozvaha"
    else:
        row_names = utils.load_profit_and_loss_row_names()
        statement_label = "Výsledovka"

    # Trim common Pydantic boilerplate and keep only the core list of issues
    core = error_msg
    # Keep text after our explicit failure marker if present
    for marker in ("Balance sheet validation failed:", "Profit and loss validation failed:"):
        if marker in core:
            core = core.split(marker, 1)[1]
            break
    # Remove Pydantic headers/footers
    core = re.sub(r"\s*\[type=.*?\]", "", core)
    core = re.sub(r"For further information visit .*", "", core)

    issues: list[str] = []

    # Split by lines, consider only those that look like rule messages
    lines = [ln.strip(" -\t\n") for ln in core.splitlines() if ln.strip()]

    # Helpers
    def with_row(num: int) -> str:
        return f"ř. {num} ({row_names.get(num, str(num))})"

    def finalize(msg: str, diff: str | None) -> str:
        if diff and tolerance is not None:
            return f"{msg}. Rozdíl {diff} > tolerance {tolerance}."
        if diff:
            return f"{msg}. Rozdíl {diff}."
        return msg

    for ln in lines:
        # Netto rule (Balance sheet)
        m = re.search(r"Rule validation failed for netto: Row (\d+) \(([^)]+)\) != Sum of rows ([^(]+) \(([^)]+)\).*?difference: (\d+)", ln)
        if m:
            target_row = int(m.group(1))
            target_val = m.group(2)
            src_rows = [p.strip() for p in m.group(3).split("+") if p.strip()]
            sum_val = m.group(4)
            diff = m.group(5)
            src_pretty: list[str] = []
            for part in src_rows:
                try:
                    src_pretty.append(with_row(int(part)))
                except Exception:
                    src_pretty.append(part)
            msg = f"{statement_label}, {with_row(target_row)} {target_val} ≠ součet {', '.join(src_pretty)} {sum_val}"
            issues.append(finalize(msg, diff))
            continue

        # Netto_minule rule (Balance sheet previous-year column)
        m = re.search(r"Rule validation failed for netto_minule: Row (\d+) \(([^)]+)\) != Sum of rows ([^(]+) \(([^)]+)\).*?difference: (\d+)", ln)
        if m:
            target_row = int(m.group(1))
            target_val = m.group(2)
            src_rows = [p.strip() for p in m.group(3).split("+") if p.strip()]
            sum_val = m.group(4)
            diff = m.group(5)
            src_pretty: list[str] = []
            for part in src_rows:
                try:
                    src_pretty.append(with_row(int(part)))
                except Exception:
                    src_pretty.append(part)
            msg = f"{statement_label}, {with_row(target_row)} (sl. minulé) {target_val} ≠ součet {', '.join(src_prety)} {sum_val}"
            # fix typo variable name if needed: ensure src_pretty is used
            msg = msg.replace("{', '.join(src_prety)}", ", ".join(src_pretty))
            issues.append(finalize(msg, diff))
            continue

        # Flexible PL rule (with + / - expression)
        m = re.search(r"Flexible rule validation failed for ([^:]+): Row (\d+) \(([^)]+)\) != ([^()]+) \(([^)]+)\).*?difference: (\d+)", ln)
        if m:
            field = m.group(1).strip()
            target_row = int(m.group(2))
            target_val = m.group(3)
            expr = m.group(4).strip()
            calc_val = m.group(5)
            diff = m.group(6)
            # Convert expression like 31+35-34 into pretty row refs
            parts_pretty: list[str] = []
            token = ""
            sign = "+"
            for ch in expr:
                if ch in "+-":
                    if token.strip():
                        try:
                            num = int(token.strip())
                            name = with_row(num)
                        except Exception:
                            name = token.strip()
                        parts_pretty.append(("+" if sign == "+" else "−") + " " + name)
                    sign = ch
                    token = ""
                else:
                    token += ch
            if token.strip():
                try:
                    num = int(token.strip())
                    name = with_row(num)
                except Exception:
                    name = token.strip()
                parts_pretty.append(("+" if sign == "+" else "−") + " " + name)
            expr_pretty = " ".join(p.lstrip("+") for p in parts_pretty).strip()
            msg = f"{statement_label}, {with_row(target_row)} ({field}) {target_val} ≠ {expr_pretty} {calc_val}"
            issues.append(finalize(msg, diff))
            continue

        # Brutto - Korekce row-level rule
        if "Brutto - Korekce validation failed" in ln:
            # Translate straight to Czech; row number is not included in the message
            ln_cz = ln.replace("Brutto - Korekce validation failed:", "Chyba kontroly Brutto − Korekce:")
            # Try to attach difference if present
            m2 = re.search(r"difference: (\d+)", ln)
            diff = m2.group(1) if m2 else None
            issues.append(finalize(f"{statement_label}: {ln_cz}", diff))
            continue

        # Fallback: replace bare Row N with Czech row + name and keep message concise
        def repl(match: re.Match[str]) -> str:
            try:
                return with_row(int(match.group(1)))
            except Exception:
                return match.group(0)
        short = re.sub(r"[Rr]ow (\d+)", repl, ln)
        short = re.sub(r"\s+", " ", short).strip()
        if short:
            issues.append(short)

    # If nothing was parsed, fall back to one trimmed message
    if not issues:
        msg = re.sub(r"\s+", " ", core).strip()
        if msg:
            issues = [msg]

    return issues


async def ocr_and_validate_with_retries(
    pdf_bytes: bytes,
    statement_type: str,
    tolerance: int,
    max_retries: int,
) -> dict:
    """Run OCR and statement-level validation with up to max_retries attempts.

    Returns a result dict containing:
      - statement_type: str
      - model: validated Pydantic model or None
      - raw: last parsed dict or None
      - validation_errors: list[str] (only from final attempt)
      - ocr_attempts: int
      - status: "ok" | "errors"
    """
    attempts = 0
    last_raw = None
    final_validation_errors: list[str] = []

    for attempt in range(1, max_retries + 1):
        attempts = attempt
        logger.info(f"OCR attempt {attempt}/{max_retries} for {statement_type}")
        text_response = await generate_json_from_pdf_async(pdf_bytes, pick_prompt(statement_type))
        if not text_response:
            logger.error("Empty response from model during OCR attempt")
            final_validation_error = "Prázdná odpověď z OCR modelu"
            continue

        try:
            data_dict = json.loads(text_response)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode failed on attempt {attempt}: {e}")
            try:
                data_dict = utils.load_json_from_text(text_response)
            except Exception as e2:
                logger.error(f"Fallback JSON extraction failed: {e2}")
                final_validation_error = "Neplatný JSON z OCR modelu"
                continue

        last_raw = data_dict

        try:
            model_obj = validate_payload(statement_type, data_dict, tolerance)
            logger.info(f"Validation succeeded on attempt {attempt} for {statement_type}")
            return {
                "statement_type": statement_type,
                "model": model_obj,
                "raw": last_raw,
                "validation_errors": [],
                "ocr_attempts": attempts,
                "status": "ok",
            }
        except Exception as e:
            # Pydantic validation error or business rule error
            raw_msg = str(e)
            formatted_list = _format_validation_error(raw_msg, statement_type, tolerance)
            logger.info(f"Validation failed on attempt {attempt}: {raw_msg}")
            final_validation_errors = formatted_list
            # continue to retry

    # All attempts failed; return best-effort model with final error
    best_effort_model = None
    if isinstance(last_raw, dict):
        try:
            # Build a model instance without triggering validators
            def construct_bs(data_dict: dict) -> BalanceSheet:
                data_int = utils.convert_string_keys_to_int(data_dict)
                rows = {}
                for k, v in (data_int.get("data") or {}).items():
                    if isinstance(v, dict):
                        rows[int(k)] = BalanceSheetRow.model_construct(**v)
                rok = data_int.get("rok")
                return BalanceSheet.model_construct(rok=rok, data=rows, tolerance=tolerance)

            def construct_pl(data_dict: dict) -> ProfitAndLoss:
                data_int = utils.convert_string_keys_to_int(data_dict)
                rows = {}
                for k, v in (data_int.get("data") or {}).items():
                    if isinstance(v, dict):
                        rows[int(k)] = ProfitAndLossRow.model_construct(**v)
                rok = data_int.get("rok")
                return ProfitAndLoss.model_construct(rok=rok, data=rows, tolerance=tolerance)

            if statement_type == "rozvaha":
                best_effort_model = construct_bs(last_raw)
            else:
                best_effort_model = construct_pl(last_raw)
        except Exception as e:
            logger.error(f"Failed to construct best-effort model: {e}")

    # Return only the final validation error (the one from the data we're actually using)
    validation_errors = final_validation_errors if final_validation_errors else []
    
    return {
        "statement_type": statement_type,
        "model": best_effort_model,
        "raw": last_raw,
        "validation_errors": validation_errors,
        "ocr_attempts": attempts,
        "status": "errors",
    }
