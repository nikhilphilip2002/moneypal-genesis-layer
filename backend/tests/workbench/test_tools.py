"""The tool registry is the "+" menu's backend: the extensible surface for actions that are
not a typed question. It is tested as data (what exists, who may run each) plus one hard
rule — running a tool enforces the same role access as seeing it, so the menu can never be
bypassed by calling the endpoint directly.
"""

from __future__ import annotations

import pytest

from app.services.workbench import tools


def test_the_phase3_tools_are_registered():
    assert set(tools.TOOLS) == {
        "competitor_landscape",
        "macro_brief",
        "regulatory_alerts",
    }


def test_visible_tools_respect_role():
    director = {t.id for t in tools.visible_tools("gicc_director")}
    policy = {t.id for t in tools.visible_tools("gicc_policy")}
    assert director == {"macro_brief"}
    assert policy == {
        "competitor_landscape",
        "macro_brief",
        "regulatory_alerts",
    }


def test_get_tool_returns_none_for_an_unknown_id():
    assert tools.get_tool("nope") is None


class TestRunTool:
    @pytest.mark.anyio
    async def test_dispatches_to_the_handler(self, monkeypatch):
        from app.services.workbench import nodes

        async def fake_macro(intent, **_kwargs):
            return nodes.SourceResult(
                source="macro",
                card_type="brief",
                payload={"summary": "Outlook."},
            )

        monkeypatch.setattr(nodes, "run_macro", fake_macro)
        result = await tools.run_tool(
            "macro_brief",
            role="admin",
            params={},
            external_sources_enabled=True,
        )
        assert result.card_type == "brief"

    @pytest.mark.anyio
    async def test_running_a_tool_the_role_cannot_see_is_refused(
        self, monkeypatch
    ):
        # A director cannot bypass the competitive source role policy.
        with pytest.raises(tools.ToolAccessError):
            await tools.run_tool(
                "competitor_landscape",
                role="gicc_director",
                params={},
                external_sources_enabled=True,
            )

    @pytest.mark.anyio
    async def test_running_an_unknown_tool_raises(self):
        with pytest.raises(tools.ToolNotFound):
            await tools.run_tool("nope", role="admin", params={})

    @pytest.mark.anyio
    async def test_competitor_landscape_returns_a_brief(self, monkeypatch):
        from app.services.workbench import nodes

        async def fake_competitive(intent, **kwargs):
            return nodes.SourceResult(
                source="competitive",
                card_type="brief",
                payload={"summary": "Rivals.", "key_points": []},
                summary="Rivals.",
            )

        monkeypatch.setattr(nodes, "run_competitive", fake_competitive)
        result = await tools.run_tool(
            "competitor_landscape",
            role="gicc_admin",
            params={},
            external_sources_enabled=True,
        )
        assert result.card_type == "brief"
        assert "Rivals." in result.payload["summary"]
