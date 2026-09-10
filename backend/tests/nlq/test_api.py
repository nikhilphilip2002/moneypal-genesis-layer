"""End-to-end: HTTP request -> chart JSON, against the real warehouse.

`/nlq/execute` is exercised for real because it has no LLM dependency and must keep
working when the assistant is offline.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.nlq import cache, ratelimit
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
        assert set(body["capabilities"]) == {"execute", "text_to_sql"}

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
        assert chart["rows"]
        assert all(row["product"] for row in chart["rows"])
        assert sum(row["loan_count"] for row in chart["rows"]) > 0
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
        assert "gold.portfolio_snapshot_as_of" in chart["lineage"]["sql"]
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


class TestRemovedAskEndpoint:
    def test_legacy_ask_route_is_absent(self, client):
        assert client.post("/nlq/ask", json={"question": "hello"}).status_code == 404
