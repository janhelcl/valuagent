"""
Data Landing Exporter

This module exports financial statement data in a clean data landing format.
The format is designed for data warehousing and analysis, with separate sheets:

- Data - Rozvaha: Balance sheet data with multiple years
  * AKTIVA section: 3 columns per year (Brutto, Korekce, Netto)
  * PASIVA section: 1 column per year (Netto only)
  * Up to 7 years supported
  * No filling from previous years (only current year data)

- Data - Výsledovka: P&L data (to be implemented)

- Data - Report Kvality: Quality report with validation results

This is an alternative to the DCF template export, focused on clean data structure.
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


def create_rozvaha_sheet(workbook: openpyxl.Workbook, balance_sheet_results: List[Dict[str, Any]]) -> None:
    """Create and fill the Data - Rozvaha sheet with balance sheet data."""
    sheet_name = "Data - Rozvaha"
    
    if sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
    else:
        sheet = workbook.create_sheet(sheet_name)
    
    if not balance_sheet_results:
        logger.warning("No balance sheet results available for Data - Rozvaha sheet")
        return
    
    # Limit to 7 years
    balance_sheet_results = balance_sheet_results[:7]
    
    structure = load_balance_sheet_structure()
    
    # Get all unique row IDs from all balance sheets
    all_row_ids = set()
    for bs_result in balance_sheet_results:
        model = bs_result.get("model")
        if model is not None:
            all_row_ids.update(model.data.keys())
    
    sorted_row_ids = sorted(all_row_ids)
    
    # Determine which rows are in AKTIVA (1-77) vs PASIVA (78+)
    # Based on standard Czech accounting, row 78 starts PASIVA section
    aktiva_rows = [rid for rid in sorted_row_ids if rid < 78]
    pasiva_rows = [rid for rid in sorted_row_ids if rid >= 78]
    
    # Setup columns A, B, C, D (prefilled structure)
    # Row 1: headers
    sheet['C1'] = "v tis. Kč"
    sheet['D1'] = "ř."
    
    # Row 2: sub-headers (will be filled below for data columns)
    # Row 3 starts with AKTIVA CELKEM header
    sheet['B3'] = "AKTIVA CELKEM"
    sheet['C3'] = "1"
    
    # Fill year headers (row 1) and sub-headers (row 2) for AKTIVA section
    col_index = 5  # Start from column E
    year_columns = []  # Track column positions for later use in PASIVA
    
    for bs_result in balance_sheet_results:
        model = bs_result.get("model")
        year = getattr(model, "rok", "")
        
        # Create date string (12/31/YYYY)
        date_str = f"12/31/{year}" if year else ""
        
        # For AKTIVA section, we need 3 columns per year
        # Merge cells for year header
        year_col_letter = get_column_letter(col_index)
        netto_col_letter = get_column_letter(col_index + 2)
        sheet.merge_cells(f"{year_col_letter}1:{netto_col_letter}1")
        sheet[f"{year_col_letter}1"] = date_str
        sheet[f"{year_col_letter}1"].alignment = Alignment(horizontal='center')
        sheet[f"{year_col_letter}1"].font = Font(bold=True)
        
        # Sub-headers
        sheet[f"{year_col_letter}2"] = "Brutto"
        sheet[f"{get_column_letter(col_index + 1)}2"] = "Korekce"
        sheet[f"{netto_col_letter}2"] = "Netto"
        
        # Store the netto column for PASIVA section (single column per year)
        year_columns.append((date_str, col_index + 2))  # Store netto column index
        
        col_index += 3
    
    # Fill AKTIVA data rows
    current_row = 3
    for row_id in aktiva_rows:
        current_row += 1
        row_info = structure.get(row_id, {})
        row_name = row_info.get("name", f"Row {row_id}")
        
        # Columns A, B, C, D
        # Column A: row label (simplified - you may want to add hierarchical labels)
        sheet[f"B{current_row}"] = row_name
        sheet[f"C{current_row}"] = row_id
        
        # Fill data for each year
        col_index = 5
        for bs_result in balance_sheet_results:
            model = bs_result.get("model")
            if model is not None and row_id in model.data:
                row_data = model.data[row_id]
                
                # Brutto
                brutto_val = getattr(row_data, "brutto", None)
                sheet.cell(row=current_row, column=col_index, value=brutto_val)
                
                # Korekce (as negative)
                korekce_val = getattr(row_data, "korekce", None)
                if korekce_val is not None:
                    try:
                        korekce_val = -abs(int(korekce_val))
                    except Exception:
                        pass
                sheet.cell(row=current_row, column=col_index + 1, value=korekce_val)
                
                # Netto
                netto_val = getattr(row_data, "netto", 0)
                sheet.cell(row=current_row, column=col_index + 2, value=netto_val)
            else:
                # Fill with 0 or leave empty
                sheet.cell(row=current_row, column=col_index, value=0)
                sheet.cell(row=current_row, column=col_index + 1, value=0)
                sheet.cell(row=current_row, column=col_index + 2, value=0)
            
            col_index += 3
    
    # Add PASIVA CELKEM section
    current_row += 2
    pasiva_start_row = current_row
    
    sheet[f"B{pasiva_start_row}"] = "PASIVA CELKEM"
    sheet[f"C{pasiva_start_row}"] = "78"
    
    # For PASIVA, setup headers - only one column per year
    # Use the stored column positions from AKTIVA section
    for date_str, col_idx in year_columns:
        col_letter = get_column_letter(col_idx)
        sheet[f"{col_letter}{pasiva_start_row}"] = date_str
        sheet[f"{col_letter}{pasiva_start_row}"].font = Font(bold=True)
    
    # Fill PASIVA data rows
    for row_id in pasiva_rows:
        current_row += 1
        row_info = structure.get(row_id, {})
        row_name = row_info.get("name", f"Row {row_id}")
        
        sheet[f"B{current_row}"] = row_name
        sheet[f"C{current_row}"] = row_id
        
        # Fill data for each year (only netto for PASIVA)
        # Use the same column positions as headers
        for idx, (date_str, col_idx) in enumerate(year_columns):
            bs_result = balance_sheet_results[idx]
            model = bs_result.get("model")
            if model is not None and row_id in model.data:
                row_data = model.data[row_id]
                netto_val = getattr(row_data, "netto", 0)
                sheet.cell(row=current_row, column=col_idx, value=netto_val)
            else:
                sheet.cell(row=current_row, column=col_idx, value=0)
    
    logger.info(f"Successfully created {sheet_name} sheet with {len(balance_sheet_results)} years")


def create_quality_report_sheet(workbook: openpyxl.Workbook, results: List[Dict[str, Any]], inter_issues: List[str], tolerance: int) -> None:
    """Create the Data - Report Kvality sheet with quality information."""
    sheet_name = "Data - Report Kvality"
    
    if sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        # Clear existing content
        for row in sheet.iter_rows():
            for cell in row:
                cell.value = None
    else:
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


def export_data_landing(results: List[Dict[str, Any]], tolerance: int = 1) -> io.BytesIO:
    """
    Export results to a new data landing format with sheets:
    - Data - Rozvaha
    - Data - Výsledovka (not implemented yet)
    - Data - Report Kvality
    """
    logger.info(f"Creating data landing export from {len(results)} results")
    
    # Create new workbook
    workbook = openpyxl.Workbook()
    
    # Remove default sheet
    if "Sheet" in workbook.sheetnames:
        del workbook["Sheet"]
    
    # Get sorted balance sheets
    sorted_balance_sheets = get_sorted_balance_sheets(results)
    
    if sorted_balance_sheets:
        create_rozvaha_sheet(workbook, sorted_balance_sheets)
    else:
        logger.warning("No balance sheet data found in results")
    
    # TODO: Add Data - Výsledovka sheet
    
    # Add quality report
    try:
        from src.services.quality import validate_interstatement
        inter_issues = validate_interstatement(results, tolerance)
        create_quality_report_sheet(workbook, results, inter_issues, tolerance)
    except Exception as e:
        logger.error(f"Failed to add quality report: {e}", exc_info=True)
    
    # Save to BytesIO buffer
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    
    logger.info(f"Data landing export completed, buffer size: {buffer.getbuffer().nbytes/1024:.1f}KB")
    return buffer

