"""Standing signals: findings the system formed before anybody asked.

"What are the emerging issues?", "What am I not asking?", "What decisions need my attention?"
are the questions a director most wants answered, and the ones a request-scoped product
cannot answer at all. By the time the question arrives there is no baseline to compare
against and nothing has been ranked — so a model asked it will describe an ordinary month as
unusual, with total confidence and no way for the reader to tell.

The scan runs on a schedule instead. Every scope is a governed query, every detector is
arithmetic, and every finding carries the `QuerySpec` that produced it, so a signal is one
click from the chart behind it. That turns the question into retrieval over pre-computed
evidence, which is the only version of it that is trustworthy.

Two properties are worth defending when this is extended:

**Abstention is a result.** Genesis holds very little history — the portfolio snapshot begins
2026-05-22 — so the statistical detectors decline to judge below six periods and the scan
reports which scopes abstained. "Not enough data yet" and "nothing is wrong" must never look
the same on a dashboard.

**A standing problem is one signal with a history.** The fingerprint is scope, detector and
member, so a re-scan updates rather than re-announces. Without that, a director who
acknowledged a breach on Monday sees it again on Tuesday and has stopped reading by Friday.
"""

from app.services.signals.morning import BriefingError, build as briefing, personas
from app.services.signals.scan import ScanError, run
from app.services.signals.store import (
    SignalStoreError,
    StoredSignal,
    open_signals,
    record,
    set_status,
)

__all__ = [
    "BriefingError",
    "ScanError",
    "SignalStoreError",
    "StoredSignal",
    "briefing",
    "open_signals",
    "personas",
    "record",
    "run",
    "set_status",
]
