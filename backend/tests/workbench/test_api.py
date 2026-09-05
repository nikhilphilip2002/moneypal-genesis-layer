"""The workbench HTTP surface: the tool endpoints. The access rule is asserted at the edge,
because that is where it is actually exposed — listing filters by role, and running enforces
it (403), so a hidden tool cannot be invoked by calling the endpoint directly.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


def _auth(username: str) -> dict:
    return {"Authorization": f"Bearer mock-token-{username}"}


class TestListTools:
    @pytest.mark.anyio
    async def test_admin_sees_all_tools(self, client):
        r = await client.get("/workbench/tools", headers=_auth("moneypal_admin"))
        assert r.status_code == 200
        ids = {t["id"] for t in r.json()["tools"]}
        assert {"show_schema", "competitor_landscape"} <= ids

    @pytest.mark.anyio
    async def test_policy_maker_does_not_see_the_schema_tool(self, client):
        r = await client.get("/workbench/tools", headers=_auth("gicc_policy"))
        ids = {t["id"] for t in r.json()["tools"]}
        assert "competitor_landscape" in ids
        assert "show_schema" not in ids


class TestCompletions:
    @pytest.fixture(autouse=True)
    def _reset_completion_cooldown(self, monkeypatch):
        from app.api.routes import workbench as route

        monkeypatch.setattr(route, "_completion_db_retry_after", 0.0)
        monkeypatch.setattr(route, "_completion_in_flight", False)

    @pytest.mark.anyio
    async def test_returns_governed_chat_completions(self, client, monkeypatch):
        from app.api.routes import workbench as route

        monkeypatch.setattr(route.record_lookup, "completions", lambda q, kind: [{
            "kind": "agent", "value": "AGNT45", "label": "Agent Name",
            "detail": "AGNT45 · Officer",
        }])

        response = await client.get(
            "/workbench/completions?q=AGNT4&kind=agent",
            headers=_auth("gicc_policy"),
        )

        assert response.status_code == 200
        assert response.json()["results"][0]["value"] == "AGNT45"

    @pytest.mark.anyio
    async def test_database_failure_starts_cooldown_instead_of_retrying_per_request(
        self, client, monkeypatch
    ):
        from app.api.routes import workbench as route

        calls = 0

        def unavailable(_q, _kind):
            nonlocal calls
            calls += 1
            raise RuntimeError("database down")

        monkeypatch.setattr(route.record_lookup, "completions", unavailable)

        first = await client.get(
            "/workbench/completions?q=Sheelavati&kind=borrower",
            headers=_auth("gicc_policy"),
        )
        second = await client.get(
            "/workbench/completions?q=Sheelav&kind=borrower",
            headers=_auth("gicc_policy"),
        )

        assert first.status_code == second.status_code == 200
        assert first.json()["results"] == second.json()["results"] == []
        assert calls == 1

    @pytest.mark.anyio
    async def test_question_prose_does_not_trigger_a_borrower_directory_query(
        self, client, monkeypatch
    ):
        from app.api.routes import workbench as route

        def must_not_query(_q, _kind):
            raise AssertionError("question prose reached entity completion SQL")

        monkeypatch.setattr(route.record_lookup, "completions", must_not_query)

        response = await client.get(
            "/workbench/completions?q=total%20lona&kind=all",
            headers=_auth("gicc_policy"),
        )

        assert response.status_code == 200
        assert response.json()["results"] == []


class TestRunTool:
    @pytest.mark.anyio
    async def test_unknown_tool_is_404(self, client):
        r = await client.post("/workbench/tool/nope", headers=_auth("moneypal_admin"), json={})
        assert r.status_code == 404

    @pytest.mark.anyio
    async def test_unauthorized_tool_is_403(self, client):
        r = await client.post("/workbench/tool/show_schema", headers=_auth("gicc_policy"), json={})
        assert r.status_code == 403

    @pytest.mark.anyio
    async def test_authorized_run_returns_a_card(self, client, monkeypatch):
        from app.services.workbench import nodes

        async def fake_schema(intent):
            return nodes.SourceResult(source="schema", card_type="schema",
                                      payload={"node_count": 3, "edge_count": 2, "nodes": [], "edges": []})

        monkeypatch.setattr(nodes, "run_schema", fake_schema)
        r = await client.post("/workbench/tool/show_schema", headers=_auth("moneypal_admin"), json={})
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

    @pytest.mark.anyio
    async def test_conversation_is_visible_only_to_its_owner(self, client):
        from app.services.workbench import history

        history.record_turn("private", "Policy question", ["macro"], user="gicc_policy")

        owner = await client.get(
            "/workbench/conversations/private", headers=_auth("gicc_policy"),
        )
        other = await client.get(
            "/workbench/conversations/private", headers=_auth("gicc_director"),
        )

        assert owner.status_code == 200
        assert other.status_code == 404
        assert (await client.get(
            "/workbench/conversations", headers=_auth("gicc_director"),
        )).json()["conversations"] == []

    @pytest.mark.anyio
    async def test_saved_cards_are_returned_for_ui_hydration(self, client):
        from app.services.workbench import history

        turn_id = history.begin_turn("cards", "gicc_policy", "Macro outlook")
        history.add_card("cards", "gicc_policy", turn_id, {
            "source": "macro", "card_type": "brief",
            "payload": {"summary": "Growth is stable."},
        })
        history.complete_turn("cards", "gicc_policy", turn_id)

        body = (await client.get(
            "/workbench/conversations/cards", headers=_auth("gicc_policy"),
        )).json()

        assert body["record_version"] == history.RECORD_VERSION
        assert body["turns"][0]["cards"][0]["payload"]["summary"] == "Growth is stable."
