"""End-to-end: HTTP request -> chart JSON, against the real warehouse.

`/nlq/execute` is exercised for real because it has no LLM dependency — it is the endpoint
that must keep working when the assistant is offline, so it is the one worth testing without
mocks. `/nlq/ask` is driven with a stub planner so the routing and SSE framing are tested
without spending tokens or depending on a model being up.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.nlq import cache, ratelimit
from app.services.nlq.contracts import QuerySpecPlan
from tests.nlq.conftest import requires_db


@pytest.fixture
def client():
    ratelimit.reset()
    cache.clear_all()
    return TestClient(app)


class TestHealth:
    def test_health_is_always_200(self, client):
        """A degraded LLM is a product state, not an error — the ask bar renders its
        offline message from this, and a 503 would give it nothing to render."""
        response = client.get("/nlq/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ("ok", "degraded")
        assert set(body["capabilities"]) == {"execute", "ask", "text_to_sql"}

    def test_catalog_exposes_labels_not_column_names(self, client):
        """Column names are meaningless to a user and leak schema."""
        body = client.get("/nlq/catalog").json()
        assert body["metrics"] and body["dimensions"] and body["example_questions"]
        serialised = json.dumps(body)
        for internal in ("gnlnac_", "ascd_", "lnrepay_"):
            assert internal not in serialised

    def test_catalog_marks_unratified_metrics(self, client):
        metrics = {m["id"]: m for m in client.get("/nlq/catalog").json()["metrics"]}
        assert metrics["par_30"]["requires_signoff"] is True


@requires_db
class TestExecuteEndpoint:
    """The LLM-free path: saved questions, drill-downs and dashboards all run through it."""

    def test_returns_a_rendered_chart(self, client, readonly_via_warehouse):
        response = client.post(
            "/nlq/execute",
            json={
                "query_spec": {
                    "metrics": ["loan_count"],
                    "dimensions": ["product"],
                    "period": {"relative": "all_time"},
                }
            },
        )
        assert response.status_code == 200
        chart = response.json()
        assert chart["chart_type"] == "bar"
        assert len(chart["rows"]) == 3
        assert {r["product"] for r in chart["rows"]} == {
            "Gold Loans",
            "Microfinance / Retail EMI",
            "Business & MSME Loans",
        }
        assert chart["lineage"]["sql"]
        assert chart["summary"]

    def test_par_30_carries_its_lineage_and_badge(self, client, readonly_via_warehouse):
        response = client.post(
            "/nlq/execute",
            json={
                "query_spec": {
                    "metrics": ["par_30"],
                    "period": {"start": "2026-01-01", "end": "2026-07-01"},
                }
            },
        )
        chart = response.json()
        assert chart["chart_type"] == "kpi"
        assert round(chart["rows"][0]["par_30"], 3) == 0.090
        assert "par_30" in chart["lineage"]["requires_signoff"]
        assert "DISTINCT ON" in chart["lineage"]["sql"]
        assert chart["lineage"]["formulas"]["par_30"]

    def test_a_refused_spec_returns_422_with_a_readable_reason(self, client):
        """The message is written for the user, not copied from a database error."""
        response = client.post(
            "/nlq/execute",
            json={
                "query_spec": {
                    "metrics": ["gl_balance"],
                    "dimensions": ["product"],
                    "period": {"relative": "this_fy"},
                }
            },
        )
        assert response.status_code == 422
        assert "no declared join" in response.json()["detail"]

    def test_a_malformed_spec_is_422(self, client):
        response = client.post("/nlq/execute", json={"query_spec": {"metrics": []}})
        assert response.status_code == 422

    def test_repeat_requests_hit_the_result_cache(self, client, readonly_via_warehouse):
        payload = {
            "query_spec": {"metrics": ["loan_count"], "period": {"relative": "all_time"}}
        }
        first = client.post("/nlq/execute", json=payload).json()
        second = client.post("/nlq/execute", json=payload).json()
        assert first["rows"] == second["rows"]
        assert second["lineage"]["duration_ms"] <= first["lineage"]["duration_ms"]


class TestAskEndpoint:
    """SSE framing and routing, with the planner stubbed."""

    def _stub_planner(self, monkeypatch, plan):
        from app.services.nlq import planner as planner_module
        from app.services.nlq.planner import PlanOutcome

        async def fake_plan(question, **kwargs):
            return PlanOutcome(
                plan=plan,
                attempts=1,
                prompt_version="test",
                model="stub",
                provider="stub",
                duration_ms=1,
            )

        monkeypatch.setattr(planner_module, "plan", fake_plan)
        from app.services.nlq import ask as ask_module

        monkeypatch.setattr(ask_module.planner, "plan", fake_plan)

    def _events(self, response) -> list[tuple[str, dict]]:
        out = []
        for frame in response.text.split("\n\n"):
            name = body = ""
            for line in frame.split("\n"):
                if line.startswith("event: "):
                    name = line[7:].strip()
                elif line.startswith("data: "):
                    body += line[6:]
            if name:
                out.append((name, json.loads(body) if body else {}))
        return out

    def test_refusal_streams_a_refusal_event_with_alternatives(self, client, monkeypatch):
        from app.services.nlq.contracts import RefusalPlan

        self._stub_planner(
            monkeypatch, RefusalPlan(reason="predictive", message="I do not forecast.")
        )
        response = client.post("/nlq/ask", json={"question": "Will defaults rise?"})
        assert response.status_code == 200

        events = dict(self._events(response))
        assert "refusal" in events
        assert events["refusal"]["reason"] == "predictive"
        # A refusal must always offer a way forward.
        assert len(events["refusal"]["examples"]) == 3
        assert "done" in events

    def test_clarification_streams_tappable_suggestions(self, client, monkeypatch):
        from app.services.nlq.contracts import ClarifyPlan

        self._stub_planner(
            monkeypatch,
            ClarifyPlan(question="Which measure?", suggestions=["Disbursement", "PAR 30"]),
        )
        response = client.post("/nlq/ask", json={"question": "How did we do?"})
        events = dict(self._events(response))
        assert events["clarify"]["question"] == "Which measure?"
        assert len(events["clarify"]["suggestions"]) == 2

    def test_stage_events_are_emitted_in_order(self, client, monkeypatch):
        from app.services.nlq.contracts import RefusalPlan

        self._stub_planner(monkeypatch, RefusalPlan(reason="out_of_scope"))
        response = client.post("/nlq/ask", json={"question": "What is the repo rate?"})
        stages = [d["stage"] for name, d in self._events(response) if name == "stage"]
        assert stages[:2] == ["understanding", "planning"]

    @requires_db
    def test_a_queryspec_plan_streams_a_chart(
        self, client, monkeypatch, readonly_via_warehouse
    ):
        from app.services.nlq.contracts import Period, QuerySpec

        self._stub_planner(
            monkeypatch,
            QuerySpecPlan(
                spec=QuerySpec(metrics=["loan_count"], period=Period(relative="all_time")),
                confidence=0.9,
            ),
        )
        response = client.post("/nlq/ask", json={"question": "How many loans?"})
        events = dict(self._events(response))
        assert "chart" in events
        assert events["chart"]["status"] == "answered"
        assert events["chart"]["chart"]["rows"][0]["loan_count"] == 13510

    def test_rate_limit_returns_429_with_retry_after(self, client, monkeypatch):
        monkeypatch.setattr(ratelimit, "QUESTIONS_PER_MINUTE", 2)
        from app.services.nlq.contracts import RefusalPlan

        self._stub_planner(monkeypatch, RefusalPlan(reason="out_of_scope"))
        for _ in range(ratelimit.QUESTIONS_PER_MINUTE):
            client.post("/nlq/ask", json={"question": "hello"})
        limited = client.post("/nlq/ask", json={"question": "hello"})
        assert limited.status_code == 429
        assert "Retry-After" in limited.headers


class TestConversationEndpoints:
    def test_conversation_round_trip(self, client):
        body = client.get("/nlq/conversations/does-not-exist").json()
        assert body["turns"] == []
        assert body["sticky_filters"] == []

    def test_clearing_a_conversation_is_204(self, client):
        assert client.delete("/nlq/conversations/whatever").status_code == 204

    def test_feedback_on_an_unknown_turn_is_404(self, client):
        response = client.post(
            "/nlq/feedback", json={"turn_id": "nope", "verdict": "down"}
        )
        assert response.status_code == 404

    def test_feedback_rejects_an_invalid_verdict(self, client):
        response = client.post(
            "/nlq/feedback", json={"turn_id": "x", "verdict": "maybe"}
        )
        assert response.status_code == 422

    def test_suggestions_are_available_without_a_conversation(self, client):
        body = client.get("/nlq/suggestions").json()
        assert len(body["suggestions"]) >= 1
