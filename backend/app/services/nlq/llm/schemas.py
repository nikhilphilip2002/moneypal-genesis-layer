"""JSON schemas passed as `response_format` for constrained decoding.

Under llama.cpp's `json_schema` mode the model *cannot* emit malformed JSON, which reduces
validation to semantics — does this metric exist? — rather than parsing. The schema is
derived from the Pydantic contracts so the two cannot drift: a field added to QuerySpec
appears here automatically.

Two deliberate deviations from a naive dump of the Pydantic schema:

* The metric and dimension enums are injected from the live catalog, so the model is
  physically unable to name a metric that does not exist. This removes the single largest
  category of planner error at the decoding layer rather than catching it downstream.
* `reasoning` is capped short. Chain-of-thought inside a constrained-decode payload bloats
  generation and measurably degrades the structured fields around it.
"""

from __future__ import annotations

from typing import Any

from app.services.nlq.catalog import Catalog, get_catalog

PROMPT_VERSION = "planner-v1"


def plan_schema(catalog: Catalog | None = None) -> dict[str, Any]:
    """The tagged union the planner must emit."""
    cat = catalog or get_catalog()
    metric_ids = sorted(cat.metrics)
    dimension_ids = sorted(cat.dimensions)
    filterable = sorted(d for d in cat.dimensions if not cat.dimensions[d].is_time)

    period = {
        "type": "object",
        "properties": {
            "grain": {
                "type": "string",
                "enum": ["day", "week", "month", "quarter", "fy", "year", "all"],
            },
            "start": {"type": "string", "description": "YYYY-MM-DD"},
            "end": {"type": "string", "description": "YYYY-MM-DD"},
            "relative": {
                "type": "string",
                "enum": [
                    "today", "yesterday", "this_month", "last_month", "this_quarter",
                    "last_quarter", "this_fy", "last_fy", "fy_to_date", "ytd",
                    "last_12_months", "last_30_days", "last_90_days", "all_time",
                ],
            },
        },
        "additionalProperties": False,
    }

    query_spec = {
        "type": "object",
        "properties": {
            "metrics": {
                "type": "array",
                "items": {"type": "string", "enum": metric_ids},
                "minItems": 1,
            },
            "dimensions": {
                "type": "array",
                "items": {"type": "string", "enum": dimension_ids},
            },
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "enum": filterable},
                        "op": {
                            "type": "string",
                            "enum": [
                                "eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte",
                                "between", "contains", "is_null",
                            ],
                        },
                        "value": {},
                    },
                    "required": ["field", "op"],
                    "additionalProperties": False,
                },
            },
            "period": period,
            "compare_to": period,
            "order_by": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "direction": {"type": "string", "enum": ["asc", "desc"]},
                },
                "required": ["field"],
                "additionalProperties": False,
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 5000},
        },
        "required": ["metrics", "period"],
        "additionalProperties": False,
    }

    confidence = {"type": "number", "minimum": 0, "maximum": 1}
    reasoning = {"type": "string", "maxLength": 200}

    # A real tagged union, one branch per route. Flattening these into one object with
    # `required: ["route"]` looks equivalent and is not: the grammar would then let the
    # model open `{"route":"queryspec"`, emit `confidence` and `reasoning`, and close —
    # a structurally valid plan with no spec in it, which is a silent demotion to
    # text-to-SQL and, from the user's seat, "not answerable from the loan book".
    #
    # Field order is load-bearing too. Constrained decoding emits properties in schema
    # order, so the payload that decides the answer is written before the prose about it;
    # if generation is cut short it is the commentary that is lost, not the spec.
    return {
        "title": "PlanResult",
        "anyOf": [
            {
                "type": "object",
                "properties": {
                    "route": {"const": "queryspec"},
                    "spec": query_spec,
                    "confidence": confidence,
                    "reasoning": reasoning,
                },
                "required": ["route", "spec", "confidence"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "route": {"const": "sql"},
                    "intent": {"type": "string"},
                    "tables": {"type": "array", "items": {"type": "string"}},
                    "confidence": confidence,
                    "reasoning": reasoning,
                },
                "required": ["route", "intent", "tables"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "route": {"const": "clarify"},
                    "question": {"type": "string"},
                    "suggestions": {
                        "type": "array", "items": {"type": "string"}, "maxItems": 3,
                    },
                },
                "required": ["route", "question"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "route": {"const": "refuse"},
                    "reason": {
                        "type": "string",
                        "enum": [
                            "out_of_scope", "not_in_data", "predictive", "advice", "unsafe",
                        ],
                    },
                    "message": {"type": "string"},
                    "examples": {
                        "type": "array", "items": {"type": "string"}, "maxItems": 3,
                    },
                },
                "required": ["route", "reason"],
                "additionalProperties": False,
            },
        ],
    }


def rewrite_schema() -> dict[str, Any]:
    """Follow-up resolution: "and by branch?" -> a complete, standalone question."""
    return {
        "title": "RewrittenQuestion",
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "is_followup": {"type": "boolean"},
        },
        "required": ["question", "is_followup"],
        "additionalProperties": False,
    }


def sql_schema() -> dict[str, Any]:
    """Text-to-SQL output. One statement, and the model states its own tables so the
    validator can cross-check what it claims against what it actually wrote."""
    return {
        "title": "GeneratedSql",
        "type": "object",
        "properties": {
            "sql": {"type": "string"},
            "tables": {"type": "array", "items": {"type": "string"}},
            "explanation": {"type": "string", "maxLength": 300},
        },
        "required": ["sql", "tables"],
        "additionalProperties": False,
    }
