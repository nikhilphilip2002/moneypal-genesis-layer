"""The workbench HTTP surface: the tool endpoints. The access rule is asserted at the edge,
because that is where it is actually exposed — listing filters by role, and running enforces
it (403), so a hidden tool cannot be invoked by calling the endpoint directly.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _auth(username: str) -> dict:
    return {"Authorization": f"Bearer mock-token-{username}"}


class TestListTools:
    def test_admin_sees_all_tools(self, client):
        r = client.get("/workbench/tools", headers=_auth("moneypal_admin"))
        assert r.status_code == 200
        ids = {t["id"] for t in r.json()["tools"]}
        assert {"show_schema", "competitor_landscape"} <= ids

    def test_policy_maker_does_not_see_the_schema_tool(self, client):
        r = client.get("/workbench/tools", headers=_auth("gicc_policy"))
        ids = {t["id"] for t in r.json()["tools"]}
        assert "competitor_landscape" in ids
        assert "show_schema" not in ids


class TestRunTool:
    def test_unknown_tool_is_404(self, client):
        r = client.post("/workbench/tool/nope", headers=_auth("moneypal_admin"), json={})
        assert r.status_code == 404

    def test_unauthorized_tool_is_403(self, client):
        r = client.post("/workbench/tool/show_schema", headers=_auth("gicc_policy"), json={})
        assert r.status_code == 403

    def test_authorized_run_returns_a_card(self, client, monkeypatch):
        from app.services.workbench import nodes

        async def fake_schema(intent):
            return nodes.SourceResult(source="schema", card_type="schema",
                                      payload={"node_count": 3, "edge_count": 2, "nodes": [], "edges": []})

        monkeypatch.setattr(nodes, "run_schema", fake_schema)
        r = client.post("/workbench/tool/show_schema", headers=_auth("moneypal_admin"), json={})
        assert r.status_code == 200
        body = r.json()
        assert body["card_type"] == "schema"
        assert body["source"] == "schema"


class TestConversationOwnership:
    @pytest.fixture(autouse=True)
    def _memory_history(self, monkeypatch):
        from app.services.workbench import history

        monkeypatch.setattr(history, "_ensure_table", lambda: False)
        history._MEMORY.clear()
        yield
        history._MEMORY.clear()

    def test_conversation_is_visible_only_to_its_owner(self, client):
        from app.services.workbench import history

        history.record_turn("private", "Policy question", ["macro"], user="gicc_policy")

        owner = client.get(
            "/workbench/conversations/private", headers=_auth("gicc_policy"),
        )
        other = client.get(
            "/workbench/conversations/private", headers=_auth("gicc_director"),
        )

        assert owner.status_code == 200
        assert other.status_code == 404
        assert client.get(
            "/workbench/conversations", headers=_auth("gicc_director"),
        ).json()["conversations"] == []

    def test_saved_cards_are_returned_for_ui_hydration(self, client):
        from app.services.workbench import history

        turn_id = history.begin_turn("cards", "gicc_policy", "Macro outlook")
        history.add_card("cards", "gicc_policy", turn_id, {
            "source": "macro", "card_type": "brief",
            "payload": {"summary": "Growth is stable."},
        })
        history.complete_turn("cards", "gicc_policy", turn_id)

        body = client.get(
            "/workbench/conversations/cards", headers=_auth("gicc_policy"),
        ).json()

        assert body["record_version"] == 2
        assert body["turns"][0]["cards"][0]["payload"]["summary"] == "Growth is stable."
