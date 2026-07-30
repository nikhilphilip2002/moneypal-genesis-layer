"""PII masking and role gating (§7.4).

Masked by default, unmasked only for roles that permit it. The masking is applied to result
rows after execution, and PII values are never placed in an LLM prompt at any point — the
deterministic narrator means result rows are never fed back to a model at all, which
removes the vector rather than mitigating it.

A caveat worth restating rather than burying: the current auth is mock tokens with no real
identity verification (`auth.py:13`). This module is only as strong as that login. It is a
real control once auth is real, and a UI convention until then — which is why replacing
mock auth is a go-live blocker in the build plan, not a nice-to-have.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.nlq.catalog import Catalog, get_catalog

# Roles permitted to see unmasked PII. Deliberately a short, explicit list rather than a
# permission flag: adding a role here should require thought.
PII_ROLES = frozenset({"gicc_admin", "gicc_director", "moneypal_admin"})


def may_see_pii(role: str | None) -> bool:
    return (role or "") in PII_ROLES


def mask_name(value: str) -> str:
    """'Rajesh Kumar' -> 'Rajesh K***'. Enough to confirm a match, not to identify."""
    parts = [p for p in str(value).split() if p]
    if not parts:
        return ""
    if len(parts) == 1:
        head = parts[0]
        return head if len(head) <= 2 else f"{head[:2]}{'*' * (len(head) - 2)}"
    return f"{parts[0]} {parts[-1][0]}***"


def mask_identifier(value: str) -> str:
    """'123456784821' -> 'XXXX-XXXX-4821'. Keeps the last four for reconciliation."""
    digits = re.sub(r"\D", "", str(value))
    if len(digits) <= 4:
        return "X" * len(digits)
    return f"XXXX-XXXX-{digits[-4:]}"


def mask_date(value: Any) -> str:
    """A date of birth becomes its year — enough for cohort analysis, not for identity."""
    text = str(value)
    match = re.match(r"(\d{4})", text)
    return f"{match.group(1)}" if match else "****"


def mask_value(value: Any, column_name: str) -> Any:
    if value is None:
        return None
    lowered = column_name.lower()
    if any(token in lowered for token in ("dob", "birth", "doi", "doe")):
        return mask_date(value)
    if any(token in lowered for token in ("pincode", "pin_code", "number", "num", "card", "aadhaar", "pan")):
        return mask_identifier(value)
    if any(token in lowered for token in ("income", "salary")):
        return "***"
    return mask_name(value)


def mask_rows(
    rows: list[dict[str, Any]],
    columns: list[Any],
    *,
    role: str | None,
    catalog: Catalog | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Mask every PII column unless the role permits. Returns (rows, masked column names).

    Operates on the ChartSpec's column metadata rather than guessing from values, so a
    column is masked because the catalog says it is sensitive — not because its contents
    happened to look like a name.
    """
    cat = catalog or get_catalog()
    if may_see_pii(role):
        return rows, []

    pii_column_names = {column for _table, column in cat.pii_columns()}
    catalog_ids = {c.id.split(".")[-1]: c for c in cat.columns.values() if c.is_pii}

    masked_fields: list[str] = []
    for column in columns:
        name = getattr(column, "name", None) or str(column)
        if name in pii_column_names or name in catalog_ids:
            masked_fields.append(name)
            if hasattr(column, "masked"):
                column.masked = True

    if not masked_fields:
        return rows, []

    out = []
    for row in rows:
        masked = dict(row)
        for field in masked_fields:
            if field in masked:
                masked[field] = mask_value(masked[field], field)
        out.append(masked)
    return out, masked_fields


def touches_pii(source_tables: list[str], catalog: Catalog | None = None) -> bool:
    """Whether a query read any PII-bearing table — drives the audit flag."""
    cat = catalog or get_catalog()
    for table_name in source_tables:
        entry = cat.table_by_name(table_name)
        if entry and entry.contains_pii:
            return True
    return False
