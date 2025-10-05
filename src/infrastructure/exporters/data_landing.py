"""
Data Landing Exporter

This module fills financial statement data into a user-provided Excel template.
The user's Excel file contains pre-configured sheets with formulas and structure.
This exporter only fills in the raw data values and dates.

- Data - Rozvaha: Fill numerical values and dates
  * AKTIVA section: Fills Brutto, Korekce, Netto values
  * PASIVA section: Fills Netto values only
  * Dates are filled in dd.mm.yyyy format at the top of columns
  * Only data values are filled - structure is pre-filled by user

- Data - Report Kvality: Quality report with validation results

The user uploads their Excel template along with PDFs, and we fill in the data.
"""

import io
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)


def load_balance_sheet_structure() -> Dict[int, Dict[str, Any]]:
    """Load the balance sheet structure with row labels and descriptions."""
    resources_dir = Path(__file__).resolve().parent.parent / "resources"
    index_path = resources_dir / "balance_sheet_index.json"
    
    try:
        with index_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Flatten structure to get row_id -> name mapping
        flat = {}
        def walk(node: dict, parent_label: str = ""):
            for key_str, value in node.items():
                try:
                    key_int = int(key_str)
                except ValueError:
                    continue
                name = value.get("name")
                if isinstance(name, str):
                    flat[key_int] = {"name": name, "label": parent_label}
                sub = value.get("sub_rows")
                if isinstance(sub, dict):
                    walk(sub, parent_label)
        
        walk(data)
        return flat
    except FileNotFoundError:
        logger.error(f"Balance sheet index not found: {index_path}")
        return {}


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


def get_row_number_column() -> int:
    """Return the fixed column for row numbers (ř.) - always column D."""
    return 4  # Column D


def get_data_start_column() -> int:
    """Return the fixed column where data starts - always column E."""
    return 5  # Column E (after column D)


