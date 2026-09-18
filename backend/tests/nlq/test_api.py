"""End-to-end: HTTP request -> chart JSON, against the real warehouse.

`/nlq/execute` is exercised for real because it has no LLM dependency and must keep
working when the assistant is offline.
"""

import json

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.nlq import cache, ratelimit
from tests.nlq.conftest import requires_db

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    ratelimit.reset()
    cache.clear_all()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as test_client:
        yield test_client


class TestHealth:
    async def test_health_is_always_200(self, client, monkeypatch):
        """A degraded LLM is a product state, not an error — the ask bar renders its
        offline message from this, and a 503 would give it nothing to render."""
        from app.api.routes import nlq as nlq_route

        class OfflineLLM:
            async def health(self):
                return {"status": "down", "detail": "offline test"}

        monkeypatch.setattr(nlq_route, "get_llm_client", lambda: OfflineLLM())
        monkeypatch.setattr(
            nlq_route.nlq_db,
            "health",
            lambda: {"status": "unconfigured", "detail": "offline test"},
        )
        response = await client.get("/nlq/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ("ok", "degraded")
        assert set(body["capabilities"]) == {"execute"}

    async def test_catalog_exposes_labels_not_column_names(self):
        """Column names are meaningless to a user and leak schema."""
        from app.api.routes import nlq as nlq_route

        body = nlq_route.catalog_summary()
        assert body["metrics"] and body["dimensions"] and body["example_questions"]
        serialised = json.dumps(body)
        for internal in ("gnlnac_", "ascd_", "lnrepay_"):
            assert internal not in serialised

    async def test_catalog_marks_unratified_metrics(self):
        from app.api.routes import nlq as nlq_route

        metrics = {m["id"]: m for m in nlq_route.catalog_summary()["metrics"]}
        assert metrics["par_30"]["requires_signoff"] is True


@requires_db
class TestExecuteEndpoint:
    """The LLM-free path: saved questions, drill-downs and dashboards all run through it."""

    async def test_returns_a_rendered_chart(self, client, readonly_via_warehouse):
        response = await client.post(
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

    async def test_par_30_carries_its_lineage_and_badge(self, client, readonly_via_warehouse):
        response = await client.post(
            "/nlq/execute",
            json={
                "query_spec": {
                    "metrics": ["par_30"],
                    "period": {"start": "2026-01-01", "end": "2026-08-30"},
                }
            },
        )
        chart = response.json()
        assert chart["chart_type"] == "kpi"
        assert round(chart["rows"][0]["par_30"], 3) == 0.426
        assert "par_30" in chart["lineage"]["requires_signoff"]
        assert "gold.daily_loan_status" in chart["lineage"]["sql"]
        assert "DISTINCT ON" in chart["lineage"]["sql"]
        assert chart["lineage"]["formulas"]["par_30"]

    async def test_a_refused_spec_returns_422_with_a_readable_reason(self, client):
        """The message is written for the user, not copied from a database error."""
        response = await client.post(
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

    async def test_a_malformed_spec_is_422(self, client):
        response = await client.post(
            "/nlq/execute", json={"query_spec": {"metrics": []}},
        )
        assert response.status_code == 422

    async def test_repeat_requests_hit_the_result_cache(self, client, readonly_via_warehouse):
        payload = {
            "query_spec": {"metrics": ["loan_count"], "period": {"relative": "all_time"}}
        }
        first = (await client.post("/nlq/execute", json=payload)).json()
        second = (await client.post("/nlq/execute", json=payload)).json()
        assert first["rows"] == second["rows"]
        assert second["lineage"]["duration_ms"] <= first["lineage"]["duration_ms"]


class TestRemovedAskEndpoint:
    async def test_legacy_ask_route_is_absent(self, client):
        response = await client.post("/nlq/ask", json={"question": "hello"})
        assert response.status_code == 404


class TestRouteIdentity:
    async def test_known_demo_token_resolves_for_owned_resources(self):
        from app.api.routes.auth import identity_from_authorization

        assert identity_from_authorization("Bearer mock-token-moneypal_admin") == (
            "moneypal_admin", "admin",
        )

    async def test_missing_token_is_anonymous(self):
        from app.api.routes.auth import identity_from_authorization

        assert identity_from_authorization(None) == ("anonymous", "anonymous")

    async def test_auth_me_uses_the_shared_identity_parser(self):
        from app.api.routes.auth import me

        assert me("Bearer mock-token-moneypal_admin")["role"] == "admin"

    async def test_auth_me_still_rejects_an_invalid_token(self):
        from app.api.routes.auth import me

        with pytest.raises(HTTPException) as exc_info:
            me("Bearer not-a-demo-token")

        assert exc_info.value.status_code == 401
