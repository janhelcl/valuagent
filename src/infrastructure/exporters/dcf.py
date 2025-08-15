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


def load_rozvaha_mapping() -> Dict[str, Dict[str, str]]:
    """Load the row mapping for Rozvaha sheet."""
    resources_dir = Path(__file__).resolve().parent.parent / "resources"
    mapping_path = resources_dir / "rozvaha_mapping.json"
    
    try:
        with mapping_path.open("r", encoding="utf-8") as f:
            mapping = json.load(f)
        logger.info(f"Loaded rozvaha_mapping.json with {len(mapping)} row mappings")
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


def get_sorted_balance_sheets(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get all balance sheets sorted by year (newest first)."""
    balance_sheets = [r for r in results if r["statement_type"] == "rozvaha"]
    
    if not balance_sheets:
        return []
    
    # Sort by year (rok) in descending order (newest first)
    balance_sheets.sort(key=lambda x: getattr(x["model"], "rok", 0), reverse=True)
    
    years = [getattr(bs["model"], "rok", "unknown") for bs in balance_sheets]
    logger.info(f"Found {len(balance_sheets)} balance sheets for years: {years}")
    
    return balance_sheets


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


def fill_rozvaha_sheet(workbook: openpyxl.Workbook, balance_sheet_results: List[Dict[str, Any]]) -> None:
    """Fill the Rozvaha sheet with multiple years of balance sheet data."""
    sheet_name = "Rozvaha"
    
    if sheet_name not in workbook.sheetnames:
        logger.error(f"Sheet '{sheet_name}' not found in template. Available sheets: {workbook.sheetnames}")
        raise ValueError(f"Sheet '{sheet_name}' not found in template")
    
    sheet = workbook[sheet_name]
    mapping = load_rozvaha_mapping()
    
    if not mapping:
        logger.warning("No Rozvaha mapping data available, skipping sheet fill")
        return
    
    if not balance_sheet_results:
        logger.warning("No balance sheet results available for Rozvaha sheet")
        return
    
    # Column mapping: I = 2nd latest, H = 3rd latest, G = 4th latest, F = 5th latest
    year_columns = ['I', 'H', 'G', 'F']
    max_years = len(year_columns)
    
    # Skip the latest year (already in Předmět ocenění), take up to 4 historical years
    historical_balance_sheets = balance_sheet_results[1:max_years+1]
    
    if not historical_balance_sheets:
        logger.info("No historical balance sheet data available for Rozvaha sheet")
        return
    
    logger.info(f"Filling Rozvaha sheet with {len(historical_balance_sheets)} historical years")
    
    # Fill year headers in row 3
    for i, balance_sheet_result in enumerate(historical_balance_sheets):
        column = year_columns[i]
        year = getattr(balance_sheet_result["model"], "rok", "")
        year_cell = f"{column}3"
        sheet[year_cell] = year
        logger.debug(f"Set year header {year_cell} = {year}")
    
    # Fill data for each year
    total_filled = 0
    total_missing = 0
    
    for year_idx, balance_sheet_result in enumerate(historical_balance_sheets):
        column = year_columns[year_idx]
        balance_sheet = balance_sheet_result["model"]
        balance_data = getattr(balance_sheet, "data", {})
        year = getattr(balance_sheet, "rok", "unknown")
        
        filled_count = 0
        missing_count = 0
        
        logger.debug(f"Filling column {column} with year {year} data ({len(balance_data)} rows)")
        
        for row_id, row_data in balance_data.items():
            row_id_str = str(row_id)
            
            if row_id_str not in mapping:
                logger.debug(f"Row ID {row_id} not found in Rozvaha mapping, skipping")
                missing_count += 1
                continue
            
            cell_mapping = mapping[row_id_str]
            row_name = cell_mapping.get("name", f"Row {row_id}")
            excel_row = cell_mapping.get("netto")
            
            if not excel_row:
                logger.warning(f"No row mapping found for row ID {row_id}")
                missing_count += 1
                continue
            
            try:
                # Fill netto value
                if hasattr(row_data, "netto"):
                    cell_address = f"{column}{excel_row}"
                    sheet[cell_address] = row_data.netto
                    logger.debug(f"Set {cell_address} = {row_data.netto} (netto for {row_name})")
                    filled_count += 1
                else:
                    logger.debug(f"No netto value for row {row_id} ({row_name})")
                    missing_count += 1
                    
            except Exception as e:
                logger.error(f"Error filling row {row_id} ({row_name}) in column {column}: {e}")
                missing_count += 1
                continue
        
        logger.info(f"Column {column} (year {year}): filled {filled_count} rows, {missing_count} missing")
        total_filled += filled_count
        total_missing += missing_count
    
    logger.info(f"Successfully filled Rozvaha sheet: {total_filled} total values, {total_missing} total missing")


def export_dcf_template(results: List[Dict[str, Any]]) -> io.BytesIO:
    """Export results to DCF template, filling Předmět ocenění and Rozvaha sheets."""
    logger.info(f"Creating DCF template export from {len(results)} results")
    
    # Load the template
    resources_dir = Path(__file__).resolve().parent.parent / "resources"
    template_path = resources_dir / "DCF.xlsx"
    
    if not template_path.exists():
        raise FileNotFoundError(f"DCF template not found: {template_path}")
    
    logger.info(f"Loading DCF template from {template_path}")
    workbook = openpyxl.load_workbook(template_path)
    logger.debug(f"Template loaded with sheets: {workbook.sheetnames}")
    
    # Get all balance sheets sorted by year (newest first)
    sorted_balance_sheets = get_sorted_balance_sheets(results)
    
    if not sorted_balance_sheets:
        logger.error("No balance sheet data found in results")
        raise ValueError("No balance sheet data found in results")
    
    # Fill Předmět ocenění sheet with latest year
    latest_balance_sheet = sorted_balance_sheets[0]
    fill_predmet_oceneni_sheet(workbook, latest_balance_sheet)
    
    # Fill Rozvaha sheet with historical years (skip latest)
    if len(sorted_balance_sheets) > 1:
        fill_rozvaha_sheet(workbook, sorted_balance_sheets)
    else:
        logger.info("Only one balance sheet year available, skipping Rozvaha sheet historical data")
    
    # Save to BytesIO buffer
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    
    logger.info(f"DCF template export completed, buffer size: {buffer.getbuffer().nbytes/1024:.1f}KB")
    return buffer
