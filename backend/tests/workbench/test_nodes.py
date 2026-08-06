"""Node adapters are thin, so the tests pin the contract, not the underlying services: each
node returns a SourceResult of the right card_type, carries a summary for synthesis, matches
the right sub-resource, and degrades to an error card rather than raising.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.workbench import nodes


def _intel(summary="A grounded summary.", key_points=None, title="Landscape"):
    return SimpleNamespace(
        summary=summary,
        key_points=key_points or ["point one", "point two"],
        title=title,
        source=SimpleNamespace(document="doc.pdf", page="3"),
    )


class TestCompetitive:
    @pytest.mark.anyio
    async def test_returns_a_brief_card_from_the_landscape(self, monkeypatch):
        from app.services import competitive

        monkeypatch.setattr(competitive, "landscape", lambda: _intel(summary="Rivals price low."))
        result = await nodes.run_competitive("who competes for MSME borrowers")

        assert result.source == "competitive"
        assert result.card_type == "brief"
        assert "Rivals price low." in result.payload["summary"]
        assert result.summary  # non-empty, so multi-source synthesis has something to use

    @pytest.mark.anyio
    async def test_service_failure_degrades_to_an_error_card(self, monkeypatch):
        from app.services import competitive

        def boom():
            raise RuntimeError("no data")

        monkeypatch.setattr(competitive, "landscape", boom)
        result = await nodes.run_competitive("anything")
        assert result.card_type == "error"


class TestRegulatory:
    def _categories(self):
        return [
            SimpleNamespace(id="psl", display_name="Priority Sector Lending", category="psl"),
            SimpleNamespace(id="dnbs", display_name="DNBS Returns", category="reporting"),
        ]

    @pytest.mark.anyio
    async def test_matches_the_category_the_question_is_about(self, monkeypatch):
        from app.services import regulatory

        seen = {}
        monkeypatch.setattr(regulatory, "list_categories", self._categories)

        def detail(category_id):
            seen["id"] = category_id
            return _intel(summary="DNBS-02 is filed quarterly.", title="DNBS Returns")

        monkeypatch.setattr(regulatory, "regulation_detail", detail)
        result = await nodes.run_regulatory("what are the DNBS reporting obligations")

        assert seen["id"] == "dnbs"
        assert result.source == "regulatory"
        assert result.card_type == "brief"
        assert "DNBS-02" in result.payload["summary"]

    @pytest.mark.anyio
    async def test_defaults_to_the_first_category_when_nothing_matches(self, monkeypatch):
        from app.services import regulatory

        seen = {}
        monkeypatch.setattr(regulatory, "list_categories", self._categories)

        def detail(category_id):
            seen["id"] = category_id
            return _intel()

        monkeypatch.setattr(regulatory, "regulation_detail", detail)
        await nodes.run_regulatory("something entirely unrelated to any category")
        assert seen["id"] == "psl"  # first category


class TestSchema:
    @pytest.mark.anyio
    async def test_returns_a_schema_card_with_entity_and_relationship_counts(self, monkeypatch):
        from app.services import db_schema

        graph = {
            "nodes": [
                {"id": "C", "name": "individual_customer_master"},
                {"id": "L", "name": "loan_account_master"},
            ],
            "edges": [{"source": "C", "target": "L", "label": "1:N"}],
        }
        monkeypatch.setattr(db_schema, "get_db_schema_graph", lambda **kw: graph)
        result = await nodes.run_schema("show the schema for accounts and customers")

        assert result.source == "schema"
        assert result.card_type == "schema"
        assert result.payload["node_count"] == 2
        assert result.payload["edge_count"] == 1
        assert len(result.payload["nodes"]) == 2

    @pytest.mark.anyio
    async def test_service_failure_degrades_to_an_error_card(self, monkeypatch):
        from app.services import db_schema

        def boom(**kw):
            raise RuntimeError("warehouse down")

        monkeypatch.setattr(db_schema, "get_db_schema_graph", boom)
        result = await nodes.run_schema("anything")
        assert result.card_type == "error"
