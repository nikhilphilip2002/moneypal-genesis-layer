from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.nlq.catalog import get_catalog
from app.services.workbench import access
from app.services.workbench.agent_contracts import (
    FinishWithoutDataArguments,
    QueryMetricsArguments,
)
from app.services.workbench.agent_tools import (
    AGENT_TOOLS,
    AgentToolAccessDenied,
    AgentToolArgumentsInvalid,
    native_tool_definitions,
    validate_agent_arguments,
)


@pytest.fixture(autouse=True)
def _connector_settings(monkeypatch):
    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)


def _policy(*, role="admin", external=True):
    return access.build_policy(role=role, external_sources_enabled=external)


def _definitions(*, role="admin", external=True):
    return {
        item["function"]["name"]: item["function"]
        for item in native_tool_definitions(_policy(role=role, external=external))
    }


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def test_registry_exposes_concrete_flat_tools():
    assert list(AGENT_TOOLS) == [
        "query_metrics",
        "lookup_records",
        "run_analysis",
        "create_worklist",
        "generate_briefing",
        "run_validated_query",
        "inspect_loan_catalog",
        "search_curated_knowledge",
        "search_public_web",
        "finish_without_data",
    ]
    assert "query_loan_book" not in AGENT_TOOLS


def test_provider_schemas_are_closed_flat_objects_without_polymorphic_keywords():
    forbidden = {"oneOf", "anyOf", "allOf", "discriminator", "if", "then", "else", "$ref", "$defs"}
    for definition in _definitions().values():
        schema = definition["parameters"]
        assert len(json.dumps(schema, separators=(",", ":"))) < 100_000
        assert definition["strict"] is True
        assert schema["type"] == "object"
        for node in _walk(schema):
            if not isinstance(node, dict):
                continue
            assert not (forbidden & set(node))
            node_type = node.get("type")
            if node_type == "object" or (
                isinstance(node_type, list) and "object" in node_type
            ):
                assert node["additionalProperties"] is False
                assert node["required"] == list(node.get("properties", {}))


def test_catalog_enums_are_injected_into_the_matching_tools():
    catalog = get_catalog()
    definitions = _definitions()
    metrics = definitions["query_metrics"]["parameters"]["properties"]
    assert set(metrics["metrics"]["items"]["enum"]) == set(catalog.metrics)
    assert set(metrics["dimensions"]["items"]["enum"]) == set(catalog.dimensions)
    assert set(
        definitions["run_analysis"]["parameters"]["properties"]["analysis_id"]["enum"]
    ) == set(catalog.analyses)
    assert set(
        definitions["create_worklist"]["parameters"]["properties"]["worklist_id"]["enum"]
    ) == set(catalog.worklists.presets)
    assert set(
        definitions["generate_briefing"]["parameters"]["properties"]["persona_id"]["enum"]
    ) == set(catalog.personas)
    assert set(
        definitions["run_validated_query"]["parameters"]["properties"]["tables"]["items"]["enum"]
    ) == set(catalog.allowed_tables())
    assert set(
        definitions["inspect_loan_catalog"]["parameters"]["properties"]["tables"]["items"]["enum"]
    ) == set(catalog.allowed_tables())


def test_retrieved_catalog_entries_can_narrow_tool_enums():
    definitions = {
        item["function"]["name"]: item["function"]
        for item in native_tool_definitions(
            _policy(),
            metric_ids=("receipt_total", "receipt_count"),
            dimension_ids=("month", "receipt_mode"),
            filter_dimension_ids=("receipt_mode",),
            table_names=("gold.semantic_receipt_adjustment_event",),
        )
    }
    metric_properties = definitions["query_metrics"]["parameters"]["properties"]
    assert metric_properties["metrics"]["items"]["enum"] == [
        "receipt_total", "receipt_count",
    ]
    assert metric_properties["dimensions"]["items"]["enum"] == [
        "month", "receipt_mode",
    ]
    assert metric_properties["filters"]["items"]["properties"]["field"]["enum"] == [
        "receipt_mode",
    ]
    assert metric_properties["having"]["items"]["properties"]["field"]["enum"] == [
        "receipt_total", "receipt_count",
    ]
    assert definitions["run_validated_query"]["parameters"]["properties"]["tables"][
        "items"
    ]["enum"] == ["gold.semantic_receipt_adjustment_event"]


