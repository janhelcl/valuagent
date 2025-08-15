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


def fill_predmet_oceneni_sheet(workbook: openpyxl.Workbook, balance_sheet_result: Dict[str, Any], disambiguation_info: Dict[str, Any] = None) -> None:
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
    
    # Fill date cells E2, F2, G2, H2 with disambiguation date
    if disambiguation_info and disambiguation_info.get("datum"):
        date_str = disambiguation_info["datum"]
        try:
            # Parse the date (expected format: YYYY-MM-DD)
            from datetime import datetime
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d.%m.%Y")
            
            # Fill all date cells
            date_cells = ["E2", "F2", "G2", "H2"]
            for cell in date_cells:
                sheet[cell] = formatted_date
                logger.debug(f"Set date cell {cell} = {formatted_date}")
            
            logger.info(f"Filled date cells with {formatted_date}")
        except ValueError as e:
            logger.warning(f"Could not parse date '{date_str}': {e}")
    else:
        logger.debug("No disambiguation date available for Předmět ocenění sheet")
    
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
    
    # Fill latest year in J3 (latest year from Předmět ocenění)
    latest_year = getattr(balance_sheet_results[0]["model"], "rok", "")
    if latest_year:
        sheet["J3"] = latest_year
        logger.debug(f"Set latest year header J3 = {latest_year}")
    
    # Column mapping: I = 2nd latest, H = 3rd latest, G = 4th latest, F = 5th latest
    year_columns = ['I', 'H', 'G', 'F']
    max_years = len(year_columns)
    
    # Skip the latest year (already in Předmět ocenění), take up to 4 historical years
    historical_balance_sheets = balance_sheet_results[1:max_years+1]
    
    # Prepare data sources: each entry is (balance_sheet_result, year, data_source)
    # data_source can be 'netto' or 'netto_minule'
    data_sources = []
    
    # Add historical balance sheets with their netto values
    for bs in historical_balance_sheets:
        year = getattr(bs["model"], "rok", 0)
        data_sources.append((bs, year, 'netto'))
    
    # If we have room left, add netto_minule values from available balance sheets
    remaining_columns = max_years - len(data_sources)
    if remaining_columns > 0:
        # Use netto_minule from balance sheets to fill additional years
        # Start from the beginning but avoid duplicating years we already have
        existing_years = {year for _, year, _ in data_sources}
        
        for bs in balance_sheet_results:
            if remaining_columns <= 0:
                break
            year = getattr(bs["model"], "rok", 0) - 1  # netto_minule is previous year
            if year > 0 and year not in existing_years:  # Only if valid and not duplicate
                data_sources.append((bs, year, 'netto_minule'))
                existing_years.add(year)
                remaining_columns -= 1
    
    # Sort by year descending (newest first) and take only what fits
    data_sources.sort(key=lambda x: x[1], reverse=True)
    data_sources = data_sources[:max_years]
    
    if not data_sources:
        logger.info("No historical balance sheet data available for Rozvaha sheet")
        return
    
    logger.info(f"Filling Rozvaha sheet with {len(data_sources)} years of historical data")
    
    # Fill year headers in row 3
    for i, (balance_sheet_result, year, data_source) in enumerate(data_sources):
        column = year_columns[i]
        year_cell = f"{column}3"
        sheet[year_cell] = year
        logger.debug(f"Set year header {year_cell} = {year} (from {data_source})")
    
    # Fill data for each year
    total_filled = 0
    total_missing = 0
    
    for year_idx, (balance_sheet_result, year, data_source) in enumerate(data_sources):
        column = year_columns[year_idx]
        balance_sheet = balance_sheet_result["model"]
        balance_data = getattr(balance_sheet, "data", {})
        
        filled_count = 0
        missing_count = 0
        
        logger.debug(f"Filling column {column} with year {year} data from {data_source} ({len(balance_data)} rows)")
        
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
                # Get the value based on data source
                value = None
                if data_source == 'netto' and hasattr(row_data, "netto"):
                    value = row_data.netto
                elif data_source == 'netto_minule' and hasattr(row_data, "netto_minule"):
                    value = row_data.netto_minule
                
                if value is not None:
                    cell_address = f"{column}{excel_row}"
                    
                    # Check if cell contains a formula - if so, skip it to preserve template logic
                    existing_cell = sheet[cell_address]
                    if existing_cell.data_type == 'f':  # 'f' means formula
                        logger.debug(f"Skipping {cell_address} - contains formula: {existing_cell.value}")
                        missing_count += 1
                    else:
                        sheet[cell_address] = value
                        logger.debug(f"Set {cell_address} = {value} ({data_source} for {row_name})")
                        filled_count += 1
                else:
                    logger.debug(f"No {data_source} value for row {row_id} ({row_name})")
                    missing_count += 1
                    
            except Exception as e:
                logger.error(f"Error filling row {row_id} ({row_name}) in column {column}: {e}")
                missing_count += 1
                continue
        
        logger.info(f"Column {column} (year {year} from {data_source}): filled {filled_count} rows, {missing_count} missing")
        total_filled += filled_count
        total_missing += missing_count
    
    logger.info(f"Successfully filled Rozvaha sheet: {total_filled} total values, {total_missing} total missing")


def export_dcf_template(results: List[Dict[str, Any]], disambiguation_info: Dict[str, Any] = None) -> io.BytesIO:
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
    
    # Fill Předmět ocenění sheet with latest year and disambiguation date
    latest_balance_sheet = sorted_balance_sheets[0]
    fill_predmet_oceneni_sheet(workbook, latest_balance_sheet, disambiguation_info)
    
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
