import json
from typing import Dict, Any, Union


def convert_string_keys_to_int(data: Union[Dict[str, Any], Any]) -> Union[Dict[int, Any], Any]:
    """
    Recursively convert string keys that represent integers to actual integers.
    
    Args:
        data: The data structure to convert (dict, list, or other)
        
    Returns:
        The converted data structure with integer keys where applicable
    """
    if isinstance(data, dict):
        converted = {}
        for key, value in data.items():
            # Try to convert string key to integer
            try:
                int_key = int(key)
                converted[int_key] = convert_string_keys_to_int(value)
            except (ValueError, TypeError):
                # If conversion fails, keep original key
                converted[key] = convert_string_keys_to_int(value)
        return converted
    elif isinstance(data, list):
        return [convert_string_keys_to_int(item) for item in data]
    else:
        return data


def read_balance_sheet_index() -> Dict[int, Any]:
    """
    Read the balance_sheet_index.json file and convert it to a Python dictionary
    with integer keys where string keys represent integers.
    
    Returns:
        Dictionary with the balance sheet structure and integer keys
    """
    with open('src/balance_sheet_index.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    return convert_string_keys_to_int(data)


def read_profit_and_loss_index() -> Dict[int, Any]:
    """
    Read the profit_and_loss_index.json file and convert it to a Python dictionary
    with integer keys where string keys represent integers.
    """
    with open('src/profit_and_loss_index.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    return convert_string_keys_to_int(data)


def index_to_string(index: Dict[int, Any], indent_level: int = 0) -> str:
    """
    Convert balance sheet index data to a formatted string representation.
    Rows are sorted by integer IDs, with sub-rows indented by tabs.
    
    Args:
        index: The balance sheet index with integer keys
        indent_level: Current indentation level (number of tabs)
        
    Returns:
        Single string with hierarchical representation of the balance sheet
    """
    result = []
    
    # Sort rows by integer keys
    for row_id in sorted(index.keys()):
        row_data = index[row_id]
        
        # Add indentation and format current row
        indent = '\t' * indent_level
        line = f"{indent}{row_id} {row_data['name']}"
        result.append(line)
        
        # Recursively process sub_rows if they exist
        if 'sub_rows' in row_data and row_data['sub_rows']:
            sub_rows_str = index_to_string(row_data['sub_rows'], indent_level + 1)
            result.append(sub_rows_str)
    
    return '\n'.join(result)

def load_json_from_text(response: str) -> Dict[str, Any]:
    """
    Extract JSON from a text response that contains a JSON block.
    
    Args:
        response: The text response containing a JSON block
        
    Returns:
        Dictionary containing the parsed JSON data
    """
    return json.loads(
        response.removeprefix('```json\n').removesuffix('\n```')
    )
