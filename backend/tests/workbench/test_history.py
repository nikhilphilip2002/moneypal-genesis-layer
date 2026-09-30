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
    record_turn(
        "c1", "What was our disbursement last quarter?", ["db"]
    )
    rec = history.get("c1")
    assert rec is not None
    assert rec.title.startswith("What was our disbursement")
    assert len(rec.turns) == 1
    assert rec.turns[0]["sources"] == ["db"]


def test_later_turns_accumulate_and_keep_the_title():
    record_turn("c1", "First question about the book", ["db"])
    record_turn("c1", "and by branch?", ["db"])
    rec = history.get("c1")
    assert rec.title.startswith("First question")
    assert len(rec.turns) == 2


def test_list_recent_orders_by_most_recently_updated():
    record_turn("a", "alpha", ["db"])
    record_turn("b", "bravo", ["macro"])
    record_turn("a", "alpha follow-up", ["db"])  # touches 'a' last
    recent = history.list_recent()
    assert [c.conversation_id for c in recent] == ["a", "b"]
    assert recent[0].turn_count == 2


def test_list_recent_respects_the_limit():
    for i in range(5):
        record_turn(f"c{i}", f"q{i}", ["db"])
    assert len(history.list_recent(limit=3)) == 3


def test_get_unknown_conversation_is_none():
    assert history.get("nope") is None


def test_conversations_and_context_are_isolated_by_user():
    record_turn("alice-chat", "Alice question", ["db"], user="alice")
    record_turn("bob-chat", "Bob question", ["db"], user="bob")

    assert history.get("bob-chat", user="alice") is None
    assert [
        item.conversation_id for item in history.list_recent(user="alice")
    ] == ["alice-chat"]
    assert history.load_messages("bob-chat", user="alice") == []


def test_previous_queries_are_owner_scoped_and_exclude_current_turn():
    old_turn = history.begin_turn("query-history", "alice", "First question")
    history.set_query_registry(
        "query-history",
        "alice",
        old_turn,
        [
            {
                "query_id": f"{old_turn}:q1",
                "status": "success",
            }
        ],
    )
    current_turn = history.begin_turn("query-history", "alice", "Follow up")
    history.set_query_registry(
        "query-history",
        "alice",
        current_turn,
        [
            {
                "query_id": f"{current_turn}:q2",
                "status": "pending",
            }
        ],
    )

    previous = history.previous_query_registry(
        "query-history",
        user="alice",
        turn_id=current_turn,
    )

    assert [item["query_id"] for item in previous] == [f"{old_turn}:q1"]
    assert (
        history.previous_query_registry(
            "query-history",
            user="bob",
            turn_id=current_turn,
        )
        == []
    )


def test_route_tools_and_structured_error_round_trip():
    turn_id = history.begin_turn("diagnostic", "alice", "Show PAR 30")
    history.set_route(
        "diagnostic",
        "alice",
        turn_id,
        sources=["db"],
        intent="Show PAR 30",
        model="native_agent",
        tools=["query_metrics"],
    )
    history.set_error(
        "diagnostic",
        "alice",
        turn_id,
        "The model timed out.",
        code="AGENT_TIMEOUT",
        retryable=True,
        reason="deadline",
    )

    turn = history.get("diagnostic", user="alice").turns[0]
    assert turn["route"]["tools"] == ["query_metrics"]
    assert turn["error"] == "The model timed out."
    assert turn["error_details"] == {
        "message": "The model timed out.",
        "code": "AGENT_TIMEOUT",
        "retryable": True,
        "reason": "deadline",
    }


def test_explicit_empty_query_attribution_survives_history_round_trip():
    turn_id = history.begin_turn("attribution", "alice", "What does PAR mean?")
    answer = {
        "schema_version": 1,
        "status": "answered",
        "text": "Portfolio at risk.",
        "active_query_ids": [],
        "visual_query_ids": [],
        "excluded_queries": [],
        "sources": [],
        "citations": [],
        "unavailable_sources": [],
        "limitations": [],
    }
    history.set_answer("attribution", "alice", turn_id, answer)

    stored = history.get("attribution", user="alice").turns[0]["answer"]
    assert stored["active_query_ids"] == []
    assert stored["visual_query_ids"] == []
    assert stored["excluded_queries"] == []


# --- Phase C: one history representation ------------------------------------------------


def test_save_refuses_a_record_version_it_does_not_understand():
    record = history.ConversationRecord(
        conversation_id="future",
        owner_username="alice",
        title="?",
        updated_at=history._now(),
        record_version=history.RECORD_VERSION + 1,
    )
    with pytest.raises(history.UnknownRecordVersion, match="record version"):
        history._save(record)
    assert ("alice", "future") not in history._MEMORY


class _FakeConn:
    def __init__(self):
        self.committed = 0
        self.rolled_back = 0

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


def test_cleanup_script_dry_run_and_apply(monkeypatch):
    import contextlib
    import importlib.util
    import sys
    from pathlib import Path

    from app.services import db_schema

    path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "clear_pre_release_workbench_history.py"
    )
    spec = importlib.util.spec_from_file_location(
        "clear_pre_release_workbench_history", path
    )
    script = importlib.util.module_from_spec(spec)
    # Registered before execution so the script's dataclass can resolve its
    # postponed annotations through sys.modules, as a normal import would.
    monkeypatch.setitem(sys.modules, spec.name, script)
    spec.loader.exec_module(script)

    class CleanupCursor:
        def __init__(self):
            self.statements = []

        def execute(self, sql, params=None):
            self.statements.append((sql, params))

        def fetchone(self):
            return (3,)

    cursor = CleanupCursor()
    conn = _FakeConn()

    @contextlib.contextmanager
    def fake_db_cursor():
        yield conn, cursor

    monkeypatch.setattr(db_schema, "db_cursor", fake_db_cursor)

    assert script.clear(apply=False) == 3
    assert conn.committed == 0 and conn.rolled_back == 1
    assert not any(sql.startswith("DELETE") for sql, _ in cursor.statements)

    assert script.clear(apply=True) == 3
    assert conn.committed == 1
    assert any(sql.startswith("DELETE") for sql, _ in cursor.statements)


def record_turn(conversation_id, question, sources, user="anonymous"):
    turn = history.begin_turn(conversation_id, user, question)
    history.set_route(conversation_id, user, turn, sources=sources, intent=question)
    history.complete_turn(conversation_id, user, turn)
