"""Node adapters are thin, so the tests pin the contract, not the underlying services: each
node returns a SourceResult of the right card_type, carries a summary for synthesis, matches
the right sub-resource, and degrades to an error card rather than raising.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.workbench import nodes
from tests.workbench.conftest import FakeLLM


def _intel(summary="A grounded summary.", key_points=None, title="Landscape"):
    return SimpleNamespace(
        summary=summary,
        key_points=key_points or ["point one", "point two"],
        title=title,
        source=SimpleNamespace(document="doc.pdf", page="3"),
    )


class TestMacro:
    @pytest.mark.anyio
    async def test_retrieval_timeout_degrades_to_an_error_card(
        self, monkeypatch
    ):
        def timeout(*args, **kwargs):
            raise TimeoutError("vector store timed out")

        async def run_inline(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        monkeypatch.setattr(nodes.rag, "search_multi", timeout)
        monkeypatch.setattr(nodes.asyncio, "to_thread", run_inline)
        result = await nodes.run_macro("current repo rate outlook")

        assert result.source == "macro"
        assert result.card_type == "error"
        assert result.payload["retryable"] is True
        assert "vector store" in result.payload["message"].lower()

    def test_missing_evidence_is_detected_and_fake_pages_are_removed(self):
        answer = (
            "The context does not contain a SIDBI benchmark (document, p.4), "
            "so a direct comparison cannot be made."
        )
        assert nodes._answer_limitation(answer)
        assert nodes._strip_unsupported_page_citations(
            answer,
            [{"document": "SIDBI", "page": None}],
        ) == (
            "The context does not contain a SIDBI benchmark (document), "
            "so a direct comparison cannot be made."
        )


class TestKnowledge:
    @pytest.mark.anyio
    async def test_returns_a_governed_catalog_brief_without_model_or_database_rows(
        self, monkeypatch
    ):
        fake = FakeLLM(
            "An interest rate is the percentage charged on principal over a stated period. "
            "Interest paid is a rupee amount, so it is different from the rate."
        )
        result = await nodes.run_knowledge("what does intrest rate mean?")

        assert result.source == "knowledge"
        assert result.card_type == "brief"
        assert "interest rate" in result.payload["summary"].lower()
        assert result.evidence
        assert fake.calls == []


class TestCompetitive:
    @pytest.mark.anyio
    async def test_returns_question_specific_retrieval_for_native_agent(
        self, monkeypatch
    ):
        from app.services import institution_loader

        monkeypatch.setattr(
            institution_loader,
            "load_all",
            lambda: [
                {
                    "id": "peer",
                    "name": "Peer Bank",
                    "type": "cooperative",
                    "qdrant_collection": "comp_peer",
                }
            ],
        )
        monkeypatch.setattr(
            nodes.rag,
            "search_multi",
            lambda *a, **k: [
                {
                    "text": "Peer Bank prices secured MSME loans competitively.",
                    "source": "peer.pdf",
                    "page": 3,
                    "score": 0.8,
                }
            ],
        )

        async def run_inline(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        monkeypatch.setattr(nodes.asyncio, "to_thread", run_inline)

        result = await nodes.run_competitive("who competes for MSME borrowers")
        assert result.source == "competitive"
        assert result.card_type == "brief"
        assert "Retrieved 1 competitive passage" in result.payload["summary"]
        assert result.evidence[0].excerpt.startswith("Peer Bank prices")
        assert (
            result.summary
        )  # non-empty, so multi-source synthesis has something to use

    @pytest.mark.anyio
    async def test_empty_registry_degrades_to_an_error_card(self, monkeypatch):
        from app.services import institution_loader

        monkeypatch.setattr(institution_loader, "load_all", lambda: [])

        async def run_inline(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        monkeypatch.setattr(nodes.asyncio, "to_thread", run_inline)
        result = await nodes.run_competitive("anything")
        assert result.card_type == "error"


class TestRegulatory:
    def _categories(self):
        return [
            SimpleNamespace(
                id="psl",
                display_name="Priority Sector Lending",
                category="psl",
                qdrant_collection="reg_psl",
                applicability="banks",
                effective_date="current",
            ),
            SimpleNamespace(
                id="dnbs",
                display_name="DNBS Returns",
                category="reporting",
                qdrant_collection="reg_dnbs",
                applicability="NBFCs",
                effective_date="current",
            ),
        ]

    @pytest.mark.anyio
    async def test_matches_the_category_the_question_is_about(
        self, monkeypatch
    ):
        from app.services import regulatory_rag
        from app.services import regulatory

        seen = {}
        monkeypatch.setattr(regulatory, "list_categories", self._categories)
        monkeypatch.setattr(regulatory_rag, "search", lambda *a, **k: [])

        async def run_inline(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        monkeypatch.setattr(nodes.asyncio, "to_thread", run_inline)

        def detail(category_id):
            seen["id"] = category_id
            return _intel(
                summary="DNBS-02 is filed quarterly.", title="DNBS Returns"
            )

        monkeypatch.setattr(regulatory, "regulation_detail", detail)
        result = await nodes.run_regulatory(
            "what are the DNBS reporting obligations"
        )

        assert seen["id"] == "dnbs"
        assert result.source == "regulatory"
        assert result.card_type == "brief"
        assert "DNBS-02" in result.payload["summary"]

    @pytest.mark.anyio
    async def test_defaults_to_the_first_category_when_nothing_matches(
        self, monkeypatch
    ):
        from app.services import regulatory_rag
        from app.services import regulatory

        seen = {}
        monkeypatch.setattr(regulatory, "list_categories", self._categories)
        monkeypatch.setattr(regulatory_rag, "search", lambda *a, **k: [])

        async def run_inline(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        monkeypatch.setattr(nodes.asyncio, "to_thread", run_inline)

        def detail(category_id):
            seen["id"] = category_id
            return _intel()

        monkeypatch.setattr(regulatory, "regulation_detail", detail)
        await nodes.run_regulatory(
            "something entirely unrelated to any category"
        )
        assert seen["id"] == "psl"  # first category
