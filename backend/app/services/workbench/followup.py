"""Structural follow-up resolution for Workbench native agent conversations.

Merges prior data query bindings (from lookup_records, query_metrics, or run_validated_query)
with incremental user refinements such as:
- 'include tenure and santioned amount with the above details'
- 'also add tenure and sanction amount'
- 'with the above details, include tenure and sanction amount'
- 'also show monthwise'
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.services.nlq.catalog import Catalog, get_catalog
from app.services.workbench.prompts import _catalog_phrase_matches

logger = logging.getLogger(__name__)

_ELLIPTICAL_PATTERNS = (
    re.compile(
        r"\b(?:with\s+(?:the\s+)?above(?:\s+details)?|for\s+(?:the\s+)?above(?:\s+details)?|"
        r"above\s+details|above\s+records|from\s+(?:the\s+)?above|for\s+them|"
        r"these\s+(?:customers|loans|accounts|borrowers|records|sanctions)|"
        r"those\s+(?:customers|loans|accounts|borrowers|records|sanctions)|"
        r"along\s+with\s+(?:the\s+)?above|as\s+well|too)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:(?:and|also|now|ok|please|can\s+you)\s+)?(?:also\s+)?(?:include|add|show|give|fetch|list|display)\s+"
        r"(?:(?:me|the|us)\s+)?(?P<detail>.+?)"
        r"(?:\s+(?:with|for|from|in|to)\s+(?:the\s+)?above(?:\s+details)?)?[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:(?:and|also|now|ok)\s+)?(?:also\s+)?(?:add|include)\s+",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:break\s*(?:that|it|this)?\s*down|breakdown|broken\s+down|group\s*(?:that|it|this)?\s*by|grouped\s+by|"
        r"slice\s*(?:that|it|this)?\s*by|\w+wise|monthly|quarterly|yearly|daily|annually)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:filter\s*(?:that|it|this)?\s*(?:to|by)|only\s+(?:active|closed|standard|regular|npa|converted)|"
        r"just\s+(?:active|closed|standard)|where\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:compare\s*(?:that|it|this)?\s*(?:with|to)|versus|vs\.?|"
        r"what\s+about\s+(?:the\s+)?(?:previous|prior|last|next|past))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:which\s+(?:branch|agent|scheme|product|vendor)|how\s+much\s+was|where\s+are\s+they|"
        r"show\s+the\s+monthly\s+trend|what\s+is\s+the\s+total\s+outstanding|summarize\s+our\s+total\s+exposure)\b",
        re.IGNORECASE,
    ),
)

FIELD_LABELS: dict[str, str] = {
    "customer_id": "customer ID",
    "customer_name": "customer name",
    "borrower_name": "borrower name",
    "sanction_amount": "sanction amount",
    "sanction_date": "sanction date",
    "disbursed_amount": "disbursed amount",
    "interest_rate": "interest rate",
    "number_of_emis": "tenure (number of EMIs)",
    "emi_amount": "EMI amount",
    "loan_account_number": "loan account number",
    "loan_status": "loan status",
    "scheme_name": "scheme name",
    "scheme_code": "scheme code",
    "branch_code": "branch code",
    "application_branch_code": "branch code",
    "dpd": "days past due",
    "days_past_due": "days past due",
    "principal_outstanding": "principal outstanding",
    "current_balance": "outstanding balance",
    "branch_name": "branch name",
    "account_status": "account status",
    "document_type": "document type",
    "expiry_date": "expiry date",
    "occupation_type": "occupation",
    "gender": "gender",
}


@dataclass(frozen=True, slots=True)
class ResolvedFollowup:
    standalone_intent: str
    tool: str
    tables: tuple[str, ...]
    output_fields: tuple[str, ...]
    filters: tuple[dict[str, Any], ...]
    retained_fields: tuple[str, ...]
    new_fields: tuple[str, ...]
    added_dimensions: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    period: dict[str, Any] | None = None
    entity: dict[str, Any] | None = None


def is_followup_question(question: str) -> bool:
    """Detect elliptical follow-ups referencing prior conversation data."""
    q = question.strip()
    for pattern in _ELLIPTICAL_PATTERNS:
        if pattern.search(q):
            return True
    return False


def resolve_followup(
    question: str,
    prior_binding: dict[str, Any],
    catalog: Catalog | None = None,
) -> ResolvedFollowup | None:
    """Resolve an elliptical question into a standalone governed intent.

    Merges prior bindings (entity/agent, filters, tables, prior fields) with newly
    requested columns or dimensions.
    """
    if not is_followup_question(question):
        return None

    cat = catalog or get_catalog()
    prior_tool = prior_binding.get("tool", "")

    # Case 1: Prior lookup_records (e.g. customers under vanitha) or record-level query
    if prior_tool == "lookup_records" or prior_binding.get("entity") or (
        prior_tool == "run_validated_query" and prior_binding.get("entity")
    ):
        prior_tables = list(prior_binding.get("tables") or ["gold.semantic_loan_account"])
        prior_entity = dict(prior_binding.get("entity") or {})
        prior_filters = list(prior_binding.get("filters") or [])
        prior_fields = list(prior_binding.get("output_fields") or [])

        detail = prior_entity.get("detail", "")
        if detail in {"agent_customers", "branch_customers"} or "customer" in detail:
            for default_col in ["customer_id", "customer_name"]:
                if default_col not in prior_fields:
                    prior_fields.append(default_col)

        # Detect newly requested columns from question
        new_fields: list[str] = []
        for table_name in prior_tables:
            for col in cat.columns_for(table_name):
                phrases = [col.label, *col.synonyms]
                if any(_catalog_phrase_matches(question, phrase) for phrase in phrases):
                    if col.column not in new_fields and col.column not in prior_fields:
                        new_fields.append(col.column)

        q_lower = question.lower()
        if ("branch" in q_lower or "where are they" in q_lower):
            for cand in ["branch_code", "application_branch_code", "branch_name"]:
                if cand not in new_fields and cand not in prior_fields:
                    if any(c.column == cand for c in cat.columns_for(prior_tables[0])):
                        new_fields.append(cand)
                        break
        if "trend" in q_lower or "monthly" in q_lower:
            if "sanction_date" not in new_fields and "sanction_date" not in prior_fields:
                if any(c.column == "sanction_date" for c in cat.columns_for(prior_tables[0])):
                    new_fields.append("sanction_date")
        if "outstanding" in q_lower or "exposure" in q_lower or "balance" in q_lower:
            for cand in ["principal_outstanding", "current_balance", "sanction_amount"]:
                if cand not in new_fields and cand not in prior_fields:
                    if any(c.column == cand for c in cat.columns_for(prior_tables[0])):
                        new_fields.append(cand)
                        break

        # Check filter refinements
        if re.search(r"\bactive\b", question, re.I):
            if not any(f.get("field") == "loan_status" for f in prior_filters):
                prior_filters.append({"field": "loan_status", "operator": "eq", "value": "active"})
        if re.search(r"\bstandard\b", question, re.I):
            if not any(f.get("field") in {"account_status", "loan_status"} for f in prior_filters):
                prior_filters.append({"field": "account_status", "operator": "eq", "value": "standard"})

        all_fields = list(prior_fields) + [f for f in new_fields if f not in prior_fields]
        selector = prior_entity.get("selector", "agent")
        value = prior_entity.get("value", "")
        selector_name = "agent" if "agent" in selector else selector.replace("_", " ")

        field_descriptions = [FIELD_LABELS.get(f, f.replace("_", " ")) for f in all_fields]
        fields_str = ", ".join(field_descriptions) if field_descriptions else "records"

        filter_desc = []
        for flt in prior_filters:
            fld = flt.get("field", "")
            val = flt.get("value", "")
            if fld and val:
                filter_desc.append(f"{fld} = {val}")
        filter_str = f" filtered to {', '.join(filter_desc)}" if filter_desc else ""

        if value:
            intent = f"List customers under {selector_name} {value} with {fields_str}{filter_str}"
        else:
            intent = f"List customer records with {fields_str}{filter_str}"

        return ResolvedFollowup(
            standalone_intent=intent,
            tool="run_validated_query",
            tables=tuple(prior_tables),
            output_fields=tuple(all_fields),
            filters=tuple(prior_filters),
            retained_fields=tuple(prior_fields),
            new_fields=tuple(new_fields),
            entity=prior_entity,
        )

    # Case 2: Prior query_metrics follow-up (e.g. adding a dimension like month or scheme)
    if prior_tool == "query_metrics":
        prior_metrics = list(prior_binding.get("metrics") or [])
        prior_dimensions = list(prior_binding.get("dimensions") or [])
        prior_filters = list(prior_binding.get("filters") or [])
        prior_period = prior_binding.get("period")

        added_dims: list[str] = []
        for dim in cat.dimensions.values():
            phrases = [dim.label, dim.id, *dim.synonyms]
            if any(_catalog_phrase_matches(question, phrase) for phrase in phrases):
                if dim.id not in prior_dimensions and dim.id not in added_dims:
                    added_dims.append(dim.id)

        # Keyword matching for common dimension aliases
        q_lower = question.lower()
        if re.search(r"\b(?:schemewise|by\s+scheme|schemes?)\b", q_lower):
            target_dim = "application_scheme" if "application" in q_lower else "scheme"
            if target_dim in cat.dimensions and target_dim not in prior_dimensions and target_dim not in added_dims:
                added_dims.append(target_dim)
        if re.search(r"\b(?:branchwise|by\s+(?:application\s+)?branch|branches?)\b", q_lower):
            target_dim = "application_branch" if "application" in q_lower else "branch"
            if target_dim in cat.dimensions and target_dim not in prior_dimensions and target_dim not in added_dims:
                added_dims.append(target_dim)
        if re.search(r"\b(?:monthwise|monthly|by\s+month)\b", q_lower):
            if "month" in cat.dimensions and "month" not in prior_dimensions and "month" not in added_dims:
                added_dims.append("month")
        if re.search(r"\b(?:gender|genderwise)\b", q_lower):
            if "gender" in cat.dimensions and "gender" not in prior_dimensions and "gender" not in added_dims:
                added_dims.append("gender")

        # Period comparisons or filters
        compare_requested = bool(re.search(r"\b(?:compare|versus|vs\.?|previous|prior|last)\b", q_lower))

        if not added_dims and not prior_metrics and not compare_requested:
            return None

        all_dimensions = list(prior_dimensions) + [d for d in added_dims if d not in prior_dimensions]
        metrics_str = ", ".join(prior_metrics) if prior_metrics else "metrics"
        dims_str = " and ".join(all_dimensions)

        if compare_requested and not dims_str:
            intent = f"Compare {metrics_str} with previous period"
        elif dims_str:
            intent = f"Show {metrics_str} broken down by {dims_str}"
        else:
            intent = f"Show {metrics_str}"

        return ResolvedFollowup(
            standalone_intent=intent,
            tool="query_metrics",
            tables=tuple(prior_binding.get("tables", ())),
            output_fields=tuple(all_dimensions + prior_metrics),
            filters=tuple(prior_filters),
            retained_fields=tuple(prior_dimensions),
            new_fields=tuple(added_dims),
            added_dimensions=tuple(added_dims),
            metrics=tuple(prior_metrics),
            dimensions=tuple(all_dimensions),
            period=prior_period,
        )

    # Case 3: Prior run_validated_query follow-up
    if prior_tool == "run_validated_query":
        prior_tables = list(prior_binding.get("tables") or ["gold.semantic_loan_account"])
        prior_intent = str(prior_binding.get("intent", ""))

        new_fields = []
        for table_name in prior_tables:
            for col in cat.columns_for(table_name):
                phrases = [col.label, *col.synonyms]
                if any(_catalog_phrase_matches(question, phrase) for phrase in phrases):
                    if col.column not in new_fields:
                        new_fields.append(col.column)

        field_descriptions = [FIELD_LABELS.get(f, f.replace("_", " ")) for f in new_fields]
        additions_str = ", ".join(field_descriptions) if field_descriptions else question
        intent = f"{prior_intent}; include {additions_str}"

        return ResolvedFollowup(
            standalone_intent=intent,
            tool="run_validated_query",
            tables=tuple(prior_tables),
            output_fields=tuple(new_fields),
            filters=(),
            retained_fields=(),
            new_fields=tuple(new_fields),
        )

    return None
