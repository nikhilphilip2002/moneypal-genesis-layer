import os
from contextlib import contextmanager

import pytest

from app.services import db_schema
from app.services.workbench import history

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_HISTORY_POSTGRES_TESTS") != "1",
    reason="Requires PostgreSQL; uses only a session-local temporary table",
)


@pytest.fixture
def postgres_history(monkeypatch):
    connection = db_schema.get_connection()
    cursor = connection.cursor()
    cursor.execute(
        history.DDL.replace(
            f"CREATE TABLE IF NOT EXISTS {history.TABLE}",
            "CREATE TEMP TABLE workbench_history_test",
        )
    )
    connection.commit()

    @contextmanager
    def db_cursor():
        yield connection, cursor

    monkeypatch.setattr(db_schema, "db_cursor", db_cursor)
    monkeypatch.setattr(history, "TABLE", "pg_temp.workbench_history_test")
    monkeypatch.setattr(history, "_ensure_table", lambda: True)
    monkeypatch.setattr(
        history.settings, "workbench_history_require_durable", True
    )
    history._MEMORY.clear()
    yield
    history._MEMORY.clear()
    connection.close()


def test_durable_reload_cached_read_and_conflicting_updates(postgres_history):
    turn = history.begin_turn("chat", "alice", "Question")
    history.set_answer("chat", "alice", turn, {"text": "Answer"})
    history.complete_turn("chat", "alice", turn)
    transcript = history.build_native_transcript("chat", user="alice")
    assert history.build_native_transcript("chat", user="alice") == transcript
    history._MEMORY.clear()
    assert history.build_native_transcript("chat", user="alice") == transcript
    assert history.get("chat", user="bob") is None

    first = history.get("chat", user="alice")
    stale = history.get("chat", user="alice")
    assert first is not None and stale is not None
    first.title = "Committed title"
    history._save(first)
    stale.title = "Lost update"
    with pytest.raises(history.HistoryConflict):
        history._save(stale)
    saved = history.get("chat", user="alice")
    assert saved is not None and saved.title == "Committed title"

    with pytest.raises(history.HistoryConflict):
        history.begin_turn("chat", "bob", "Take over")
    saved = history.get("chat", user="alice")
    assert saved is not None and saved.owner_username == "alice"
