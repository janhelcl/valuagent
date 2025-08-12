from typing import Dict, List, Tuple, Optional, Any
from pydantic import BaseModel, Field, model_validator


class BalanceSheetRow(BaseModel):
    """Represents a single row in the balance sheet."""
    brutto: Optional[int] = Field(default=None, description="Brutto amount")
    korekce: Optional[int] = Field(default=None, description="Correction amount")
    netto: int = Field(default=0, description="Net amount")
    netto_minule: int = Field(default=0, description="Previous year net amount")

    @model_validator(mode='after')
    def validate_brutto_korekce_netto(self, info):
        """Validate that when brutto and korekce are set, brutto - korekce = netto."""
        if self.brutto is not None and self.korekce is not None:
            expected_netto = self.brutto - abs(self.korekce)
            
            # Get tolerance from multiple sources (in order of priority):
            # 1. model_config if set via with_tolerance()
            # 2. validation context if passed to model_validate()
            # 3. default to 0 for exact validation
            tolerance = 0
            if hasattr(self, 'model_config') and 'tolerance' in self.model_config:
                tolerance = self.model_config['tolerance']
            elif info.context and 'tolerance' in info.context:
                tolerance = info.context['tolerance']
            
            difference = abs(self.netto - expected_netto)
            if difference > tolerance:
                raise ValueError(
                    f"Brutto - Korekce validation failed: "
                    f"brutto ({self.brutto}) - korekce ({abs(self.korekce)}) = {expected_netto}, "
                    f"but netto is {self.netto} (difference: {difference}, tolerance: {tolerance})"
                )
        return self

    @classmethod
    def with_tolerance(cls, tolerance: int = 0, **kwargs):
        """Create a BalanceSheetRow with a specific tolerance for validation."""
        row = cls(**kwargs)
        if not hasattr(row, 'model_config'):
            row.model_config = {}
        row.model_config['tolerance'] = tolerance
        return row


class ProfitAndLossRow(BaseModel):
    """Represents a single row in the profit and loss statement."""
    současné: int = Field(default=0, description="Current period amount")
    minulé: int = Field(default=0, description="Previous period amount")

    @classmethod
    def with_tolerance(cls, tolerance: int = 0, **kwargs):
        """Create a ProfitAndLossRow with a specific tolerance for validation."""
        row = cls(**kwargs)
        if not hasattr(row, 'model_config'):
            row.model_config = {}
        row.model_config['tolerance'] = tolerance
        return row