def test_time_only_context_forbids_invented_filters():
    definitions = {
        item["function"]["name"]: item["function"]
        for item in native_tool_definitions(
            _policy(),
            metric_ids=("disbursement_total",),
            dimension_ids=("month",),
            tool_names=("query_metrics",),
        )
    }
    filters = definitions["query_metrics"]["parameters"]["properties"]["filters"]
    assert filters["maxItems"] == 0


def test_empty_dimension_context_forbids_invented_groupings():
    definitions = {
        item["function"]["name"]: item["function"]
        for item in native_tool_definitions(
            _policy(),
            metric_ids=("share_capital", "capital_reserves"),
            dimension_ids=(),
            tool_names=("query_metrics",),
        )
    }
    dimensions = definitions["query_metrics"]["parameters"]["properties"]["dimensions"]
    assert dimensions["maxItems"] == 0


def test_policy_omits_live_web_and_filters_curated_domains_without_consent():
    definitions = _definitions(external=False)
    assert "search_public_web" not in definitions
    domains = definitions["search_curated_knowledge"]["parameters"]["properties"]["domain"]
    assert domains["enum"] == ["concepts", "schema"]


def test_role_policy_removes_forbidden_curated_domains():
    definitions = _definitions(role="gicc_director", external=True)
    domains = definitions["search_curated_knowledge"]["parameters"]["properties"]["domain"]
    assert "macro" in domains["enum"]
    assert "competitive" not in domains["enum"]
    assert "regulatory" not in domains["enum"]


def test_canonical_model_fields_match_provider_schema_properties():
    definitions = _definitions()
    for name, tool in AGENT_TOOLS.items():
        assert set(tool.arguments_model.model_fields) == set(
            definitions[name]["parameters"]["properties"]
        )


def test_query_metrics_validates_with_full_queryspec_contract():
    parsed = validate_agent_arguments(
        "query_metrics",
        {
            "metrics": ["par_30"],
            "dimensions": ["branch"],
            "period": {"relative": "this_month"},
        },
        policy=_policy(),
    )
    assert isinstance(parsed, QueryMetricsArguments)
    assert parsed.metrics == ["par_30"]


@pytest.mark.parametrize(
    "name,arguments,error",
    [
        (
            "query_metrics",
            {"metrics": ["not_a_metric"], "dimensions": [], "period": {"relative": "this_month"}},
            "unknown metric",
        ),
        ("run_analysis", {"analysis_id": "not_an_analysis"}, "unknown analysis"),
        ("create_worklist", {"worklist_id": "not_a_worklist"}, "unknown worklist"),
        ("generate_briefing", {"persona_id": "not_a_persona"}, "unknown persona"),
        ("run_validated_query", {"intent": "x", "tables": ["private.secret"]}, "unknown catalog tables"),
        (
            "lookup_records",
            {
                "selector": "customer_id",
                "value": "42",
                "detail": "loan_details",
                "metrics": ["par_30"],
            },
            "Extra inputs are not permitted",
        ),
    ],
)
def test_execution_boundary_rejects_unknown_catalog_values_and_foreign_fields(
    name, arguments, error,
):
    with pytest.raises(AgentToolArgumentsInvalid, match=error):
        validate_agent_arguments(name, arguments, policy=_policy())


def test_forged_curated_domain_is_reauthorized_at_validation_time():
    with pytest.raises(AgentToolAccessDenied, match="external source consent"):
        validate_agent_arguments(
            "search_curated_knowledge",
            {"domain": "regulatory", "query": "RBI PSL rules"},
            policy=_policy(external=False),
        )


@pytest.mark.parametrize(
    "arguments,error",
    [
        (
            {
                "outcome": "clarify",
                "message": "Which period?",
                "suggestions": [],
                "reason_code": "out_of_scope",
            },
            "clarification cannot include",
        ),
        (
            {
                "outcome": "refuse",
                "message": "I cannot do that.",
                "suggestions": [],
                "reason_code": None,
            },
            "refusal requires",
        ),
    ],
)
def test_terminal_tool_cross_field_rules(arguments, error):
    with pytest.raises(AgentToolArgumentsInvalid, match=error):
        validate_agent_arguments("finish_without_data", arguments, policy=_policy())


def test_valid_terminal_tool_is_typed():
    parsed = validate_agent_arguments(
        "finish_without_data",
        {
            "outcome": "clarify",
            "message": "Which reporting period should I use?",
            "suggestions": ["This month", "Last month"],
            "reason_code": None,
        },
        policy=_policy(),
    )
    assert isinstance(parsed, FinishWithoutDataArguments)
