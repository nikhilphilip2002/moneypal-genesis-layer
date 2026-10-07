from __future__ import annotations

import pytest

from app.services.workbench import access, history, nodes, tools
from app.api.routes.workbench import AskRequest, ToolRequest


@pytest.fixture(autouse=True)
def _connector_settings(monkeypatch):
    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)


def test_source_groups_match_the_product_contract():
    assert access.source_group("db") is access.SourceGroup.INTERNAL_DATA
    assert access.source_group("knowledge") is access.SourceGroup.LOCAL_KNOWLEDGE
    assert access.source_group("macro") is access.SourceGroup.EXTERNAL_INDEXED
    assert access.source_group("competitive") is access.SourceGroup.EXTERNAL_INDEXED
    assert access.source_group("regulatory") is access.SourceGroup.EXTERNAL_INDEXED
    assert access.source_group("email") is access.SourceGroup.EXTERNAL_INDEXED
    assert access.source_group("web") is access.SourceGroup.LIVE_EXTERNAL


def test_api_request_models_default_external_access_off():
    assert AskRequest(question="q").external_sources_enabled is False
    assert ToolRequest().external_sources_enabled is False


def test_api_request_models_default_email_access_off():
    assert AskRequest(question="q").email_enabled is False


def test_default_policy_keeps_internal_sources_and_blocks_all_external_sources():
    policy = access.build_policy(role="admin", external_sources_enabled=False)
    assert {"db", "knowledge"} <= set(policy.effective_sources)
    assert not ({"macro", "competitive", "regulatory", "email", "web"} & set(policy.effective_sources))


def test_email_switch_grants_only_the_mailbox():
    policy = access.build_policy(role="admin", external_sources_enabled=False, email_enabled=True)
    assert "email" in policy.effective_sources
    # The dedicated switch must not leak the other external sources.
    assert not ({"macro", "competitive", "regulatory", "web"} & set(policy.effective_sources))
    assert policy.email_enabled is True


def test_legacy_external_consent_still_grants_the_mailbox():
    policy = access.build_policy(role="admin", external_sources_enabled=True, email_enabled=False)
    assert "email" in policy.effective_sources
    assert policy.email_enabled is False


def test_email_access_still_requires_the_mailbox_to_be_deployed(monkeypatch):
    # The mailbox is grouped external_indexed, so it stays subject to the connector
    # deployment flag: consent alone cannot conjure an ingestion service.
    assert "email" in access.build_policy(
        role="admin", email_enabled=True,
    ).effective_sources

    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", False)
    assert "email" not in access.build_policy(
        role="admin", external_sources_enabled=True, email_enabled=True,
    ).effective_sources


@pytest.mark.anyio
async def test_email_handler_refuses_without_the_switch():
    with pytest.raises(access.SourceAccessDenied):
        await nodes.run_email("who approved the limit increase", policy=access.build_policy(role="admin"))


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
async def test_external_pin_and_direct_handler_cannot_bypass_consent():
    policy = access.build_policy(role="admin", external_sources_enabled=False)
    pinned = access.build_policy(
        role="admin", external_sources_enabled=False, pinned_source="macro",
    )
    assert pinned.effective_sources == ()
    with pytest.raises(access.SourceAccessDenied):
        await nodes.run_macro("outlook", policy=policy)


def test_authorized_pin_only_narrows_effective_sources():
    policy = access.build_policy(
        role="admin", external_sources_enabled=True, pinned_source="macro",
    )
    assert policy.effective_sources == ("macro",)
    assert policy.pinned_source == "macro"


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
    assert record.email_enabled is False


def test_history_persists_and_reloads_the_email_switch(monkeypatch):
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    history._MEMORY.clear()
    policy = access.build_policy(role="admin", email_enabled=True)
    history.begin_turn("mail", "alice", "who sent the term sheet", source_policy=policy.snapshot())

    # The turn snapshot carries the flag, so the switch can be restored on reload.
    record = history.get("mail", user="alice")
    turn = next(item for item in record.turns if item["source_policy"])
    assert turn["source_policy"]["email_enabled"] is True

    # And it survives the payload round-trip used to load a conversation.
    payload = history._record_payload(record)
    assert payload["email_enabled"] is True
    restored = history._load("mail", "alice")
    assert restored is not None
    assert restored.email_enabled is True
