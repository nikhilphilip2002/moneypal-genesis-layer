"""A failed EXPLAIN must not poison the transaction used for execution."""

from contextlib import contextmanager

import pytest

from app.services.nlq import executor
from app.services.nlq.executor import QueryTimeoutError, _explain


class _Connection:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


class _FailingCursor:
    def execute(self, _sql, *_params):
        raise RuntimeError("bad generated column")


class _RecordingCursor:
    def __init__(self):
        self.args = None

    def execute(self, *args):
        self.args = args

    def fetchall(self):
        return [["Seq Scan  (cost=0.00..1.00 rows=1 width=4)"]]


def test_failed_explain_rolls_back_the_connection():
    connection = _Connection()

    assert _explain(connection, _FailingCursor(), "SELECT broken", []) is None
    assert connection.rollbacks == 1


def test_explain_omits_empty_parameter_sequence_for_literal_percent_signs():
    cursor = _RecordingCursor()

    assert _explain(_Connection(), cursor, "SELECT 'name%'", []) == 1.0
    assert cursor.args == ("EXPLAIN SELECT 'name%'",)


def test_execute_raw_classifies_postgres_statement_timeout(monkeypatch):
    class QueryCanceled(Exception):
        sqlstate = "57014"

    class Cursor:
        description = None

        def execute(self, sql):
            if not sql.startswith("EXPLAIN "):
                raise QueryCanceled("canceling statement due to statement timeout")

        def fetchall(self):
            return [["Seq Scan  (cost=0.00..1.00 rows=1 width=4)"]]

    @contextmanager
    def readonly_cursor():
        yield _Connection(), Cursor()

    monkeypatch.setattr(executor.nlq_db, "readonly_cursor", readonly_cursor)
    monkeypatch.setattr(executor.settings, "nlq_statement_timeout_ms", 15_000)

    with pytest.raises(QueryTimeoutError) as caught:
        executor.execute_raw("SELECT value FROM gold.slow_view LIMIT 1")

    assert caught.value.code == "QUERY_TIMEOUT"
    assert "15-second execution limit" in str(caught.value)
    assert "do not repeat the same SQL" in str(caught.value)
