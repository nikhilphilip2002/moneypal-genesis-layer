"""Source metadata and role/deployment visibility."""

from __future__ import annotations

import pytest

from app.services.workbench import sources
from app.core.config import settings


ALL_IDS = {"db", "macro", "competitive", "regulatory", "knowledge", "web"}


@pytest.fixture(autouse=True)
def _connector_settings(monkeypatch):
    monkeypatch.setattr(
        settings, "workbench_external_connectors_enabled", True
    )
    monkeypatch.setattr(settings, "exa_mcp_enabled", True)


def test_all_phase2_sources_are_registered():
    assert set(sources.SOURCES) == ALL_IDS


def test_admin_sees_every_source():
    visible = {s.id for s in sources.visible_sources("admin")}
    assert visible == ALL_IDS


def test_director_sees_loan_book_sources_but_not_market_or_regulatory():
    # The director's workspace is the portfolio and public macro, not competitive or
    # regulatory, which they have no module access to.
    visible = {s.id for s in sources.visible_sources("gicc_director")}
    assert visible == {"db", "macro", "knowledge", "web"}


def test_policy_maker_sees_loan_book_during_open_access_rollout():
    visible = {s.id for s in sources.visible_sources("gicc_policy")}
    assert visible == {
        "db",
        "macro",
        "competitive",
        "regulatory",
        "knowledge",
        "web",
    }


def test_loan_book_is_sensitive_public_intelligence_is_not():
    assert sources.SOURCES["db"].sensitive is True
    for public in ("macro", "competitive", "regulatory", "knowledge", "web"):
        assert sources.SOURCES[public].sensitive is False


def test_web_source_disappears_when_feature_flag_is_off(monkeypatch):
    monkeypatch.setattr(settings, "exa_mcp_enabled", False)

    assert "web" not in {
        source.id for source in sources.visible_sources("admin")
    }
