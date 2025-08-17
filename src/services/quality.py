from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.shared import utils


def _safe_get_bs_value(result: Dict[str, Any], row_id: int, field: str) -> Optional[int]:
    model = result.get("model")
    if model is not None:
        row = getattr(model, "data", {}).get(row_id)
        if row is not None and hasattr(row, field):
            return getattr(row, field)
    raw = result.get("raw") or {}
    data = raw.get("data") or {}
    # Try string key then int key
    for key in (str(row_id), row_id):
        val = None
        try:
            val = (data.get(key) or {}).get(field)
        except Exception:
            val = None
        if val is not None:
            try:
                return int(val)
            except Exception:
                pass
    return None


def _safe_get_pl_value(result: Dict[str, Any], row_id: int, field: str) -> Optional[int]:
    model = result.get("model")
    if model is not None:
        row = getattr(model, "data", {}).get(row_id)
        if row is not None and hasattr(row, field):
            return getattr(row, field)
    raw = result.get("raw") or {}
    data = raw.get("data") or {}
    for key in (str(row_id), row_id):
        val = None
        try:
            val = (data.get(key) or {}).get(field)
        except Exception:
            val = None
        if val is not None:
            try:
                return int(val)
            except Exception:
                pass
    return None


def _pick_best_per_year(results: List[Dict[str, Any]], statement_type: str) -> Dict[int, Dict[str, Any]]:
    by_year: Dict[int, Dict[str, Any]] = {}
    for r in results:
        if r.get("statement_type") != statement_type:
            continue
        model = r.get("model")
        year = getattr(model, "rok", None) if model is not None else (r.get("raw") or {}).get("rok")
        if not isinstance(year, int):
            continue
        prev = by_year.get(year)
        if prev is None:
            by_year[year] = r
        else:
            # prefer OK status, or fewer validation errors
            def score(x: Dict[str, Any]) -> Tuple[int, int]:
                status_ok = 1 if x.get("status") == "ok" else 0
                err_count = len(x.get("validation_errors") or [])
                return (status_ok, -err_count)
            if score(r) > score(prev):
                by_year[year] = r
    return by_year


def validate_interstatement(results: List[Dict[str, Any]], tolerance: int) -> List[str]:
    """Perform interstatement checks and return a list of plain-Czech issue messages."""
    issues: List[str] = []

    bs_names = utils.load_balance_sheet_row_names()
    pl_names = utils.load_profit_and_loss_row_names()

    bs_by_year = _pick_best_per_year(results, "rozvaha")
    pl_by_year = _pick_best_per_year(results, "vzz")

    # Within-year linkage: BS row 99 netto == PL row 53 současné
    for year, bs in bs_by_year.items():
        pl = pl_by_year.get(year)
        if not pl:
            continue
        bs_val = _safe_get_bs_value(bs, 99, "netto")
        pl_val = _safe_get_pl_value(pl, 53, "současné")
        if bs_val is None or pl_val is None:
            continue
        if abs(bs_val - pl_val) > tolerance:
            issues.append(
                f"Rok {year}: Rozvaha ř. 99 ({bs_names.get(99, 'ř. 99')}) {bs_val} ≠ Výsledovka ř. 53 ({pl_names.get(53, 'ř. 53')}) {pl_val}. Rozdíl {abs(bs_val - pl_val)} > tolerance {tolerance}."
            )

    # YoY consistency: BS netto_minule vs prior year's netto; PL minulé vs prior year's současné
    for year, bs in bs_by_year.items():
        prev = bs_by_year.get(year - 1)
        if not prev:
            continue
        bs_curr_rows = getattr(bs.get("model"), "data", {}) if bs.get("model") is not None else (bs.get("raw") or {}).get("data", {})
        row_ids = set()
        try:
            row_ids = set(int(k) for k in bs_curr_rows.keys())
        except Exception:
            try:
                row_ids = set(bs_curr_rows.keys())
            except Exception:
                row_ids = set()
        for rid in sorted(row_ids):
            rid_int = int(rid)
            prev_netto = _safe_get_bs_value(prev, rid_int, "netto")
            curr_prev = _safe_get_bs_value(bs, rid_int, "netto_minule")
            if prev_netto is None or curr_prev is None:
                continue
            if abs(curr_prev - prev_netto) > tolerance:
                issues.append(
                    f"Rozvaha, ř. {rid_int} ({bs_names.get(rid_int, str(rid_int))}): rok {year} (sl. minulé) {curr_prev} ≠ rok {year-1} (sl. běžné) {prev_netto}. Rozdíl {abs(curr_prev - prev_netto)} > tolerance {tolerance}."
                )

    for year, pl in pl_by_year.items():
        prev = pl_by_year.get(year - 1)
        if not prev:
            continue
        pl_curr_rows = getattr(pl.get("model"), "data", {}) if pl.get("model") is not None else (pl.get("raw") or {}).get("data", {})
        row_ids = set()
        try:
            row_ids = set(int(k) for k in pl_curr_rows.keys())
        except Exception:
            try:
                row_ids = set(pl_curr_rows.keys())
            except Exception:
                row_ids = set()
        for rid in sorted(row_ids):
            rid_int = int(rid)
            prev_soucasne = _safe_get_pl_value(prev, rid_int, "současné")
            curr_minule = _safe_get_pl_value(pl, rid_int, "minulé")
            if prev_soucasne is None or curr_minule is None:
                continue
            if abs(curr_minule - prev_soucasne) > tolerance:
                issues.append(
                    f"Výsledovka, ř. {rid_int} ({pl_names.get(rid_int, str(rid_int))}): rok {year} (sl. minulé) {curr_minule} ≠ rok {year-1} (sl. běžné) {prev_soucasne}. Rozdíl {abs(curr_minule - prev_soucasne)} > tolerance {tolerance}."
                )

    return issues