def fill_rozvaha_sheet(workbook: openpyxl.Workbook, balance_sheet_results: List[Dict[str, Any]]) -> None:
    """Fill numerical data and dates into existing Data - Rozvaha sheet."""
    sheet_name = "Data - Rozvaha"
    
    if sheet_name not in workbook.sheetnames:
        logger.error(f"Sheet '{sheet_name}' not found in template. Available sheets: {workbook.sheetnames}")
        raise ValueError(f"Sheet '{sheet_name}' not found in uploaded template")
    
    sheet = workbook[sheet_name]
    
    if not balance_sheet_results:
        logger.warning("No balance sheet results available for Data - Rozvaha sheet")
        return
    
    # Limit to 7 years
    balance_sheet_results = balance_sheet_results[:7]
    
    # Fixed columns: D for row numbers, E for data start
    row_num_col = get_row_number_column()  # Column D
    data_start_col = get_data_start_column()  # Column E
    
    logger.info(f"Filling {sheet_name} with {len(balance_sheet_results)} years starting at column {data_start_col} (row numbers in column {row_num_col})")
    
    # Fill dates in row 1 (dd.mm.yyyy format)
    col_index = data_start_col
    year_to_columns = {}  # Map year to list of column indices
    
    for bs_result in balance_sheet_results:
        model = bs_result.get("model")
        year = getattr(model, "rok", "")
        
        if not year:
            continue
        
        # Create date string in dd.mm.yyyy format (31.12.YYYY)
        date_str = f"31.12.{year}"
        
        # Store column positions for this year
        year_columns = []
        
        # AKTIVA section: 3 columns per year (Brutto, Korekce, Netto)
        # Fill the same date for all 3 columns
        for i in range(3):
            sheet.cell(row=1, column=col_index, value=date_str)
            year_columns.append(col_index)
            col_index += 1
        
        year_to_columns[year] = year_columns
        logger.debug(f"Set dates for year {year} in columns {year_columns}")
    
    # Create a mapping of row_number -> sheet_row for efficient lookup
    # Scan the row number column to find where each row ID is located
    row_id_to_sheet_row = {}
    for row_idx in range(3, sheet.max_row + 1):
        cell_value = sheet.cell(row=row_idx, column=row_num_col).value
        if cell_value is not None:
            try:
                # Convert to integer (handles both int and string representations)
                row_id = int(cell_value)
                if row_id > 0:
                    row_id_to_sheet_row[row_id] = row_idx
            except (ValueError, TypeError):
                pass
    
    logger.info(f"Found {len(row_id_to_sheet_row)} row mappings in template: {list(row_id_to_sheet_row.keys())[:10]}...")
    logger.info(f"Year to columns mapping: {year_to_columns}")
    
    # Fill data for each year
    total_filled = 0
    for year, columns in year_to_columns.items():
        bs_result = None
        for result in balance_sheet_results:
            if getattr(result.get("model"), "rok", None) == year:
                bs_result = result
                break
        
        if not bs_result:
            logger.warning(f"No balance sheet result found for year {year}")
            continue
        
        model = bs_result.get("model")
        if not model:
            logger.warning(f"No model found for year {year}")
            continue
        
        logger.info(f"Processing year {year} with {len(model.data)} rows")
        
        # columns = [brutto_col, korekce_col, netto_col]
        brutto_col, korekce_col, netto_col = columns
        logger.info(f"Using columns for year {year}: Brutto={brutto_col}, Korekce={korekce_col}, Netto={netto_col}")
        
        filled_count = 0
        skipped_count = 0
        for row_id, row_data in model.data.items():
            # Find which Excel row corresponds to this row_id
            if row_id not in row_id_to_sheet_row:
                logger.debug(f"Row ID {row_id} not found in template, skipping")
                skipped_count += 1
                continue
            
            excel_row = row_id_to_sheet_row[row_id]
            logger.debug(f"  Processing row_id={row_id} -> excel_row={excel_row}")
            
            # Determine if this is AKTIVA or PASIVA
            # AKTIVA (< 78): Fill Brutto, Korekce, Netto
            # PASIVA (>= 78): Fill only Netto (in the third column position)
            
            if row_id < 78:
                # AKTIVA section - fill all 3 columns
                # Brutto
                brutto_val = getattr(row_data, "brutto", None)
                if brutto_val is not None:
                    sheet.cell(row=excel_row, column=brutto_col, value=brutto_val)
                    logger.debug(f"  Filled row {row_id} Brutto at ({excel_row}, {brutto_col}): {brutto_val}")
                
                # Korekce (as negative)
                korekce_val = getattr(row_data, "korekce", None)
                if korekce_val is not None:
                    try:
                        korekce_val = -abs(int(korekce_val))
                    except Exception:
                        pass
                    sheet.cell(row=excel_row, column=korekce_col, value=korekce_val)
                    logger.debug(f"  Filled row {row_id} Korekce at ({excel_row}, {korekce_col}): {korekce_val}")
                
                # Netto
                netto_val = getattr(row_data, "netto", None)
                if netto_val is not None:
                    sheet.cell(row=excel_row, column=netto_col, value=netto_val)
                    logger.debug(f"  Filled row {row_id} Netto at ({excel_row}, {netto_col}): {netto_val}")
                
                filled_count += 1
            else:
                # PASIVA section - fill only Netto column
                netto_val = getattr(row_data, "netto", None)
                if netto_val is not None:
                    # For PASIVA, use the netto column position
                    sheet.cell(row=excel_row, column=netto_col, value=netto_val)
                    logger.debug(f"  Filled PASIVA row {row_id} Netto at ({excel_row}, {netto_col}): {netto_val}")
                filled_count += 1
        
        logger.info(f"Year {year}: Filled {filled_count} rows, Skipped {skipped_count} rows (not in template)")
        total_filled += filled_count
    
    logger.info(f"Successfully filled {sheet_name} sheet: {total_filled} total values")


