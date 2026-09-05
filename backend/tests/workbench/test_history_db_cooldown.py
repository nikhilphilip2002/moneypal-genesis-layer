"""A database outage must not trigger one history connection attempt per mutation."""

from app.services import db_schema
from app.services.workbench import history


def test_history_table_failure_suppresses_immediate_retries(monkeypatch):
    calls = 0

    def unavailable_cursor():
        nonlocal calls
        calls += 1
        raise RuntimeError("database down")

    monkeypatch.setattr(db_schema, "db_cursor", unavailable_cursor)
    monkeypatch.setattr(history, "_table_ready", False)
    monkeypatch.setattr(history, "_table_retry_after", 0.0)

    assert history._ensure_table() is False
    assert history._ensure_table() is False
    assert calls == 1
