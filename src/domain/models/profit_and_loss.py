from typing import Dict, List, Tuple, Optional
from pydantic import BaseModel, Field, model_validator

from src.domain.models.rules import (
    PREDEFINED_PL_FLEXIBLE_RULES,
    PREDEFINED_PL_VALIDATION_RULES,
    FlexibleValidationRule,
    ValidationRule,
)


class ProfitAndLossRow(BaseModel):
    """Represents a single row in the profit and loss statement."""
    současné: int = Field(default=0, description="Current period amount")
    minulé: int = Field(default=0, description="Previous period amount")

    @classmethod
    def with_tolerance(cls, tolerance: int = 0, **kwargs):
        row = cls(**kwargs)
        if not hasattr(row, 'model_config'):
            row.model_config = {}
        row.model_config['tolerance'] = tolerance
        return row


class ProfitAndLoss(BaseModel):
    """Czech profit and loss statement with preconfigured validation rules."""
    rok: int = Field(..., description="Year of the profit and loss statement")
    data: Dict[int, ProfitAndLossRow] = Field(..., description="Profit and loss data by row number")
    tolerance: int = Field(default=0, description="Tolerance for validation rules (default: 0 for exact validation)")

    @model_validator(mode='after')
    def validate_consistency(self, info):
        errors = []
        tolerance = self.tolerance
        if tolerance == 0 and info.context and 'tolerance' in info.context:
            tolerance = info.context['tolerance']
            self.tolerance = tolerance

        for field in ['současné', 'minulé']:
            for rule in PREDEFINED_PL_VALIDATION_RULES:
                is_valid, error_msg = rule.validate_profit_and_loss(self.data, field=field, tolerance=tolerance)
                if not is_valid:
                    errors.append(error_msg)
            for flexible_rule in PREDEFINED_PL_FLEXIBLE_RULES:
                is_valid, error_msg = flexible_rule.validate_profit_and_loss(self.data, field=field, tolerance=tolerance)
                if not is_valid:
                    errors.append(error_msg)

        if errors:
            raise ValueError("Profit and loss validation failed:\n" + "\n".join(f"- {error}" for error in errors))
        return self

    def get_row_value(self, row_number: int, field: str = 'současné') -> int:
        if row_number in self.data:
            return getattr(self.data[row_number], field)
        return 0

    def validate_rule(self, target_row: int, source_rows: List[int], field: str = 'současné', tolerance: Optional[int] = None) -> Tuple[bool, str]:
        rule = ValidationRule(target_row=target_row, source_rows=source_rows)
        used_tolerance = tolerance if tolerance is not None else self.tolerance
        return rule.validate_profit_and_loss(self.data, field=field, tolerance=used_tolerance)

    def validate_flexible_rule(self, target_row: int, source_expressions: List[Tuple[int, int]], field: str = 'současné', tolerance: Optional[int] = None) -> Tuple[bool, str]:
        flexible_rule = FlexibleValidationRule(target_row=target_row, source_expressions=source_expressions)
        used_tolerance = tolerance if tolerance is not None else self.tolerance
        return flexible_rule.validate_profit_and_loss(self.data, field=field, tolerance=used_tolerance)

    def summary_report(self) -> str:
        report = [
            f"Profit and Loss Validation Report - Year {self.rok}",
            "-" * 60,
            f"Total rows: {len(self.data)}",
            f"Hierarchical rules: {len(PREDEFINED_PL_VALIDATION_RULES)}",
            f"Flexible rules: {len(PREDEFINED_PL_FLEXIBLE_RULES)}",
            f"Total validation rules: {len(PREDEFINED_PL_VALIDATION_RULES) + len(PREDEFINED_PL_FLEXIBLE_RULES)}",
            f"Tolerance: {self.tolerance}",
            "",
        ]
        all_valid = True
        for field in ['současné', 'minulé']:
            report.append(f"Field: {field}")
            report.append("-" * 20)
            for i, rule in enumerate(PREDEFINED_PL_VALIDATION_RULES, 1):
                # FlexibleValidationRule has source_expressions, not source_rows
                expression_parts = []
                for row_number, operation in rule.source_expressions:
                    op_symbol = "+" if operation > 0 else "-"
                    if len(expression_parts) == 0 and operation > 0:
                        expression_parts.append(str(row_number))
                    else:
                        expression_parts.append(f"{op_symbol}{row_number}")
                expression_str = "".join(expression_parts)
                report.append(f"Hierarchical Rule {i}: Row {rule.target_row} = {expression_str}")
                is_valid, error_msg = rule.validate_profit_and_loss(self.data, field=field, tolerance=self.tolerance)
                status = "✓" if is_valid else "✗"
                report.append(f"  {field}: {status}")
                if not is_valid:
                    all_valid = False
                    report.append(f"    {error_msg}")
                report.append("")
            for i, flexible_rule in enumerate(PREDEFINED_PL_FLEXIBLE_RULES, 1):
                expression_parts = []
                for row_number, operation in flexible_rule.source_expressions:
                    op_symbol = "+" if operation > 0 else "-"
                    if len(expression_parts) == 0 and operation > 0:
                        expression_parts.append(str(row_number))
                    else:
                        expression_parts.append(f"{op_symbol}{row_number}")
                expression_str = "".join(expression_parts)
                report.append(f"Flexible Rule {i}: Row {flexible_rule.target_row} = {expression_str}")
                is_valid, error_msg = flexible_rule.validate_profit_and_loss(self.data, field=field, tolerance=self.tolerance)
                status = "✓" if is_valid else "✗"
                report.append(f"  {field}: {status}")
                if not is_valid:
                    all_valid = False
                    report.append(f"    {error_msg}")
                report.append("")
        report.append(f"Overall Status: {'✓ VALID' if all_valid else '✗ VALIDATION ERRORS'}")
        return "\n".join(report)

    @classmethod
    def model_validate_with_tolerance(cls, obj: dict, tolerance: int = 0, **kwargs):
        context = kwargs.get('context', {})
        context['tolerance'] = tolerance
        kwargs['context'] = context
        return cls.model_validate(obj, **kwargs)

    @classmethod
    def from_ocr_with_tolerance(cls, ocr_data: dict, tolerance: int = 0):
        return cls.model_validate_with_tolerance(ocr_data, tolerance=tolerance)