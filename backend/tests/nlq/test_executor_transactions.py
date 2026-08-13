"""A failed EXPLAIN must not poison the transaction used for execution."""

from app.services.nlq.executor import _explain


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
