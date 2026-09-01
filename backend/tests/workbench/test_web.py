"""Live-web governance: sanitization, source authority, normalization and node contract."""

from __future__ import annotations

import pytest

from app.mcp.exa_client import ExaToolResult
from app.services.workbench import models, nodes, web
from tests.workbench.conftest import FakeLLM


class TestPrivacy:
    @pytest.mark.parametrize(
        "question",
        [
            "search online for customer ID 42",
            "find repayment history for borrower Anitha Rao on the web",
            "find borrower anitha rao on the web",
            "check internet sources for phone number 9988776655",
        ],
    )
    def test_private_identifiers_never_become_web_queries(self, question):
        with pytest.raises(web.UnsafeWebQuery):
            web.public_query(question)

    def test_hybrid_question_keeps_only_the_public_half(self):
        assert web.public_query(
            "Compare our loan growth against the latest RBI bank credit growth"
        ) == "the latest RBI bank credit growth"


class TestAuthority:
    def test_repo_query_prefers_rbi_domains(self):
        domains = web.domains_for("latest RBI repo rate", tier=1)
        assert "rbi.org.in" in domains
        assert "mospi.gov.in" not in domains

    def test_structured_results_are_normalized_ranked_and_deduplicated(self):
        result = ExaToolResult(
            structured={"results": [
                {"title": "Commentary", "url": "https://example.com/a?utm_source=x"},
                {"title": "RBI release", "url": "https://www.rbi.org.in/release?id=1"},
                {"title": "Duplicate", "url": "https://www.rbi.org.in/release?id=1"},
            ]},
            text="results",
        )

        evidence = web.normalize(result)

        assert [item.title for item in evidence] == ["RBI release", "Commentary"]
        assert evidence[0].source_tier == 1
        assert evidence[0].primary is True
        assert "utm_source" not in evidence[1].url


class TestNode:
    @pytest.mark.anyio
    async def test_web_node_returns_citable_brief(self, monkeypatch):
        item = web.WebEvidence(
            title="RBI release", url="https://rbi.org.in/release", publisher="RBI",
            domain="rbi.org.in", excerpt="The policy rate was announced.",
            published_at="2026-08-01", retrieved_at="2026-09-01T00:00:00+00:00",
            source_tier=1, primary=True,
        )

        async def fake_retrieve(*args, **kwargs):
            return "latest repo rate", [item], "[RBI release](https://rbi.org.in/release)"

        monkeypatch.setattr(web, "retrieve", fake_retrieve)
        monkeypatch.setattr(models, "for_step", lambda *a, **k: FakeLLM("Grounded answer."))

        result = await nodes.run_web("latest repo rate", user="alice")

        assert result.source == "web"
        assert result.card_type == "brief"
        assert result.sources[0]["url"] == "https://rbi.org.in/release"
        assert result.sources[0]["primary"] is True
