import io
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

import openpyxl

logger = logging.getLogger(__name__)


def load_predmet_oceneni_mapping() -> Dict[str, Dict[str, str]]:
    """Load the cell mapping for Předmět ocenění sheet."""
    resources_dir = Path(__file__).resolve().parent.parent / "resources"
    mapping_path = resources_dir / "predmet_oceneni_mapping.json"
    
    try:
        with mapping_path.open("r", encoding="utf-8") as f:
            mapping = json.load(f)
        logger.info(f"Loaded predmet_oceneni_mapping.json with {len(mapping)} row mappings")
        return mapping
    except FileNotFoundError:
        logger.error(f"Mapping file not found: {mapping_path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in mapping file: {e}")
        return {}


def find_latest_balance_sheet(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Find the balance sheet result with the latest year."""
    balance_sheets = [r for r in results if r["statement_type"] == "rozvaha"]
    
    if not balance_sheets:
        raise ValueError("No balance sheet found in results")
    
    # Sort by year (rok) in descending order
    balance_sheets.sort(key=lambda x: getattr(x["model"], "rok", 0), reverse=True)
    latest = balance_sheets[0]
    
    latest_year = getattr(latest["model"], "rok", "unknown")
    logger.info(f"Using latest balance sheet from year {latest_year} (from file: {latest['original']})")
    
    return latest


def fill_predmet_oceneni_sheet(workbook: openpyxl.Workbook, balance_sheet_result: Dict[str, Any]) -> None:
    """Fill the Předmět ocenění sheet with balance sheet data."""
    sheet_name = "Předmět oce"
    
    if sheet_name not in workbook.sheetnames:
        logger.error(f"Sheet '{sheet_name}' not found in template. Available sheets: {workbook.sheetnames}")
        raise ValueError(f"Sheet '{sheet_name}' not found in template")
    
    sheet = workbook[sheet_name]
    mapping = load_predmet_oceneni_mapping()
    
    if not mapping:
        logger.warning("No mapping data available, skipping sheet fill")
        return
    
    balance_sheet = balance_sheet_result["model"]
    balance_data = getattr(balance_sheet, "data", {})
    
    filled_count = 0
    missing_count = 0
    
    logger.info(f"Filling {sheet_name} sheet with {len(balance_data)} balance sheet rows")
    
    for row_id, row_data in balance_data.items():
        row_id_str = str(row_id)
        
        if row_id_str not in mapping:
            logger.debug(f"Row ID {row_id} not found in mapping, skipping")
            missing_count += 1
            continue
        
        cell_mapping = mapping[row_id_str]
        row_name = cell_mapping.get("name", f"Row {row_id}")
        
        try:
            # Fill brutto value if mapping and data exist
            if "brutto" in cell_mapping and hasattr(row_data, "brutto") and row_data.brutto is not None:
                brutto_cell = cell_mapping["brutto"]
                sheet[brutto_cell] = row_data.brutto
                logger.debug(f"Set {brutto_cell} = {row_data.brutto} (brutto for {row_name})")
            
            # Fill korekce value if mapping and data exist
            if "korekce" in cell_mapping and hasattr(row_data, "korekce") and row_data.korekce is not None:
                korekce_cell = cell_mapping["korekce"]
                sheet[korekce_cell] = row_data.korekce
                logger.debug(f"Set {korekce_cell} = {row_data.korekce} (korekce for {row_name})")
            
            # Fill netto value if mapping and data exist (for equity/liability rows)
            if "netto" in cell_mapping and hasattr(row_data, "netto"):
                netto_cell = cell_mapping["netto"]
                sheet[netto_cell] = row_data.netto
                logger.debug(f"Set {netto_cell} = {row_data.netto} (netto for {row_name})")
            
            filled_count += 1
            
        except Exception as e:
            logger.error(f"Error filling row {row_id} ({row_name}): {e}")
            continue
    
    logger.info(f"Successfully filled {filled_count} rows in {sheet_name} sheet, {missing_count} rows not mapped")


def export_dcf_template(results: List[Dict[str, Any]]) -> io.BytesIO:
    """Export results to DCF template, filling Předmět ocenění sheet with latest balance sheet data."""
    logger.info(f"Creating DCF template export from {len(results)} results")
    
    # Load the template
    resources_dir = Path(__file__).resolve().parent.parent / "resources"
    template_path = resources_dir / "DCF.xlsx"
    
    if not template_path.exists():
        raise FileNotFoundError(f"DCF template not found: {template_path}")
    
    logger.info(f"Loading DCF template from {template_path}")
    workbook = openpyxl.load_workbook(template_path)
    logger.debug(f"Template loaded with sheets: {workbook.sheetnames}")
    
    # Find the latest balance sheet
    try:
        latest_balance_sheet = find_latest_balance_sheet(results)
    except ValueError as e:
        logger.error(f"Cannot create DCF export: {e}")
        raise
    
    # Fill Předmět ocenění sheet
    fill_predmet_oceneni_sheet(workbook, latest_balance_sheet)
    
    # Save to BytesIO buffer
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    
    logger.info(f"DCF template export completed, buffer size: {buffer.getbuffer().nbytes/1024:.1f}KB")
    return buffer
