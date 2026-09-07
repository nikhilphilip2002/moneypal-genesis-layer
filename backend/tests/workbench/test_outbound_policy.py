from __future__ import annotations

import pytest

from app.services.workbench import access, outbound_policy, web


@pytest.fixture(autouse=True)
def _connectors(monkeypatch):
    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)


def _policy(enabled=True):
    return access.build_policy(role="admin", external_sources_enabled=enabled)


@pytest.mark.parametrize(
    "query",
    [
        "latest RBI rule for PAN ABCDE1234F",
        "search Aadhaar 1234 5678 9012",
        "look up mobile +91 99887-76655",
        "repayment details for borrower",
        "customer＿id 42 latest news",
        "loan—number 1000400000075 RBI news",
        "customer\u200did 42 RBI news",
    ],
)
def test_private_variants_are_rejected(query):
    with pytest.raises(outbound_policy.OutboundPolicyDenied):
        outbound_policy.authorize_public_search(
            {"search_query": query}, policy=_policy(),
        )


def test_nested_arguments_are_scanned():
    with pytest.raises(outbound_policy.OutboundPolicyDenied):
        outbound_policy.authorize_public_search(
            {"search_query": "RBI news", "context": {"phone": "9988776655"}},
            policy=_policy(),
        )


def test_session_private_entities_are_rejected():
    with pytest.raises(outbound_policy.OutboundPolicyDenied):
        outbound_policy.authorize_public_search(
            {"search_query": "news about Asha Rao"},
            policy=_policy(),
            private_entities=["Asha Rao"],
        )


def test_consent_is_checked_before_search():
    with pytest.raises(access.SourceAccessDenied):
        outbound_policy.authorize_public_search(
            {"search_query": "latest RBI repo rate"}, policy=_policy(False),
        )


def test_public_comparison_keeps_only_external_half():
    decision = outbound_policy.authorize_public_search(
        {"search_query": "Compare our portfolio against RBI bank credit growth"},
        policy=_policy(),
    )
    assert decision.query == "RBI bank credit growth"


@pytest.mark.anyio
async def test_denial_performs_no_retrieval(monkeypatch):
    called = False

    async def fake_retrieve(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(web, "retrieve", fake_retrieve)
    with pytest.raises(outbound_policy.OutboundPolicyDenied):
        await outbound_policy.retrieve_public(
            "customer ID 42", user="alice", policy=_policy(),
        )
    assert called is False