class ValidationRule(BaseModel):
    """Represents a validation rule for balance sheet consistency."""
    target_row: int = Field(..., description="Target row number (left side of equation)")
    source_rows: List[int] = Field(..., description="Source row numbers (right side of equation)")

    def validate_netto(self, balance_data: Dict[str, BalanceSheetRow], tolerance: int = 0) -> Tuple[bool, str]:
        """
        Validate the netto field for this rule with optional tolerance.
        
        Args:
            balance_data: Dictionary of row number -> BalanceSheetRow
            tolerance: Maximum allowed difference between target and sum
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get target value (default to 0 if row doesn't exist)
        target_value = 0
        if self.target_row in balance_data:
            target_value = balance_data[self.target_row].netto
        
        # Calculate sum of source values (default to 0 if row doesn't exist)
        source_sum = 0
        for source_row in self.source_rows:
            if source_row in balance_data:
                source_sum += balance_data[source_row].netto
        
        difference = abs(target_value - source_sum)
        is_valid = difference <= tolerance
        
        if not is_valid:
            error_msg = (
                f"Rule validation failed for netto: "
                f"Row {self.target_row} ({target_value}) != "
                f"Sum of rows {'+'.join(str(row) for row in self.source_rows)} ({source_sum}) "
                f"(difference: {difference}, tolerance: {tolerance})"
            )
            return False, error_msg
        
        return True, ""

    def validate_profit_and_loss(self, pl_data: Dict[str, ProfitAndLossRow], field: str = 'současné', tolerance: int = 0) -> Tuple[bool, str]:
        """
        Validate the specified field for this rule in profit and loss data.
        
        Args:
            pl_data: Dictionary of row number -> ProfitAndLossRow
            field: Field to validate ('současné' or 'minulé')
            tolerance: Maximum allowed difference between target and sum
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get target value (default to 0 if row doesn't exist)
        target_value = 0
        if self.target_row in pl_data:
            target_value = getattr(pl_data[self.target_row], field)
        
        # Calculate sum of source values (default to 0 if row doesn't exist)
        source_sum = 0
        for source_row in self.source_rows:
            if source_row in pl_data:
                source_sum += getattr(pl_data[source_row], field)
        
        difference = abs(target_value - source_sum)
        is_valid = difference <= tolerance
        
        if not is_valid:
            error_msg = (
                f"Rule validation failed for {field}: "
                f"Row {self.target_row} ({target_value}) != "
                f"Sum of rows {'+'.join(str(row) for row in self.source_rows)} ({source_sum}) "
                f"(difference: {difference}, tolerance: {tolerance})"
            )
            return False, error_msg
        
        return True, ""


class FlexibleValidationRule(BaseModel):
    """Represents a flexible validation rule that can handle addition and subtraction."""
    target_row: int = Field(..., description="Target row number (left side of equation)")
    source_expressions: List[Tuple[int, int]] = Field(..., description="List of (row_number, operation) where operation is +1 or -1")
    
    def validate_profit_and_loss(self, pl_data: Dict[str, ProfitAndLossRow], field: str = 'současné', tolerance: int = 0) -> Tuple[bool, str]:
        """
        Validate the specified field for this flexible rule in profit and loss data.
        
        Args:
            pl_data: Dictionary of row number -> ProfitAndLossRow
            field: Field to validate ('současné' or 'minulé')
            tolerance: Maximum allowed difference between target and calculated value
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get target value (default to 0 if row doesn't exist)
        target_value = 0
        if self.target_row in pl_data:
            target_value = getattr(pl_data[self.target_row], field)
        
        # Calculate result of expression
        calculated_value = 0
        expression_parts = []
        
        for row_number, operation in self.source_expressions:
            if row_number in pl_data:
                row_value = getattr(pl_data[row_number], field)
                calculated_value += row_value * operation
                
                # Build expression string for error messages
                op_symbol = "+" if operation > 0 else "-"
                if len(expression_parts) == 0 and operation > 0:
                    expression_parts.append(str(row_number))
                else:
                    expression_parts.append(f"{op_symbol}{row_number}")
        
        difference = abs(target_value - calculated_value)
        is_valid = difference <= tolerance
        
        if not is_valid:
            expression_str = "".join(expression_parts)
            error_msg = (
                f"Flexible rule validation failed for {field}: "
                f"Row {self.target_row} ({target_value}) != "
                f"{expression_str} ({calculated_value}) "
                f"(difference: {difference}, tolerance: {tolerance})"
            )
            return False, error_msg
        
        return True, ""


def generate_validation_rules() -> list:
    """
    Automatically generate all validation rules from the balance sheet index.
    Each parent row should equal the sum of its direct sub_rows.
    
    Returns:
        List of tuples (target_row, source_rows) for ValidationRule creation
    """
    from .utils import read_balance_sheet_index
    
    index = read_balance_sheet_index()
    rules = []
    
    def collect_rules_recursive(data: Dict[int, Any]):
        """Recursively collect validation rules from the hierarchical structure."""
        for row_id, row_data in data.items():
            if 'sub_rows' in row_data and row_data['sub_rows']:
                # Parent row should equal sum of direct sub_rows
                sub_row_ids = list(row_data['sub_rows'].keys())
                rules.append((row_id, sub_row_ids))
                
                # Recursively process sub_rows
                collect_rules_recursive(row_data['sub_rows'])
    
    # Collect all hierarchical rules
    collect_rules_recursive(index)
    
    # Add the fundamental accounting equation: Assets = Liabilities
    rules.append((1, [78]))  # Aktiva = Pasiva
    
    return rules


def generate_profit_and_loss_validation_rules() -> list:
    """
    Automatically generate all validation rules from the profit and loss index.
    Each parent row should equal the sum of its direct sub_rows.
    
    Returns:
        List of tuples (target_row, source_rows) for ValidationRule creation
    """
    from .utils import read_profit_and_loss_index
    
    index = read_profit_and_loss_index()
    rules = []
    
    def collect_rules_recursive(data: Dict[int, Any]):
        """Recursively collect validation rules from the hierarchical structure."""
        for row_id, row_data in data.items():
            if 'sub_rows' in row_data and row_data['sub_rows']:
                # Parent row should equal sum of direct sub_rows
                sub_row_ids = list(row_data['sub_rows'].keys())
                rules.append((row_id, sub_row_ids))
                
                # Recursively process sub_rows
                collect_rules_recursive(row_data['sub_rows'])
    
    # Collect all hierarchical rules
    collect_rules_recursive(index)
    
    return rules


def _generate_predefined_rules():
    """Generate all validation rules automatically from the balance sheet structure."""
    try:
        rules_data = generate_validation_rules()
        return [ValidationRule(target_row=target, source_rows=sources) for target, sources in rules_data]
    except Exception:
        # Fallback if generation fails
        return [ValidationRule(target_row=1, source_rows=[78])]

# Automatically generated validation rules for Czech balance sheets
PREDEFINED_VALIDATION_RULES = _generate_predefined_rules()


class BalanceSheet(BaseModel):
    """Czech balance sheet with preconfigured validation rules."""
    rok: int = Field(..., description="Year of the balance sheet")
    data: Dict[int, BalanceSheetRow] = Field(..., description="Balance sheet data by row number")
    tolerance: int = Field(default=0, description="Tolerance for validation rules (default: 0 for exact validation)")

    @model_validator(mode='after')
    def validate_consistency(self, info):
        """Validate all predefined consistency rules for netto fields only."""
        errors = []
        
        # Get tolerance from validation context if not set directly
        tolerance = self.tolerance
        if tolerance == 0 and info.context and 'tolerance' in info.context:
            tolerance = info.context['tolerance']
            # Also update the instance tolerance for consistency
            self.tolerance = tolerance
        
        for rule in PREDEFINED_VALIDATION_RULES:
            is_valid, error_msg = rule.validate_netto(self.data, tolerance=tolerance)
            if not is_valid:
                errors.append(error_msg)
        
        if errors:
            raise ValueError(f"Balance sheet validation failed:\n" + "\n".join(f"- {error}" for error in errors))
        
        return self

    def get_row_value(self, row_number: str, field: str = 'netto') -> int:
        """Get value for a specific row and field, returning 0 if row doesn't exist."""
        if row_number in self.data:
            return getattr(self.data[row_number], field)
        return 0

    def validate_rule(self, target_row: str, source_rows: List[str], tolerance: Optional[int] = None) -> Tuple[bool, str]:
        """
        Validate a specific rule for netto field only.
        
        Args:
            target_row: Target row number
            source_rows: List of source row numbers
            tolerance: Optional tolerance override (uses instance tolerance if None)
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        rule = ValidationRule(target_row=target_row, source_rows=source_rows)
        used_tolerance = tolerance if tolerance is not None else self.tolerance
        return rule.validate_netto(self.data, tolerance=used_tolerance)

    def summary_report(self) -> str:
        """Generate a summary report of the balance sheet validation."""
        report = [
            f"Balance Sheet Validation Report - Year {self.rok}",
            "=" * 50,
            f"Total rows: {len(self.data)}",
            f"Validation rules: {len(PREDEFINED_VALIDATION_RULES)}",
            f"Tolerance: {self.tolerance}",
            "",
        ]
        
        # Test all predefined rules
        all_valid = True
        for i, rule in enumerate(PREDEFINED_VALIDATION_RULES, 1):
            report.append(f"Rule {i}: Row {rule.target_row} = {' + '.join(str(r) for r in rule.source_rows)}")
            
            is_valid, error_msg = rule.validate_netto(self.data, tolerance=self.tolerance)
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
        """
        Validate a BalanceSheet with specified tolerance for both row and balance sheet level validation.
        
        Args:
            obj: Dictionary with balance sheet data (OCR format)
            tolerance: Tolerance for all validation rules
            **kwargs: Additional arguments passed to model_validate
        
        Returns:
            BalanceSheet instance
        """
        # Set up validation context with tolerance
        context = kwargs.get('context', {})
        context['tolerance'] = tolerance
        kwargs['context'] = context
        
        return cls.model_validate(obj, **kwargs)

    @classmethod  
    def from_ocr_with_tolerance(cls, ocr_data: dict, tolerance: int = 0):
        """
        Alternative method to create BalanceSheet from OCR data with tolerance.
        Equivalent to create_balance_sheet_from_ocr() but as a class method.
    
    Args:
        ocr_data: Dictionary with 'rok' and 'data' keys from OCR
            tolerance: Tolerance for validation rules
    
    Returns:
        BalanceSheet instance
    """
        return cls.model_validate_with_tolerance(ocr_data, tolerance=tolerance)


# Automatically generated validation rules for profit and loss statements
def _generate_predefined_pl_rules():
    """Generate all validation rules automatically from the profit and loss structure."""
    try:
        rules_data = generate_profit_and_loss_validation_rules()
        return [ValidationRule(target_row=target, source_rows=sources) for target, sources in rules_data]
    except Exception:
        # Fallback if generation fails
        return []

PREDEFINED_PL_VALIDATION_RULES = _generate_predefined_pl_rules()

# Manual flexible validation rules for P&L that require addition/subtraction
PREDEFINED_PL_FLEXIBLE_RULES = [
    # Výsledek hospodaření před zdaněním
    FlexibleValidationRule(target_row=49, source_expressions=[(30, 1), (48, 1)]),
    # Výsledek hospodaření po zdanění
    FlexibleValidationRule(target_row=53, source_expressions=[(49, 1), (50, -1)]),
    # Výsledek hospodaření za účetní období
    FlexibleValidationRule(target_row=55, source_expressions=[(53, 1), (54, -1)]),
    # Finanční výsledek hospodaření
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
        ]),
    # Provozní výsledek hospodaření
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
            (24, -1)
        ]),
]


class ProfitAndLoss(BaseModel):
    """Czech profit and loss statement with preconfigured validation rules."""
    rok: int = Field(..., description="Year of the profit and loss statement")
    data: Dict[int, ProfitAndLossRow] = Field(..., description="Profit and loss data by row number")
    tolerance: int = Field(default=0, description="Tolerance for validation rules (default: 0 for exact validation)")

    @model_validator(mode='after')
    def validate_consistency(self, info):
        """Validate all predefined consistency rules for both současné and minulé fields."""
        errors = []
        
        # Get tolerance from validation context if not set directly
        tolerance = self.tolerance
        if tolerance == 0 and info.context and 'tolerance' in info.context:
            tolerance = info.context['tolerance']
            # Also update the instance tolerance for consistency
            self.tolerance = tolerance
        
        # Validate both současné and minulé fields
        for field in ['současné', 'minulé']:
            # Validate hierarchical summation rules
            for rule in PREDEFINED_PL_VALIDATION_RULES:
                is_valid, error_msg = rule.validate_profit_and_loss(self.data, field=field, tolerance=tolerance)
                if not is_valid:
                    errors.append(error_msg)
            
            # Validate flexible addition/subtraction rules
            for flexible_rule in PREDEFINED_PL_FLEXIBLE_RULES:
                is_valid, error_msg = flexible_rule.validate_profit_and_loss(self.data, field=field, tolerance=tolerance)
                if not is_valid:
                    errors.append(error_msg)
        
        if errors:
            raise ValueError(f"Profit and loss validation failed:\n" + "\n".join(f"- {error}" for error in errors))
        
        return self

    def get_row_value(self, row_number: str, field: str = 'současné') -> int:
        """Get value for a specific row and field, returning 0 if row doesn't exist."""
        if row_number in self.data:
            return getattr(self.data[row_number], field)
        return 0

    def validate_rule(self, target_row: str, source_rows: List[str], field: str = 'současné', tolerance: Optional[int] = None) -> Tuple[bool, str]:
        """
        Validate a specific rule for the specified field.
        
        Args:
            target_row: Target row number
            source_rows: List of source row numbers
            field: Field to validate ('současné' or 'minulé')
            tolerance: Optional tolerance override (uses instance tolerance if None)
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        rule = ValidationRule(target_row=target_row, source_rows=source_rows)
        used_tolerance = tolerance if tolerance is not None else self.tolerance
        return rule.validate_profit_and_loss(self.data, field=field, tolerance=used_tolerance)

    def validate_flexible_rule(self, target_row: str, source_expressions: List[Tuple[int, int]], field: str = 'současné', tolerance: Optional[int] = None) -> Tuple[bool, str]:
        """
        Validate a specific flexible rule for the specified field.
        
        Args:
            target_row: Target row number
            source_expressions: List of (row_number, operation) where operation is +1 or -1
            field: Field to validate ('současné' or 'minulé')
            tolerance: Optional tolerance override (uses instance tolerance if None)
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        flexible_rule = FlexibleValidationRule(target_row=target_row, source_expressions=source_expressions)
        used_tolerance = tolerance if tolerance is not None else self.tolerance
        return flexible_rule.validate_profit_and_loss(self.data, field=field, tolerance=used_tolerance)

    def summary_report(self) -> str:
        """Generate a summary report of the profit and loss validation."""
        report = [
            f"Profit and Loss Validation Report - Year {self.rok}",
            "=" * 60,
            f"Total rows: {len(self.data)}",
            f"Hierarchical rules: {len(PREDEFINED_PL_VALIDATION_RULES)}",
            f"Flexible rules: {len(PREDEFINED_PL_FLEXIBLE_RULES)}",
            f"Total validation rules: {len(PREDEFINED_PL_VALIDATION_RULES) + len(PREDEFINED_PL_FLEXIBLE_RULES)}",
            f"Tolerance: {self.tolerance}",
            "",
        ]
        
        # Test all predefined rules for both fields
        all_valid = True
        for field in ['současné', 'minulé']:
            report.append(f"Field: {field}")
            report.append("-" * 20)
            
            # Test hierarchical rules
            for i, rule in enumerate(PREDEFINED_PL_VALIDATION_RULES, 1):
                report.append(f"Hierarchical Rule {i}: Row {rule.target_row} = {' + '.join(str(r) for r in rule.source_rows)}")
                
                is_valid, error_msg = rule.validate_profit_and_loss(self.data, field=field, tolerance=self.tolerance)
                status = "✓" if is_valid else "✗"
                report.append(f"  {field}: {status}")
                if not is_valid:
                    all_valid = False
                    report.append(f"    {error_msg}")
                report.append("")
            
            # Test flexible rules
            for i, flexible_rule in enumerate(PREDEFINED_PL_FLEXIBLE_RULES, 1):
                # Build expression string for display
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
        """
        Validate a ProfitAndLoss with specified tolerance for validation rules.
        
        Args:
            obj: Dictionary with profit and loss data (OCR format)
            tolerance: Tolerance for all validation rules
            **kwargs: Additional arguments passed to model_validate
        
        Returns:
            ProfitAndLoss instance
        """
        # Set up validation context with tolerance
        context = kwargs.get('context', {})
        context['tolerance'] = tolerance
        kwargs['context'] = context
        
        return cls.model_validate(obj, **kwargs)

    @classmethod  
    def from_ocr_with_tolerance(cls, ocr_data: dict, tolerance: int = 0):
        """
        Alternative method to create ProfitAndLoss from OCR data with tolerance.
        
        Args:
            ocr_data: Dictionary with 'rok' and 'data' keys from OCR
            tolerance: Tolerance for validation rules
            
        Returns:
            ProfitAndLoss instance
        """
        return cls.model_validate_with_tolerance(ocr_data, tolerance=tolerance)


# Helper function to create ProfitAndLoss from OCR data format
def create_profit_and_loss_from_ocr(ocr_data: dict, tolerance: int = 0) -> ProfitAndLoss:
    """
    Convert OCR data format to ProfitAndLoss instance.
    
    Args:
        ocr_data: Dictionary with 'rok' and 'data' keys from OCR
        tolerance: Tolerance for validation rules (default: 0 for exact validation)
    
    Returns:
        ProfitAndLoss instance
    """
    # Use the new validation context approach for consistency
    return ProfitAndLoss.model_validate_with_tolerance(ocr_data, tolerance=tolerance)
