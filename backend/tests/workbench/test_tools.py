"""The tool registry is the "+" menu's backend: the extensible surface for actions that are
not a typed question. It is tested as data (what exists, who may run each) plus one hard
rule — running a tool enforces the same role access as seeing it, so the menu can never be
bypassed by calling the endpoint directly.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.workbench import tools


def test_the_phase3_tools_are_registered():
    assert {"show_schema", "competitor_landscape"} <= set(tools.TOOLS)


def test_visible_tools_respect_role():
    director = {t.id for t in tools.visible_tools("gicc_director")}
    policy = {t.id for t in tools.visible_tools("gicc_policy")}
    # The director owns the portfolio (schema) but not the competitor set; policy the reverse.
    assert "show_schema" in director and "competitor_landscape" not in director
    assert "competitor_landscape" in policy and "show_schema" not in policy


def test_get_tool_returns_none_for_an_unknown_id():
    assert tools.get_tool("nope") is None


class TestRunTool:
    @pytest.mark.anyio
    async def test_dispatches_to_the_handler(self, monkeypatch):
        from app.services.workbench import nodes

        async def fake_schema(intent):
            return nodes.SourceResult(source="schema", card_type="schema", payload={"node_count": 2})

        monkeypatch.setattr(nodes, "run_schema", fake_schema)
        result = await tools.run_tool("show_schema", role="admin", params={})
        assert result.card_type == "schema"

    @pytest.mark.anyio
    async def test_running_a_tool_the_role_cannot_see_is_refused(self, monkeypatch):
        # gicc_policy has no access to schema; calling the endpoint directly must not work.
        with pytest.raises(tools.ToolAccessError):
            await tools.run_tool("show_schema", role="gicc_policy", params={})

    @pytest.mark.anyio
    async def test_running_an_unknown_tool_raises(self):
        with pytest.raises(tools.ToolNotFound):
            await tools.run_tool("nope", role="admin", params={})

    @pytest.mark.anyio
    async def test_competitor_landscape_returns_a_brief(self, monkeypatch):
        from app.services.workbench import nodes

        async def fake_competitive(intent):
            return nodes.SourceResult(
                source="competitive", card_type="brief",
                payload={"summary": "Rivals.", "key_points": []},
                summary="Rivals.",
            )

        monkeypatch.setattr(nodes, "run_competitive", fake_competitive)
        result = await tools.run_tool("competitor_landscape", role="gicc_admin", params={})
        assert result.card_type == "brief"
        assert "Rivals." in result.payload["summary"]
