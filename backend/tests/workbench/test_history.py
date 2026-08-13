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


def test_complete_cards_are_saved_and_become_assistant_context():
    turn_id = history.begin_turn("c1", "alice", "What is PAR 30?")
    history.set_route("c1", "alice", turn_id, sources=["db"], intent="What is PAR 30?")
    history.add_card("c1", "alice", turn_id, {
        "source": "db",
        "card_type": "chart",
        "payload": {
            "title": "PAR 30",
            "chart_type": "kpi",
            "columns": [{"name": "par_30", "label": "PAR 30"}],
            "rows": [{"par_30": 4.2}],
            "summary": "PAR 30 is 4.2%.",
            "lineage": {"sql": "must not enter model context"},
        },
    })
    history.complete_turn("c1", "alice", turn_id)

    rec = history.get("c1", user="alice")
    assert rec is not None and rec.turns[0]["cards"][0]["payload"]["title"] == "PAR 30"
    messages = history.transcript("c1", user="alice")
    assert messages[-2] == {"role": "user", "content": "What is PAR 30?"}
    assert "PAR 30 is 4.2%" in messages[-1]["content"]
    assert "Chart context: type=kpi; fields=par_30" in messages[-1]["content"]
    assert "must not enter model context" not in messages[-1]["content"]


def test_conversations_and_context_are_isolated_by_user():
    history.record_turn("alice-chat", "Alice question", ["db"], user="alice")
    history.record_turn("bob-chat", "Bob question", ["db"], user="bob")

    assert history.get("bob-chat", user="alice") is None
    assert [item.conversation_id for item in history.list_recent(user="alice")] == ["alice-chat"]
    assert history.transcript("bob-chat", user="alice") == []


def test_new_conversation_starts_with_empty_context():
    history.record_turn("old", "Old question", ["db"], user="alice")
    assert history.transcript("new", user="alice") == []


def test_transcript_respects_the_character_budget():
    for index in range(12):
        turn_id = history.begin_turn("long", "alice", f"Question {index} " + "q" * 100)
        history.add_card("long", "alice", turn_id, {
            "source": "macro", "card_type": "brief",
            "payload": {"summary": f"Answer {index} " + "a" * 600},
        })
        history.complete_turn("long", "alice", turn_id)

    messages = history.transcript("long", user="alice", char_budget=4_000)
    assert sum(len(message["content"]) for message in messages) <= 4_200
    assert "Question 11" in messages[-2]["content"]
