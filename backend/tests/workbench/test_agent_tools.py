from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.tool_names import (
    READ_TOOL_OUTPUT,
    SEARCH_CURATED_KNOWLEDGE,
    SEARCH_PUBLIC_WEB,
    SUBMIT_ANSWER,
)
from app.services.workbench import access
from app.mcp.tool_catalog import ToolCatalog
from app.services.workbench.agent_contracts import (
    SubmitAnswerArguments,
    SubmitClarificationArguments,
    SubmitRefusalArguments,
)
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
        READ_TOOL_OUTPUT,
        SEARCH_CURATED_KNOWLEDGE,
        SEARCH_PUBLIC_WEB,
        SUBMIT_ANSWER,
    ]
    assert "query_loan_book" not in RUNTIME_TOOL_POLICIES
    for policy in RUNTIME_TOOL_POLICIES.values():
        assert not hasattr(policy, "arguments_model")
        assert not hasattr(policy, "description")
        assert not hasattr(policy, "handler_key")


@pytest.mark.anyio
async def test_provider_schemas_are_closed_objects_without_unsupported_keywords():
    forbidden = {
        "oneOf",
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
    assert set(definitions) == set(RUNTIME_TOOL_POLICIES)
    assert all(
        definition["parameters"]["properties"]
        for definition in definitions.values()
    )


@pytest.mark.anyio
async def test_policy_omits_live_web_and_filters_curated_domains_without_consent():
    definitions = await _definitions(external=False)
    assert SEARCH_PUBLIC_WEB not in definitions
    domains = definitions[SEARCH_CURATED_KNOWLEDGE]["parameters"][
        "properties"
    ]["domain"]
    assert domains["enum"] == ["concepts"]


@pytest.mark.anyio
async def test_role_policy_removes_forbidden_curated_domains():
    definitions = await _definitions(role="gicc_director", external=True)
    domains = definitions[SEARCH_CURATED_KNOWLEDGE]["parameters"][
        "properties"
    ]["domain"]
    assert "macro" in domains["enum"]
    assert "competitive" not in domains["enum"]
    assert "regulatory" not in domains["enum"]


def test_forged_curated_domain_is_reauthorized_at_validation_time():
    with pytest.raises(AgentToolAccessDenied, match="external source consent"):
        authorize_local_tool_call(
            SEARCH_CURATED_KNOWLEDGE,
            {"domain": "regulatory", "query": "RBI PSL rules"},
            policy=_policy(external=False),
        )


def test_final_answer_requires_database_only_for_query_answer():
    policy = access.build_policy(
        role="admin", external_sources_enabled=False, pinned_source="knowledge"
    )
    authorize_local_tool_call(
        SUBMIT_ANSWER,
        {"submission": {"outcome": "clarify", "message": "Which period?"}},
        policy=policy,
    )
    with pytest.raises(
        AgentToolAccessDenied, match="db: source is unavailable"
    ):
        authorize_local_tool_call(
            SUBMIT_ANSWER,
            {
                "submission": {
                    "outcome": "answer",
                    "message": "",
                    "evidence": [{"query_id": 1}],
                    "visuals": [{"query_id": 1, "view": "table"}],
                }
            },
            policy=policy,
        )


@pytest.mark.anyio
async def test_final_answer_schema_supports_all_terminal_outcomes():
    schema = (await _definitions())[SUBMIT_ANSWER]["parameters"]
    assert list(schema["properties"]) == ["submission"]
    variants = schema["properties"]["submission"]["anyOf"]
    assert len(variants) == 3
    answer, clarify, refuse = (variant["properties"] for variant in variants)
    for variant in variants:
        assert variant["additionalProperties"] is False
        assert variant["required"] == list(variant["properties"])
    assert set(answer) == {
        "outcome",
        "message",
        "evidence",
        "visuals",
    }
    assert answer["outcome"]["enum"] == ["answer"]
    references = answer["evidence"]["items"]["anyOf"]
    assert [set(ref["properties"]) for ref in references] == [
        {"query_id"},
        {"card_reference"},
    ]
    for reference in references:
        assert reference["required"] == list(reference["properties"])
        assert reference["additionalProperties"] is False
    for variant in variants:
        message = variant["properties"]["message"]
        assert message["minLength"] == 1
        assert message["pattern"] == r"\S"
    for variant, model in zip(
        variants,
        (SubmitAnswerArguments, SubmitClarificationArguments, SubmitRefusalArguments),
        strict=True,
    ):
        assert set(variant["required"]) == {
            name for name, field in model.model_fields.items() if field.is_required()
        }
    assert answer["visuals"]["items"]["properties"]["view"]["enum"] == [
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
    assert list(clarify) == ["outcome", "message", "suggestions"]
    assert clarify["outcome"]["enum"] == ["clarify"]
    assert clarify["suggestions"]["maxItems"] == 3
    assert list(refuse) == ["outcome", "message", "reason_code"]
    assert refuse["outcome"]["enum"] == ["refuse"]
    assert refuse["reason_code"]["type"] == "string"
    assert refuse["reason_code"]["enum"] == [
        "out_of_scope",
        "not_in_data",
        "predictive",
        "advice",
        "unsafe",
    ]
