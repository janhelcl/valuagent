from typing import Dict, List, Tuple, Optional
from pydantic import BaseModel, Field


class ValidationRule(BaseModel):
    """Represents a validation rule for balance sheet consistency."""
    target_row: int = Field(..., description="Target row number (left side of equation)")
    source_rows: List[int] = Field(..., description="Source row numbers (right side of equation)")

    def validate_netto(self, balance_data: Dict[int, "BalanceSheetRow"], tolerance: int = 0) -> Tuple[bool, str]:
        target_value = balance_data.get(self.target_row, None).netto if self.target_row in balance_data else 0
        source_sum = sum(balance_data[s].netto for s in self.source_rows if s in balance_data)
        difference = abs(target_value - source_sum)
        if difference <= tolerance:
            return True, ""
        return False, (
            f"Rule validation failed for netto: Row {self.target_row} ({target_value}) != "
            f"Sum of rows {'+'.join(str(row) for row in self.source_rows)} ({source_sum}) "
            f"(difference: {difference}, tolerance: {tolerance})"
        )


class FlexibleValidationRule(BaseModel):
    """Represents a flexible validation rule that can handle addition and subtraction."""
    target_row: int = Field(..., description="Target row number (left side of equation)")
    source_expressions: List[Tuple[int, int]] = Field(..., description="List of (row_number, operation) where operation is +1 or -1")

    def validate_profit_and_loss(self, pl_data: Dict[int, "ProfitAndLossRow"], field: str = 'současné', tolerance: int = 0) -> Tuple[bool, str]:
        target_value = getattr(pl_data[self.target_row], field) if self.target_row in pl_data else 0
        calculated_value = 0
        expression_parts: List[str] = []
        for row_number, operation in self.source_expressions:
            if row_number in pl_data:
                row_value = getattr(pl_data[row_number], field)
                calculated_value += row_value * operation
                op_symbol = "+" if operation > 0 else "-"
                if len(expression_parts) == 0 and operation > 0:
                    expression_parts.append(str(row_number))
                else:
                    expression_parts.append(f"{op_symbol}{row_number}")

        difference = abs(target_value - calculated_value)
        if difference <= tolerance:
            return True, ""
        expression_str = "".join(expression_parts)
        return False, (
            f"Flexible rule validation failed for {field}: Row {self.target_row} ({target_value}) != "
            f"{expression_str} ({calculated_value}) (difference: {difference}, tolerance: {tolerance})"
        )


def generate_validation_rules() -> list:
    """Generate hierarchical balance sheet validation rules from packaged index."""
    from src.shared.utils import read_balance_sheet_index
    index = read_balance_sheet_index()
    rules: List[Tuple[int, List[int]]] = []

    def collect_rules_recursive(data: Dict[int, dict]):
        for row_id, row_data in data.items():
            if 'sub_rows' in row_data and row_data['sub_rows']:
                sub_row_ids = list(row_data['sub_rows'].keys())
                rules.append((row_id, sub_row_ids))
                collect_rules_recursive(row_data['sub_rows'])

    collect_rules_recursive(index)
    rules.append((1, [78]))  # Aktiva = Pasiva
    return rules


def generate_profit_and_loss_validation_rules() -> list:
    """Generate hierarchical profit and loss validation rules from packaged index."""
    from src.shared.utils import read_profit_and_loss_index
    index = read_profit_and_loss_index()
    rules: List[Tuple[int, List[int]]] = []

    def collect_rules_recursive(data: Dict[int, dict]):
        for row_id, row_data in data.items():
            if 'sub_rows' in row_data and row_data['sub_rows']:
                sub_row_ids = list(row_data['sub_rows'].keys())
                rules.append((row_id, sub_row_ids))
                collect_rules_recursive(row_data['sub_rows'])

    collect_rules_recursive(index)
    return rules


def _generate_predefined_rules():
    try:
        rules_data = generate_validation_rules()
        return [ValidationRule(target_row=target, source_rows=sources) for target, sources in rules_data]
    except Exception:
        return [ValidationRule(target_row=1, source_rows=[78])]


PREDEFINED_VALIDATION_RULES = _generate_predefined_rules()


def _generate_predefined_pl_rules():
    try:
        rules_data = generate_profit_and_loss_validation_rules()
        return [ValidationRule(target_row=target, source_rows=sources) for target, sources in rules_data]
    except Exception:
        return []


PREDEFINED_PL_VALIDATION_RULES = _generate_predefined_pl_rules()

PREDEFINED_PL_FLEXIBLE_RULES = [
    FlexibleValidationRule(target_row=49, source_expressions=[(30, 1), (48, 1)]),
    FlexibleValidationRule(target_row=53, source_expressions=[(49, 1), (50, -1)]),
    FlexibleValidationRule(target_row=55, source_expressions=[(53, 1), (54, -1)]),
    FlexibleValidationRule(
        target_row=48,
        source_expressions=[
            (31, 1),
            (35, 1),
            (39, 1),
            (46, 1),
            (34, -1),
            (38, -1),
            (42, -1),
            (43, -1),
            (47, -1),
        ],
    ),
    FlexibleValidationRule(
        target_row=30,
        source_expressions=[
            (1, 1),
            (2, 1),
            (20, 1),
            (3, -1),
            (7, -1),
            (8, -1),
            (9, -1),
            (14, -1),
            (24, -1),
        ],
    ),
]


