"""The source catalog is where routing coverage and access control live, so it is tested
as data: which sources exist, who may see each, and that the router schema and prompt are
derived from exactly the visible set.
"""

from __future__ import annotations

from app.services.workbench import sources


ALL_IDS = {"db", "macro", "competitive", "regulatory", "knowledge", "schema"}


def test_all_phase2_sources_are_registered():
    assert set(sources.SOURCES) == ALL_IDS


def test_admin_sees_every_source():
    visible = {s.id for s in sources.visible_sources("admin")}
    assert visible == ALL_IDS


def test_director_sees_loan_book_sources_but_not_market_or_regulatory():
    # gicc_director's workspace is the portfolio: loan book, its schema, and public macro —
    # not competitive or regulatory, which they have no module access to.
    visible = {s.id for s in sources.visible_sources("gicc_director")}
    assert visible == {"db", "macro", "knowledge", "schema"}


def test_policy_maker_sees_loan_book_during_open_access_rollout():
    visible = {s.id for s in sources.visible_sources("gicc_policy")}
    assert visible == {"db", "macro", "competitive", "regulatory", "knowledge"}


def test_loan_book_and_schema_are_sensitive_public_intelligence_is_not():
    assert sources.SOURCES["db"].sensitive is True
    assert sources.SOURCES["schema"].sensitive is True
    for public in ("macro", "competitive", "regulatory", "knowledge"):
        assert sources.SOURCES[public].sensitive is False


def test_route_schema_constrains_sources_to_the_roles_visible_set():
    schema = sources.route_schema("gicc_policy")
    enum = schema["properties"]["sources"]["items"]["enum"]
    assert set(enum) == {"db", "macro", "competitive", "regulatory", "knowledge"}


def test_router_prompt_describes_only_visible_sources():
    prompt = sources.router_system_prompt("gicc_director")
    assert "competitive" not in prompt.lower().split("rules")[0]  # not in the source list
    assert "loan book" in prompt.lower() or "lending warehouse" in prompt.lower()
