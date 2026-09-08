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
        r"these\s+(?:customers|loans|accounts|borrowers|records)|"
        r"those\s+(?:customers|loans|accounts|borrowers|records))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:(?:and|also|now|ok|please)\s+)?(?:include|add|show|give|fetch|list)\s+"
        r"(?:(?:me|the|us)\s+)?(?P<detail>.+?)"
        r"(?:\s+(?:with|for|from|in|to)\s+(?:the\s+)?above(?:\s+details)?)?[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:(?:and|also|now|ok)\s+)?(?:also\s+)?(?:add|include)\s+",
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
    if prior_tool == "lookup_records" or prior_binding.get("entity"):
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

        if not new_fields and not prior_fields:
            return None

        all_fields = list(prior_fields) + [f for f in new_fields if f not in prior_fields]
        selector = prior_entity.get("selector", "agent")
        value = prior_entity.get("value", "")
        selector_name = "agent" if "agent" in selector else selector.replace("_", " ")

        field_descriptions = [FIELD_LABELS.get(f, f.replace("_", " ")) for f in all_fields]
        fields_str = ", ".join(field_descriptions)

        if value:
            intent = f"List customers under {selector_name} {value} with {fields_str}"
        else:
            intent = f"List customer records with {fields_str}"

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

        added_dims: list[str] = []
        for dim in cat.dimensions.values():
            phrases = [dim.label, *dim.synonyms]
            if any(_catalog_phrase_matches(question, phrase) for phrase in phrases):
                if dim.id not in prior_dimensions and dim.id not in added_dims:
                    added_dims.append(dim.id)

        if not added_dims:
            return None

        all_dimensions = list(prior_dimensions) + added_dims
        metrics_str = ", ".join(prior_metrics)
        dims_str = " and ".join(all_dimensions)
        intent = f"Show {metrics_str} broken down by {dims_str}"

        return ResolvedFollowup(
            standalone_intent=intent,
            tool="query_metrics",
            tables=tuple(prior_binding.get("tables", ())),
            output_fields=tuple(all_dimensions + prior_metrics),
            filters=tuple(prior_filters),
            retained_fields=tuple(prior_dimensions),
            new_fields=tuple(added_dims),
            added_dimensions=tuple(added_dims),
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
