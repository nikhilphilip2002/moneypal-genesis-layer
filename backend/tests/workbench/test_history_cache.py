from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import Mock
from typing import cast

import pytest

from app.services import db_schema
from app.services.workbench import graph, history


@pytest.fixture(autouse=True)
def clean_cache():
    history._MEMORY.clear()
    yield
    history._MEMORY.clear()


def install_database(monkeypatch, rows):
    connection = Mock()
    cursor = Mock()
    cursor.fetchone.side_effect = rows

    @contextmanager
    def db_cursor():
        yield connection, cursor

    monkeypatch.setattr(history, "_ensure_table", lambda: True)
    monkeypatch.setattr(db_schema, "db_cursor", db_cursor)
    monkeypatch.setattr(
        history.settings, "workbench_history_require_durable", True
    )
    return connection, cursor


def test_cached_history_checks_revision_and_refreshes_external_changes(
    monkeypatch,
):
    now = datetime.now(UTC)
    payload = {"version": 9, "turns": [], "title": "Initial"}
    _, cursor = install_database(
        monkeypatch,
        [
            ("Initial", payload, now, "alice", 9, 1),
            ("Initial", None, now, "alice", 9, 1),
            ("Changed", {**payload, "title": "Changed"}, now, "alice", 9, 2),
            None,
        ],
    )
    first = history.get("chat", user="alice")
    assert first is not None
    first.title = "Uncommitted mutation"
    second = history.get("chat", user="alice")
    assert second is not None and second.title == "Initial"
    assert cursor.execute.call_args_list[1].args[1][:2] == (1, now)
    updated = history.get("chat", user="alice")
    assert updated is not None and updated.title == "Changed"
    assert history.get("chat", user="bob") is None


def test_conflicting_write_never_overwrites_or_caches_uncommitted_record(
    monkeypatch,
):
    connection, _ = install_database(monkeypatch, [None])
    record = history.ConversationRecord(
        "chat", "Title", datetime.now(UTC), owner_username="alice", revision=1
    )
    with pytest.raises(history.HistoryConflict):
        history._save(record)
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()
    assert ("alice", "chat") not in history._MEMORY


def test_durable_history_rejects_memory_fallback(monkeypatch):
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    monkeypatch.setattr(
        history.settings, "workbench_history_require_durable", True
    )
    with pytest.raises(history.HistoryUnavailable):
        history.begin_turn("chat", "alice", "Question")
    assert not history._MEMORY


def test_replay_cache_is_isolated_and_invalidates_after_mutation(monkeypatch):
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    turn = history.begin_turn("chat", "alice", "First question")
    history.set_answer("chat", "alice", turn, {"text": "First answer"})
    history.complete_turn("chat", "alice", turn)
    original = history.native_replay_group
    spy = Mock(wraps=original)
    monkeypatch.setattr(history, "native_replay_group", spy)
    first = history.build_native_transcript("chat", user="alice")
    first[0]["content"] = "Caller mutation"
    second = history.build_native_transcript("chat", user="alice")
    assert second[0]["content"] == "First question"
    assert spy.call_count == 1
    next_turn = history.begin_turn("chat", "alice", "Second question")
    history.complete_turn("chat", "alice", next_turn)
    assert any(
        message.get("content") == "Second question"
        for message in history.build_native_transcript("chat", user="alice")
    )
    assert spy.call_count == 3


def test_history_cache_has_entry_and_byte_limits(monkeypatch):
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    monkeypatch.setattr(history.settings, "workbench_history_cache_entries", 1)
    history.begin_turn("first", "alice", "First")
    history.begin_turn("second", "alice", "Second")
    assert list(history._MEMORY) == [("alice", "second")]
    monkeypatch.setattr(history.settings, "workbench_history_cache_bytes", 1)
    history.begin_turn("third", "alice", "Third")
    assert ("alice", "third") not in history._MEMORY


@pytest.mark.anyio
async def test_answer_is_not_emitted_when_persistence_fails(monkeypatch):
    import asyncio

    def fail(*_args):
        raise history.HistoryUnavailable("Storage failed")

    monkeypatch.setattr(history, "set_answer", fail)
    state = {
        "conversation_id": "chat",
        "user": "alice",
        "turn_id": "turn",
        "emit": asyncio.Queue(),
    }
    with pytest.raises(history.HistoryUnavailable):
        await graph.emit_answer(
            cast(graph.WorkbenchState, state), {"text": "Answer"}
        )
    assert state["emit"].empty()
