from __future__ import annotations

import pytest

from app.services.workbench import access, history, nodes, router, tools
from app.api.routes.workbench import AskRequest, ToolRequest


@pytest.fixture(autouse=True)
def _connector_settings(monkeypatch):
    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)


def test_source_groups_match_the_product_contract():
    assert access.source_group("db") is access.SourceGroup.INTERNAL_DATA
    assert access.source_group("schema") is access.SourceGroup.INTERNAL_METADATA
    assert access.source_group("knowledge") is access.SourceGroup.LOCAL_KNOWLEDGE
    assert access.source_group("macro") is access.SourceGroup.EXTERNAL_INDEXED
    assert access.source_group("competitive") is access.SourceGroup.EXTERNAL_INDEXED
    assert access.source_group("regulatory") is access.SourceGroup.EXTERNAL_INDEXED
    assert access.source_group("web") is access.SourceGroup.LIVE_EXTERNAL


def test_api_request_models_default_external_access_off():
    assert AskRequest(question="q").external_sources_enabled is False
    assert ToolRequest().external_sources_enabled is False


def test_default_policy_keeps_internal_sources_and_blocks_all_external_sources():
    policy = access.build_policy(role="admin", external_sources_enabled=False)
    assert {"db", "schema", "knowledge"} <= set(policy.effective_sources)
    assert not ({"macro", "competitive", "regulatory", "web"} & set(policy.effective_sources))


def test_source_metadata_exposes_group_consent_and_deployment_state():
    metadata = {item["id"]: item for item in access.source_metadata("admin")}
    assert metadata["db"]["group"] == "internal_data"
    assert metadata["db"]["requires_external_consent"] is False
    assert metadata["macro"]["requires_external_consent"] is True
    assert metadata["macro"]["deployment_available"] is True


def test_consent_cannot_grant_role_or_deployment_capability(monkeypatch):
    director = access.build_policy(role="gicc_director", external_sources_enabled=True)
    assert "macro" in director.effective_sources
    assert "competitive" not in director.effective_sources
    assert "regulatory" not in director.effective_sources

    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", False)
    killed = access.build_policy(role="admin", external_sources_enabled=True)
    assert not ({"macro", "competitive", "regulatory", "web"} & set(killed.effective_sources))


@pytest.mark.anyio
async def test_deployment_kill_switch_returns_unavailable_not_consent_prompt(monkeypatch):
    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", False)
    policy = access.build_policy(role="admin", external_sources_enabled=True)
    decision = await router.route("Karnataka GDP outlook", role="admin", policy=policy)
    assert decision.route == "refuse"
    assert decision.reason == "source_unavailable"


@pytest.mark.anyio
async def test_external_only_request_is_deterministic_when_consent_is_off(monkeypatch):
    class MustNotRun:
        async def complete(self, **_kwargs):  # pragma: no cover - a call is the failure
            raise AssertionError("router model must not run")

    monkeypatch.setattr(router.models, "for_step", lambda *args, **kwargs: MustNotRun())
    policy = access.build_policy(role="admin", external_sources_enabled=False)
    decision = await router.route(
        "Explain Karnataka GDP growth trends", role="admin", policy=policy,
    )
    assert decision.route == "refuse"
    assert decision.reason == "external_consent_required"
    assert decision.model == "policy"


@pytest.mark.anyio
async def test_governed_record_lookup_bypasses_router_model(monkeypatch):
    class MustNotRun:
        async def complete(self, **_kwargs):  # pragma: no cover - a call is the failure
            raise AssertionError("router model must not run")

    monkeypatch.setattr(router.models, "for_step", lambda *args, **kwargs: MustNotRun())
    policy = access.build_policy(role="admin", external_sources_enabled=False)
    decision = await router.route(
        "repayment history for customer ID 42", role="admin", policy=policy,
    )
    assert decision.sources == ["db"]
    assert decision.model == "catalog"


@pytest.mark.anyio
async def test_mixed_request_returns_only_db_with_a_limitation_when_off(monkeypatch):
    class MustNotRun:
        async def complete(self, **_kwargs):  # pragma: no cover - a call is the failure
            raise AssertionError("router model must not run")

    monkeypatch.setattr(router.models, "for_step", lambda *args, **kwargs: MustNotRun())
    policy = access.build_policy(role="admin", external_sources_enabled=False)
    decision = await router.route(
        "Compare our loan growth with inflation", role="admin", policy=policy,
    )
    assert decision.route == "dispatch"
    assert decision.sources == ["db"]
    assert decision.limitations
    assert decision.model == "policy"


@pytest.mark.anyio
async def test_external_pin_and_direct_handler_cannot_bypass_consent():
    policy = access.build_policy(role="admin", external_sources_enabled=False)
    decision = await router.route("anything", role="admin", pinned="macro", policy=policy)
    assert decision.reason == "external_consent_required"
    with pytest.raises(access.SourceAccessDenied):
        await nodes.run_macro("outlook", policy=policy)


@pytest.mark.anyio
async def test_direct_tool_cannot_bypass_consent():
    with pytest.raises(tools.ToolAccessError):
        await tools.run_tool(
            "competitor_landscape", role="admin", external_sources_enabled=False,
        )


def test_history_persists_latest_consent_and_turn_snapshot(monkeypatch):
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    history._MEMORY.clear()
    policy = access.build_policy(role="admin", external_sources_enabled=True)
    turn_id = history.begin_turn(
        "consent", "alice", "question", source_policy=policy.snapshot(),
    )
    record = history.get("consent", user="alice")
    assert record is not None
    assert record.external_sources_enabled is True
    turn = next(item for item in record.turns if item["id"] == turn_id)
    assert turn["source_policy"]["effective_sources"] == list(policy.effective_sources)


def test_old_history_defaults_consent_off(monkeypatch):
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    history._MEMORY.clear()
    history.record_turn("old", "question", ["db"], user="alice")
    record = history.get("old", user="alice")
    assert record is not None
    assert record.external_sources_enabled is False
