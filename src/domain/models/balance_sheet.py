from typing import Dict, List, Tuple, Optional
from pydantic import BaseModel, Field, model_validator

from src.domain.models.rules import PREDEFINED_VALIDATION_RULES, ValidationRule


class BruttoKorekceNettoError(BaseModel):
    """Error when brutto - korekce != netto for a row."""
    row_id: int
    brutto: int
    korekce: int
    netto: int
    expected_netto: int
    difference: int
    tolerance: int


class BalanceSheetRow(BaseModel):
    """Represents a single row in the balance sheet."""
    brutto: Optional[int] = Field(default=None, description="Brutto amount")
    korekce: Optional[int] = Field(default=None, description="Correction amount")
    netto: int = Field(default=0, description="Net amount")
    netto_minule: int = Field(default=0, description="Previous year net amount")


class BalanceSheet(BaseModel):
    """Czech balance sheet with preconfigured validation rules.
    
    Note: All values are normalized to thousands (jednotky=1000) before validation.
    """
    rok: int = Field(..., description="Year of the balance sheet")
    jednotky: int = Field(default=1000, description="Units multiplier (always 1000 after normalization)")
    data: Dict[int, BalanceSheetRow] = Field(..., description="Balance sheet data by row number")
    tolerance: int = Field(default=0, description="Tolerance for validation rules (default: 0 for exact validation)")

    @model_validator(mode='after')
    def validate_consistency(self, info):
        errors = []
        structured_errors = []
        brutto_korekce_errors = []
        tolerance = self.tolerance
        if tolerance == 0 and info.context and 'tolerance' in info.context:
            tolerance = info.context['tolerance']
            self.tolerance = tolerance

        # Validate brutto - korekce = netto for each row
        for row_id, row_data in self.data.items():
            if row_data.brutto is not None and row_data.korekce is not None:
                expected_netto = row_data.brutto - abs(row_data.korekce)
                difference = abs(row_data.netto - expected_netto)
                if difference > tolerance:
                    error_msg = (
                        f"Brutto - Korekce validation failed for row {row_id}: "
                        f"brutto ({row_data.brutto}) - korekce ({abs(row_data.korekce)}) = {expected_netto}, "
                        f"but netto is {row_data.netto} (difference: {difference}, tolerance: {tolerance})"
                    )
                    errors.append(error_msg)
                    brutto_korekce_errors.append(BruttoKorekceNettoError(
                        row_id=row_id,
                        brutto=row_data.brutto,
                        korekce=row_data.korekce,
                        netto=row_data.netto,
                        expected_netto=expected_netto,
                        difference=difference,
                        tolerance=tolerance
                    ))

        for rule in PREDEFINED_VALIDATION_RULES:
            is_valid, error_msg, structured = rule.validate_netto(self.data, tolerance=tolerance)
            if not is_valid:
                errors.append(error_msg)
                if structured:
                    structured_errors.append(structured)
            # Also validate hierarchical rules for previous year column
            is_valid_prev, error_msg_prev, structured_prev = rule.validate_netto_minule(self.data, tolerance=tolerance)
            if not is_valid_prev:
                errors.append(error_msg_prev)
                if structured_prev:
                    structured_errors.append(structured_prev)

        if errors:
            # Store structured errors in context for later retrieval
            if info.context:
                info.context['structured_errors'] = structured_errors
                info.context['brutto_korekce_errors'] = brutto_korekce_errors
            raise ValueError("Balance sheet validation failed:\n" + "\n".join(f"- {error}" for error in errors))
        return self

    def get_row_value(self, row_number: int, field: str = 'netto') -> int:
        if row_number in self.data:
            return getattr(self.data[row_number], field)
        return 0

    def validate_rule(self, target_row: int, source_rows: List[int], tolerance: Optional[int] = None) -> Tuple[bool, str]:
        rule = ValidationRule(target_row=target_row, source_rows=source_rows)
        used_tolerance = tolerance if tolerance is not None else self.tolerance
        is_valid, msg, _ = rule.validate_netto(self.data, tolerance=used_tolerance)
        return is_valid, msg

    def summary_report(self) -> str:
        report = [
            f"Balance Sheet Validation Report - Year {self.rok}",
            "-" * 50,
            f"Total rows: {len(self.data)}",
            f"Validation rules: {len(PREDEFINED_VALIDATION_RULES)}",
            f"Tolerance: {self.tolerance}",
            "",
        ]
        all_valid = True
        for i, rule in enumerate(PREDEFINED_VALIDATION_RULES, 1):
            report.append(f"Rule {i}: Row {rule.target_row} = {' + '.join(str(r) for r in rule.source_rows)}")
            is_valid, error_msg, _ = rule.validate_netto(self.data, tolerance=self.tolerance)
            status = "✓" if is_valid else "✗"
            report.append(f"  Netto: {status}")
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


