import json
from typing import Dict, Any, Union
from importlib import resources


def convert_string_keys_to_int(data: Union[Dict[str, Any], Any]) -> Union[Dict[int, Any], Any]:
    """
    Recursively convert string keys that represent integers to actual integers.
    """
    if isinstance(data, dict):
        converted = {}
        for key, value in data.items():
            try:
                int_key = int(key)
                converted[int_key] = convert_string_keys_to_int(value)
            except (ValueError, TypeError):
                converted[key] = convert_string_keys_to_int(value)
        return converted
    if isinstance(data, list):
        return [convert_string_keys_to_int(item) for item in data]
    return data


def read_balance_sheet_index() -> Dict[int, Any]:
    """Read packaged balance sheet index as a dict with int keys."""
    with resources.files("src.infrastructure.resources").joinpath("balance_sheet_index.json").open(
        "r", encoding="utf-8"
    ) as file:
        data = json.load(file)
    return convert_string_keys_to_int(data)


def read_profit_and_loss_index() -> Dict[int, Any]:
    """Read packaged profit and loss index as a dict with int keys."""
    with resources.files("src.infrastructure.resources").joinpath("profit_and_loss_index.json").open(
        "r", encoding="utf-8"
    ) as file:
        data = json.load(file)
    return convert_string_keys_to_int(data)


def index_to_string(index: Dict[int, Any], indent_level: int = 0) -> str:
    """Convert index dict to a formatted string with tab indents."""
    result = []
    for row_id in sorted(index.keys()):
        row_data = index[row_id]
        indent = "\t" * indent_level
        line = f"{indent}{row_id} {row_data['name']}"
        result.append(line)
        if "sub_rows" in row_data and row_data["sub_rows"]:
            result.append(index_to_string(row_data["sub_rows"], indent_level + 1))
    return "\n".join(result)


def load_json_from_text(response: str) -> Dict[str, Any]:
    """Extract JSON from a text response that contains a JSON code block."""
    return json.loads(response.removeprefix("```json\n").removesuffix("\n```"))


