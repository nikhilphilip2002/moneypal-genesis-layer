from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.workbench import access
from app.mcp.tool_catalog import ToolCatalog
from app.services.workbench.agent_tools import (
    RUNTIME_TOOL_POLICIES,
    AgentToolAccessDenied,
    authorize_local_tool_call,
)


@pytest.fixture(autouse=True)
def _connector_settings(monkeypatch):
    monkeypatch.setattr(
        access.settings, "workbench_external_connectors_enabled", True
    )
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)


def _policy(*, role="admin", external=True):
    return access.build_policy(role=role, external_sources_enabled=external)


async def _definitions(*, role="admin", external=True):
    catalog = ToolCatalog()
    await catalog.discover_local()
    return {
        item["function"]["name"]: item["function"]
        for item in await catalog.model_tool_definitions(
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


def test_registry_contains_runtime_policy_only():
    assert list(RUNTIME_TOOL_POLICIES) == [
        "search_curated_knowledge",
        "search_public_web",
        "visualize_query_result",
        "finish_without_data",
        "submit_final_answer",
    ]
    assert "query_loan_book" not in RUNTIME_TOOL_POLICIES
    for policy in RUNTIME_TOOL_POLICIES.values():
        assert not hasattr(policy, "arguments_model")
        assert not hasattr(policy, "description")
        assert not hasattr(policy, "handler_key")


@pytest.mark.anyio
async def test_provider_schemas_are_closed_flat_objects_without_polymorphic_keywords():
    forbidden = {
        "oneOf",
        "anyOf",
        "allOf",
        "discriminator",
        "if",
        "then",
        "else",
        "$ref",
        "$defs",
    }
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
    assert set(definitions) == set(RUNTIME_TOOL_POLICIES) - {
        "visualize_query_result"
    }
    assert all(
        definition["parameters"]["properties"]
        for definition in definitions.values()
    )


@pytest.mark.anyio
async def test_policy_omits_live_web_and_filters_curated_domains_without_consent():
    definitions = await _definitions(external=False)
    assert "search_public_web" not in definitions
    domains = definitions["search_curated_knowledge"]["parameters"][
        "properties"
    ]["domain"]
    assert domains["enum"] == ["concepts"]


@pytest.mark.anyio
async def test_role_policy_removes_forbidden_curated_domains():
    definitions = await _definitions(role="gicc_director", external=True)
    domains = definitions["search_curated_knowledge"]["parameters"][
        "properties"
    ]["domain"]
    assert "macro" in domains["enum"]
    assert "competitive" not in domains["enum"]
    assert "regulatory" not in domains["enum"]


def test_forged_curated_domain_is_reauthorized_at_validation_time():
    with pytest.raises(AgentToolAccessDenied, match="external source consent"):
        authorize_local_tool_call(
            "search_curated_knowledge",
            {"domain": "regulatory", "query": "RBI PSL rules"},
            policy=_policy(external=False),
        )


@pytest.mark.anyio
async def test_final_answer_schema_is_minimal():
    schema = (await _definitions())["submit_final_answer"]["parameters"]
    properties = schema["properties"]

    assert list(properties) == ["insights", "query_id", "view"]
    assert properties["view"]["enum"] == [
        "kpi",
        "line",
        "area",
        "stacked_area",
        "bar",
        "grouped_bar",
        "table",
        "donut",
        "scatter",
        "heatmap",
    ]
