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
    allowed_tables = sorted(cat.allowed_tables())

    from app.services.worklists.rules import FILTERABLE as worklist_filterable

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

    # Shared by the queryspec and analysis branches: a preset is bound to a slice of the
    # book the same way a hand-written question is, so both must accept the same filters.
    filter_item = {
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
                "items": filter_item,
            },
            "having": {
                "type": "array",
                "description": "Conditions on aggregate metric results, applied after grouping.",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "enum": metric_ids},
                        "op": {
                            "type": "string",
                            "enum": ["eq", "ne", "gt", "gte", "lt", "lte", "between", "is_null"],
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
            "as_share": {
                "type": "boolean",
                "description": "True when the question asks for a mix, share, split or "
                "composition rather than a comparison of magnitudes. Selects a "
                "part-to-whole chart; it does not change the numbers.",
            },
            "explain": {
                "type": "boolean",
                "description": "True when the question asks WHY a measure moved rather than "
                "what it is: 'why are collections down', 'what is driving the rise in PAR'. "
                "Requires compare_to and at least one dimension to attribute the change "
                "across. The change is then decomposed into each member's contribution.",
            },
        },
        # `dimensions` is required even though an empty list is valid. Optional properties
        # are skippable under constrained decoding, and models take the shortest legal path
        # through the grammar — "collection efficiency by product" came back with no
        # dimensions, one row, and a KPI tile where a bar chart belonged. Requiring the key
        # forces the model to state the grouping, including stating that there is none.
        "required": ["metrics", "dimensions", "period"],
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
                    "route": {"const": "analysis"},
                    # An enum, so the model can only choose an analysis that exists — the
                    # same discipline as the metric enum, and the reason a preset can never
                    # be half-invented.
                    "analysis_id": {"type": "string", "enum": sorted(cat.analyses)},
                    "period": period,
                    "filters": {"type": "array", "items": filter_item, "maxItems": 4},
                    "confidence": confidence,
                    "reasoning": reasoning,
                },
                "required": ["route", "analysis_id", "confidence"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "route": {"const": "worklist"},
                    "worklist_id": {"type": "string", "enum": sorted(cat.worklists.presets)},
                    # A worklist reads one account-level relation, so it accepts only the
                    # slices that relation carries. Offering the full dimension enum here
                    # would let the model ask for a filter the list cannot honour.
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string", "enum": sorted(worklist_filterable)},
                                "op": {"type": "string", "enum": ["eq", "in"]},
                                "value": {},
                            },
                            "required": ["field", "op", "value"],
                            "additionalProperties": False,
                        },
                        "maxItems": 4,
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    "confidence": confidence,
                    "reasoning": reasoning,
                },
                "required": ["route", "worklist_id", "confidence"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "route": {"const": "briefing"},
                    "persona_id": {"type": "string", "enum": sorted(cat.personas)},
                    "confidence": confidence,
                    "reasoning": reasoning,
                },
                "required": ["route", "persona_id", "confidence"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "route": {"const": "sql"},
                    "intent": {"type": "string"},
                    "tables": {
                        "type": "array",
                        "items": {"type": "string", "enum": allowed_tables},
                    },
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
                    "message": {"type": "string", "maxLength": 200},
                    # No `examples` field: the "try instead" list is served from the
                    # catalog, so letting the model write one only invites it to invent
                    # questions the warehouse cannot answer (see ask.py).
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
