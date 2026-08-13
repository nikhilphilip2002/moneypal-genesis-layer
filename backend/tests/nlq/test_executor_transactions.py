"""A failed EXPLAIN must not poison the transaction used for execution."""

from app.services.nlq.executor import _explain


class _Connection:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


class _FailingCursor:
    def execute(self, _sql, _params):
        raise RuntimeError("bad generated column")


def test_failed_explain_rolls_back_the_connection():
    connection = _Connection()

    assert _explain(connection, _FailingCursor(), "SELECT broken", []) is None
    assert connection.rollbacks == 1
