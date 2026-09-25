"""Comprehensive test suite for external customer profile retrieval and policy."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.mcp import workbench_server
from app.services.workbench import access, customer, nodes
from app.services.workbench.access import SourceAccessDenied
from app.services.workbench.agent_tools import (
    AgentToolAccessDenied,
    native_tool_definitions,
    validate_agent_arguments,
)
from app.services.workbench.outbound_policy import (
    OutboundPolicyDenied,
    authorize_public_search,
)


@pytest.fixture(autouse=True)
def _enable_customer(monkeypatch):
    monkeypatch.setattr(settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(settings, "exa_mcp_enabled", True)
    monkeypatch.setattr(settings, "workbench_customer_source_enabled", True)


# ==============================================================================
# 1. Policy & Authorization Tests
# ==============================================================================

def test_anonymous_request_fails_closed():
    """Anonymous sessions must fail closed for customer profiles."""
    for anon_role in ("", "anonymous", "guest"):
        policy = access.build_policy(role=anon_role, external_sources_enabled=True)
        assert "customer" not in policy.role_sources
        assert "customer" not in policy.effective_sources
        assert policy.allows("customer") is False
        tools = [item["function"]["name"] for item in native_tool_definitions(policy)]
        assert "lookup_customer_profile" not in tools


def test_consent_off_blocks_customer_profile():
    """When external consent toggle is False, customer source is not effective."""
    policy = access.build_policy(role="admin", external_sources_enabled=False)
    assert "customer" in policy.role_sources
    assert "customer" not in policy.effective_sources
    assert policy.allows("customer") is False
    tools = [item["function"]["name"] for item in native_tool_definitions(policy)]
    assert "lookup_customer_profile" not in tools


def test_deployment_off_blocks_customer_profile(monkeypatch):
    """When deployment switch is disabled, customer source is unavailable even with consent."""
    monkeypatch.setattr(settings, "workbench_customer_source_enabled", False)
    policy = access.build_policy(role="admin", external_sources_enabled=True)
    assert "customer" not in policy.deployment_sources
    assert "customer" not in policy.effective_sources
    assert policy.allows("customer") is False
    tools = [item["function"]["name"] for item in native_tool_definitions(policy)]
    assert "lookup_customer_profile" not in tools


def test_external_connectors_disabled_blocks_customer(monkeypatch):
    """When master external connectors switch is off, customer source is omitted."""
    monkeypatch.setattr(settings, "workbench_external_connectors_enabled", False)
    policy = access.build_policy(role="admin", external_sources_enabled=True)
    assert "customer" not in policy.deployment_sources
    assert "customer" not in policy.effective_sources
    assert policy.allows("customer") is False


def test_allowed_roles_can_access_customer():
    """Only admin and gicc_admin roles can access customer profiles initially."""
    for role in ("admin", "gicc_admin"):
        policy = access.build_policy(role=role, external_sources_enabled=True)
        assert "customer" in policy.role_sources
        assert "customer" in policy.effective_sources
        assert policy.allows("customer") is True
        tools = [item["function"]["name"] for item in native_tool_definitions(policy)]
        assert "lookup_customer_profile" in tools


def test_denied_roles_cannot_access_customer():
    """Roles other than admin and gicc_admin cannot see or use customer source."""
    for role in ("gicc_director", "gicc_policy", "auditor"):
        policy = access.build_policy(role=role, external_sources_enabled=True)
        assert "customer" not in policy.role_sources
        assert "customer" not in policy.effective_sources
        assert policy.allows("customer") is False
        tools = [item["function"]["name"] for item in native_tool_definitions(policy)]
        assert "lookup_customer_profile" not in tools


def test_execution_time_validation_denies_unauthorized_call():
    """Direct execution attempt without authorized customer policy raises AgentToolAccessDenied."""
    policy = access.build_policy(role="gicc_director", external_sources_enabled=True)
    with pytest.raises(AgentToolAccessDenied):
        validate_agent_arguments(
            "lookup_customer_profile",
            {"customer_id": "10455"},
            policy=policy,
        )


def test_node_level_require_external_denies_consent_off():
    policy = access.build_policy(role="admin", external_sources_enabled=False)
    with pytest.raises(SourceAccessDenied):
        nodes._require_external(policy, "customer")


# ==============================================================================
# 2. Retrieval & Data Contract Tests
# ==============================================================================

@pytest.mark.anyio
async def test_retrieval_exact_id_matches_and_masks_fields():
    """Exact ID lookup filters by payload and retains only approved fields."""
    mock_point_1 = MagicMock(
        payload={
            "customer_id": "10455",
            "customer_name": "Kiran",
            "occupation": "SALARIED",
            "city": "Mangalore",
            "district": "Dakshina Kannada",
            "channel": "LinkedIn",
            "external_source": "https://in.linkedin.com/in/kiran",
            "source_name": "LinkedIn · Kiran",
            "scraped_snippet": "Senior Consultant at Vee Healthtek",
            "internal_secret_field": "do_not_leak",
        }
    )
    mock_point_2 = MagicMock(
        payload={
            "customer_id": "10455",
            "customer_name": "Kiran Kumar",
            "occupation": "SALARIED",
            "city": "Mangalore",
            "district": "Dakshina Kannada",
            "channel": "Twitter",
            "external_source": "https://twitter.com/kiran",
            "source_name": "Twitter · Kiran",
            "scraped_snippet": "Healthcare analyst",
        }
    )

    with patch.object(customer, "_query_qdrant_sync") as mock_query:
        mock_query.return_value = [
            {
                k: v for k, v in mock_point_1.payload.items()
                if k in customer.APPROVED_FIELDS
            },
            {
                k: v for k, v in mock_point_2.payload.items()
                if k in customer.APPROVED_FIELDS
            },
        ]
        result = await customer.lookup_customer_profile("10455")

    assert result.source == "customer"
    assert result.card_type == "profile"
    assert result.sensitive is True
    assert result.complete is True
    assert result.payload["found"] is True
    assert result.payload["customer_id"] == "10455"
    assert result.payload["customer_name"] == "Kiran"
    assert len(result.payload["records"]) == 2
    for record in result.payload["records"]:
        assert "internal_secret_field" not in record
        assert record["customer_id"] == "10455"
    assert len(result.sources) == 2
    assert len(result.evidence) == 2


@pytest.mark.anyio
async def test_retrieval_wrong_id_or_no_match():
    """No matching points in Qdrant returns a clear, typed no-match profile card."""
    with patch.object(customer, "_query_qdrant_sync", return_value=[]):
        result = await customer.lookup_customer_profile("999999")

    assert result.source == "customer"
    assert result.card_type == "profile"
    assert result.sensitive is True
    assert result.complete is False
    assert result.payload["found"] is False
    assert result.payload["customer_id"] == "999999"
    assert "No external profile" in result.summary


@pytest.mark.anyio
async def test_retrieval_empty_or_whitespace_id():
    """Blank or whitespace-only customer ID is rejected immediately."""
    result = await customer.lookup_customer_profile("   ")
    assert result.source == "customer"
    assert result.card_type == "profile"
    assert result.sensitive is True
    assert result.complete is False
    assert result.payload["found"] is False


@pytest.mark.anyio
async def test_retrieval_qdrant_exception_returns_typed_error():
    """Qdrant connection failure degrades into a retryable error card."""
    with patch.object(customer, "_query_qdrant_sync", side_effect=RuntimeError("Qdrant unreachable")):
        result = await customer.lookup_customer_profile("10455")

    assert result.source == "customer"
    assert result.card_type == "error"
    assert result.sensitive is True
    assert result.complete is False
    assert result.payload.get("retryable") is True


def test_qdrant_sync_query_filters_mismatched_ids():
    """Verify that _query_qdrant_sync drops points with non-matching customer_id."""
    mock_client = MagicMock()
    mock_client.scroll.return_value = (
        [
            MagicMock(payload={"customer_id": "10455", "customer_name": "Alice"}),
            MagicMock(payload={"customer_id": "99999", "customer_name": "Bob"}),
        ],
        None,
    )
    with patch.object(customer, "_get_qdrant_client", return_value=mock_client):
        records = customer._query_qdrant_sync("10455", "External_customer_details")
        assert len(records) == 1
        assert records[0]["customer_id"] == "10455"


# ==============================================================================
# 3. Privacy & Outbound Safety Tests
# ==============================================================================

def test_outbound_policy_blocks_customer_identifiers():
    """Ensure customer ID or profile references cannot be leaked to live web."""
    policy = access.build_policy(role="admin", external_sources_enabled=True)
    with pytest.raises(OutboundPolicyDenied):
        authorize_public_search(
            {"search_query": "search online for customer ID 10455"},
            policy=policy,
        )


# ==============================================================================
# 4. FastMCP & Extension Tests
# ==============================================================================

def test_workbench_fastmcp_server_contract():
    """FastMCP server exposes lookup_customer_profile classified in RUNTIME_TOOL_POLICIES."""
    assert "lookup_customer_profile" in workbench_server.RUNTIME_TOOL_POLICIES
    assert workbench_server.RUNTIME_TOOL_POLICIES["lookup_customer_profile"] == "customer"


@pytest.mark.anyio
async def test_workbench_fastmcp_tool_execution():
    with patch.object(customer, "lookup_customer_profile") as mock_lookup:
        from app.services.workbench.results import SourceResult
        mock_lookup.return_value = SourceResult(
            source="customer",
            card_type="profile",
            payload={"customer_id": "10455", "found": True},
            summary="Found",
            sensitive=True,
        )
        res = await workbench_server.lookup_customer_profile("10455")
        assert res["source"] == "customer"
        assert res["kind"] == "profile"
        assert res["sensitive"] is True