def fill_quality_report_sheet(workbook: openpyxl.Workbook, results: List[Dict[str, Any]], inter_issues: List[str], tolerance: int) -> None:
    """Fill or create the Data - Report Kvality sheet with quality information."""
    sheet_name = "Data - Report Kvality"
    
    if sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        logger.info(f"Found existing '{sheet_name}' sheet, clearing and filling with data")
        # Clear existing content
        for row in sheet.iter_rows():
            for cell in row:
                cell.value = None
    else:
        logger.info(f"Creating new '{sheet_name}' sheet")
        sheet = workbook.create_sheet(sheet_name)
    
    # Header
    sheet["A1"] = "Kvalita dat"
    sheet["A1"].font = Font(bold=True, size=14)
    sheet["A2"] = f"Tolerance: {tolerance}"
    
    # Overview table
    headers = ["Soubor", "Výkaz", "Rok", "Pokusy OCR", "Status", "Počet problémů"]
    for col, h in enumerate(headers, start=1):
        cell = sheet.cell(row=4, column=col, value=h)
        cell.font = Font(bold=True)
    
    row = 5
    for r in results:
        file_name = r.get("original")
        st = r.get("statement_type")
        model = r.get("model")
        rok = getattr(model, "rok", None) if model is not None else (r.get("raw") or {}).get("rok")
        attempts = r.get("ocr_attempts", 1)
        status = r.get("status", "ok")
        err_count = len(r.get("validation_errors") or [])
        values = [file_name, st, rok, attempts, "OK" if status == "ok" else "Chyby", err_count]
        for col, v in enumerate(values, start=1):
            sheet.cell(row=row, column=col, value=v)
        row += 1
    
    # Statement-level problems
    start = row + 1
    sheet.cell(row=start, column=1, value="Problémy ve výkazech (po opakování OCR)").font = Font(bold=True)
    row = start + 1
    
    found_errors = False
    for r in results:
        errs = r.get("validation_errors") or []
        if not errs:
            continue
        found_errors = True
        file_name = r.get("original")
        st = r.get("statement_type")
        model = r.get("model")
        rok = getattr(model, "rok", None) if model is not None else (r.get("raw") or {}).get("rok")
        sheet.cell(row=row, column=1, value=f"Soubor: {file_name}")
        sheet.cell(row=row, column=2, value=f"Výkaz: {st}")
        sheet.cell(row=row, column=3, value=f"Rok: {rok}")
        row += 1
        for msg in errs:
            sheet.cell(row=row, column=2, value=msg)
            row += 1
        row += 1
    
    if not found_errors:
        sheet.cell(row=row, column=1, value="Žádné problémy")
        row += 2
    
    # Interstatement issues
    sheet.cell(row=row, column=1, value="Problémy mezi výkazy a mezi roky").font = Font(bold=True)
    row += 1
    if inter_issues:
        for msg in inter_issues:
            sheet.cell(row=row, column=1, value=msg)
            row += 1
    else:
        sheet.cell(row=row, column=1, value="Žádné problémy")
        row += 1
    
    logger.info(f"Successfully created {sheet_name} sheet")


def export_data_landing(results: List[Dict[str, Any]], template_bytes: bytes, tolerance: int = 1) -> io.BytesIO:
    """
    Fill financial data into user-provided Excel template.
    
    Args:
        results: Processed financial statement results
        template_bytes: User's Excel template file as bytes
        tolerance: Validation tolerance
    
    Returns:
        BytesIO buffer with filled Excel file
    """
    logger.info(f"Filling data landing template with {len(results)} results")
    
    # Load the user's template
    template_buffer = io.BytesIO(template_bytes)
    workbook = openpyxl.load_workbook(template_buffer)
    logger.info(f"Loaded template with sheets: {workbook.sheetnames}")
    
    # Get sorted balance sheets
    sorted_balance_sheets = get_sorted_balance_sheets(results)
    
    if sorted_balance_sheets:
        fill_rozvaha_sheet(workbook, sorted_balance_sheets)
    else:
        logger.warning("No balance sheet data found in results")
    
    # TODO: Fill Data - Výsledovka sheet when implemented
    
    # Fill quality report
    try:
        from src.services.quality import validate_interstatement
        inter_issues = validate_interstatement(results, tolerance)
        fill_quality_report_sheet(workbook, results, inter_issues, tolerance)
    except Exception as e:
        logger.error(f"Failed to fill quality report: {e}", exc_info=True)
    
    # Save to BytesIO buffer
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    
    logger.info(f"Data landing export completed, buffer size: {buffer.getbuffer().nbytes/1024:.1f}KB")
    return buffer

