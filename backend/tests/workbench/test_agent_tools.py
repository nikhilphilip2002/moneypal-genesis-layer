from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.workbench import access
from app.mcp import workbench_client
from app.services.workbench.agent_contracts import FinishWithoutDataArguments
from app.services.workbench.agent_tools import (
    AGENT_TOOLS,
    AgentToolAccessDenied,
    AgentToolArgumentsInvalid,
    validate_agent_arguments,
)


@pytest.fixture(autouse=True)
def _connector_settings(monkeypatch):
    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)


def _policy(*, role="admin", external=True):
    return access.build_policy(role=role, external_sources_enabled=external)


async def _definitions(*, role="admin", external=True):
    return {
        item["function"]["name"]: item["function"]
        for item in await workbench_client.model_tool_definitions(
            _policy(role=role, external=external)
        )
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
        "search_curated_knowledge",
        "search_public_web",
        "visualize_query_result",
        "finish_without_data",
        "submit_final_answer",
    ]
    assert "query_loan_book" not in AGENT_TOOLS


@pytest.mark.anyio
async def test_provider_schemas_are_closed_flat_objects_without_polymorphic_keywords():
    forbidden = {"oneOf", "anyOf", "allOf", "discriminator", "if", "then", "else", "$ref", "$defs"}
    for definition in (await _definitions()).values():
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


@pytest.mark.anyio
async def test_every_authorized_tool_is_offered_with_its_full_schema():
    """Every policy-authorized local tool is offered with its complete schema."""
    definitions = await _definitions()
    assert set(definitions) == set(AGENT_TOOLS)
    assert all(definition["parameters"]["properties"] for definition in definitions.values())


@pytest.mark.anyio
async def test_policy_omits_live_web_and_filters_curated_domains_without_consent():
    definitions = await _definitions(external=False)
    assert "search_public_web" not in definitions
    domains = definitions["search_curated_knowledge"]["parameters"]["properties"]["domain"]
    assert domains["enum"] == ["concepts"]


@pytest.mark.anyio
async def test_role_policy_removes_forbidden_curated_domains():
    definitions = await _definitions(role="gicc_director", external=True)
    domains = definitions["search_curated_knowledge"]["parameters"]["properties"]["domain"]
    assert "macro" in domains["enum"]
    assert "competitive" not in domains["enum"]
    assert "regulatory" not in domains["enum"]


@pytest.mark.anyio
async def test_canonical_model_fields_match_provider_schema_properties():
    definitions = await _definitions()
    for name, tool in AGENT_TOOLS.items():
        assert set(tool.arguments_model.model_fields) == set(
            definitions[name]["parameters"]["properties"]
        )


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


@pytest.mark.anyio
async def test_visualization_schema_is_compact_and_carries_aggregation_guidance():
    schema = (await _definitions())["visualize_query_result"]["parameters"]
    properties = schema["properties"]

    assert properties["chart_type"]["enum"] == [
        "kpi", "line", "area", "stacked_area", "bar", "grouped_bar", "table",
        "donut", "scatter", "heatmap",
    ]
    assert properties["aggregation"]["description"] == (
        "Use none when each x/series pair is already aggregated; otherwise choose "
        "how to combine multiple y values for the same x/series pair."
    )
    assert "minItems" not in properties["y"]
    assert "maxItems" not in properties["y"]
