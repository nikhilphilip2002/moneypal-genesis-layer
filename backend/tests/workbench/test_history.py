"""Durable conversation history. In the test environment no database is configured, so these
exercise the in-memory fallback — the same code path a dev box runs — and pin the semantics:
the title comes from the first question, turns accumulate, and recency ordering is correct.
"""

from __future__ import annotations

import pytest

from app.services.workbench import history


@pytest.fixture(autouse=True)
def _memory_only(monkeypatch):
    # Force the in-memory path so these are deterministic and independent of whatever
    # database happens to be reachable. The Postgres path mirrors the same semantics and is
    # covered by integration, not this unit suite.
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    history._MEMORY.clear()
    yield
    history._MEMORY.clear()


def test_first_turn_titles_the_conversation_from_the_question():
    history.record_turn("c1", "What was our disbursement last quarter?", ["db"])
    rec = history.get("c1")
    assert rec is not None
    assert rec.title.startswith("What was our disbursement")
    assert len(rec.turns) == 1
    assert rec.turns[0]["sources"] == ["db"]


def test_later_turns_accumulate_and_keep_the_title():
    history.record_turn("c1", "First question about the book", ["db"])
    history.record_turn("c1", "and by branch?", ["db"])
    rec = history.get("c1")
    assert rec.title.startswith("First question")
    assert len(rec.turns) == 2


def test_list_recent_orders_by_most_recently_updated():
    history.record_turn("a", "alpha", ["db"])
    history.record_turn("b", "bravo", ["macro"])
    history.record_turn("a", "alpha follow-up", ["db"])  # touches 'a' last
    recent = history.list_recent()
    assert [c.conversation_id for c in recent] == ["a", "b"]
    assert recent[0].turn_count == 2


def test_list_recent_respects_the_limit():
    for i in range(5):
        history.record_turn(f"c{i}", f"q{i}", ["db"])
    assert len(history.list_recent(limit=3)) == 3


def test_get_unknown_conversation_is_none():
    assert history.get("nope") is None
