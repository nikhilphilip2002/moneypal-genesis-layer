from dataclasses import replace
from types import SimpleNamespace

import pytest
import requests

from app.mcp import workbench_client
from app.mcp.tool_catalog import ToolCatalog
from app.services.workbench import access, customer_details
from app.services.workbench.agent_tools import AgentToolAccessDenied, authorize_local_tool_call


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)


def policy(role="admin", external=True, pinned=None):
    return access.build_policy(role=role, external_sources_enabled=external, pinned_source=pinned)


@pytest.mark.anyio
async def test_discovery_and_toggle():
    catalog = ToolCatalog()
    await catalog.discover_local()
    assert catalog.owner("search_customer_360") == "workbench"
    for external in (True, False):
        definitions = await catalog.model_tool_definitions(policy(external=external))
        assert ("search_customer_360" in {d["function"]["name"] for d in definitions}) is external


@pytest.mark.parametrize("denied", [
    policy(external=False), policy(pinned="knowledge"),
    replace(policy(), role_sources=("db",)),
    replace(policy(), deployment_external_connectors_enabled=False),
])
def test_direct_call_cannot_bypass_policy(denied):
    with pytest.raises(AgentToolAccessDenied):
        authorize_local_tool_call("search_customer_360", {"customer_id": "128"}, policy=denied)


@pytest.mark.anyio
async def test_protocol_found_card_preserves_db_pin(monkeypatch):
    monkeypatch.setattr(customer_details, "_lookup", lambda *args: ([{
        "customer_id": "128", "customer_name": "Example Borrower",
        "occupation": "Farmer", "source_name": "Field report",
        "scraped_snippet": "Credit assessment notes", "secret_unknown_field": "Never returned",
    }], False))
    ctx = SimpleNamespace(
        user="test", role="admin", conversation_id="customer360-test", turn_id="turn",
        source_policy=policy(pinned="db"), deadline_s=25, question="Customer 128",
        catalog_version="test", private_entities=(), query_id=None, attempt_id=None,
    )
    data = await workbench_client.call_tool(
        "search_customer_360", {"customer_id": "128", "entity_type": "customer"}, context=ctx,
    )
    assert data["card"]["kind"] == "customer_360"
    assert data["card"]["payload"]["records"][0]["snippet"] == "Credit assessment notes"
    assert "Never returned" not in str(data)


@pytest.mark.anyio
async def test_missing_and_unavailable_are_distinct(monkeypatch):
    monkeypatch.setattr(customer_details, "_lookup", lambda *args: ([], False))
    missing = await customer_details.search_customer_details("missing", entity_type="customer", role="admin", policy=policy())
    assert missing.payload["status"] == "not_found"
    assert missing.summary == "Couldn't find external data for this customer."
    def fail(*args):
        raise requests.ConnectionError("private connection details")
    monkeypatch.setattr(customer_details, "_lookup", fail)
    unavailable = await customer_details.search_customer_details("128", entity_type="customer", role="admin", policy=policy())
    assert unavailable.payload["status"] == "unavailable"
    assert not unavailable.complete
    assert "private connection details" not in str(unavailable.as_dict())


@pytest.mark.anyio
async def test_standard_role_never_receives_pii_or_free_text(monkeypatch):
    monkeypatch.setattr(access.settings, "nlq_open_pii_access", True)
    monkeypatch.setattr(customer_details, "_lookup", lambda *args: ([{
        "customer_id": "private-id", "customer_name": "Secret Name",
        "scraped_snippet": "PAN ABCDE1234F and Secret Name", "source_name": "Secret Name report",
    }], False))
    result = await customer_details.search_customer_details("private-id", entity_type="customer", role="gicc_policy", policy=policy(role="gicc_policy"))
    assert result.payload["status"] == "found"
    assert all(value not in str(result.as_dict()) for value in ("private-id", "Secret Name", "ABCDE1234F"))


@pytest.mark.parametrize("entity_type,field,identifier,values", [
    ("customer", "customer_id", "128", ["128", 128]),
    ("agent", "agent_id", "AG-9", ["AG-9"]),
    ("customer", "customer_id", "00128", ["00128"]),
])
def test_qdrant_filter_uses_exact_entity_identity(monkeypatch, entity_type, field, identifier, values):
    captured = {}
    def post(url, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"result": {"points": [], "next_page_offset": None}})
    monkeypatch.setattr(customer_details.requests, "post", post)
    assert customer_details._lookup(identifier, entity_type) == ([], False)
    assert captured["json"]["filter"]["should"] == [{"key": field, "match": {"value": v}} for v in values]
    assert captured["json"]["with_vector"] is False


def test_qdrant_name_lookup_uses_the_entity_name_field(monkeypatch):
    captured = {}
    def post(url, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"result": {"points": [], "next_page_offset": None}})
    monkeypatch.setattr(customer_details.requests, "post", post)
    assert customer_details._lookup("Swamy", "customer", "name") == ([], False)
    assert captured["json"]["filter"]["should"] == [
        {"key": "customer_name", "match": {"text": "Swamy"}}
    ]


@pytest.mark.anyio
async def test_name_lookup_is_returned_when_the_database_has_no_match(monkeypatch):
    monkeypatch.setattr(customer_details, "_lookup", lambda *args: ([{
        "customer_id": "10597", "customer_name": "Swamy",
        "source_name": "LinkedIn", "scraped_snippet": "External profile",
    }], False))
    result = await customer_details.search_customer_details(
        "Swamy", entity_type="customer", role="admin", policy=policy(), lookup_by="name",
    )
    assert result.payload["status"] == "found"
    assert result.payload["lookup_by"] == "name"
