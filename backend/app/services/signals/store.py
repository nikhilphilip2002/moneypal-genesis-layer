"""Where findings live between the scan and the question.

A standing problem is one signal with a history, not a fresh alarm every night. The
fingerprint — scope, detector, member — is what makes that true: a re-scan that finds the same
deterioration updates the existing row and leaves its acknowledgement alone. Without that, a
director who acknowledged Aluva's PAR breach on Monday sees it again on Tuesday, and by Friday
has stopped reading the feed.

Falls back to memory when no database is configured, as the rest of the product does.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.services.nlq.contracts import Signal

logger = logging.getLogger(__name__)

TABLE = "public.signals"
DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    fingerprint   text PRIMARY KEY,
    scope         text NOT NULL,
    kind          text NOT NULL,
    member        text NOT NULL DEFAULT '',
    severity      text NOT NULL,
    payload_json  jsonb NOT NULL,
    status        text NOT NULL DEFAULT 'open',
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at  timestamptz NOT NULL DEFAULT now(),
    acknowledged_by text
);
"""
INDEXES = (
    f"CREATE INDEX IF NOT EXISTS signals_open_idx ON {TABLE} (status, severity, last_seen_at DESC)",
)

STATUSES = ("open", "acknowledged", "resolved")

_table_ready = False
_MEMORY: dict[str, "StoredSignal"] = {}


@dataclass(slots=True)
class StoredSignal:
    signal: Signal
    status: str = "open"
    first_seen_at: datetime = None  # type: ignore[assignment]
    last_seen_at: datetime = None  # type: ignore[assignment]
    acknowledged_by: str = ""

    @property
    def is_standing(self) -> bool:
        """Seen on more than one scan. Worth showing differently: a problem that has been
        there for a week is a different conversation from one that appeared last night."""
        return self.first_seen_at != self.last_seen_at


class SignalStoreError(ValueError):
    """An operation that cannot be honoured — an unknown signal, or an invented status."""


def _ensure_table() -> bool:
    global _table_ready
    if _table_ready:
        return True
    try:
        from app.services.db_schema import db_cursor

        with db_cursor() as (conn, cur):
            cur.execute(DDL)
            for statement in INDEXES:
                cur.execute(statement)
            conn.commit()
        _table_ready = True
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("signals table unavailable, using memory: %s", exc)
        return False


def record(signals: list[Signal]) -> int:
    """Persist a scan's findings, merging with what is already known.

    Returns the number of signals that were new. An existing fingerprint has its reading
    refreshed and its acknowledgement preserved — the problem has not gone away, and it has
    not become news again either.
    """
    now = datetime.now(timezone.utc)
    new = 0

    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                for signal in signals:
                    cur.execute(
                        f"INSERT INTO {TABLE} (fingerprint, scope, kind, member, severity, "
                        "payload_json, first_seen_at, last_seen_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (fingerprint) DO UPDATE SET "
                        "  severity = EXCLUDED.severity, "
                        "  payload_json = EXCLUDED.payload_json, "
                        "  last_seen_at = EXCLUDED.last_seen_at "
                        "RETURNING (xmax = 0) AS inserted",
                        (
                            signal.fingerprint, signal.scope, signal.kind, signal.member,
                            signal.severity, json.dumps(signal.model_dump(mode="json")),
                            now, now,
                        ),
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        new += 1
                conn.commit()
            return new
        except Exception as exc:  # noqa: BLE001
            logger.warning("signal write failed, keeping in memory: %s", exc)

    for signal in signals:
        existing = _MEMORY.get(signal.fingerprint)
        if existing is None:
            _MEMORY[signal.fingerprint] = StoredSignal(
                signal=signal, first_seen_at=now, last_seen_at=now
            )
            new += 1
        else:
            existing.signal = signal
            existing.last_seen_at = now
    return new


def open_signals(
    *, scopes: list[str] | None = None, severities: list[str] | None = None, limit: int = 20
) -> list[StoredSignal]:
    """The current findings, most notable first.

    Resolved signals are excluded and acknowledged ones are kept: acknowledging says "I have
    seen this", not "this is fixed", and a briefing that hid acknowledged problems would let a
    standing deterioration disappear by being read.
    """
    records: list[StoredSignal]

    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            clauses = ["status <> 'resolved'"]
            params: list[Any] = []
            if scopes:
                clauses.append("scope = ANY(%s)")
                params.append(list(scopes))
            if severities:
                clauses.append("severity = ANY(%s)")
                params.append(list(severities))
            params.append(limit)

            with db_cursor() as (conn, cur):
                cur.execute(
                    f"SELECT payload_json, status, first_seen_at, last_seen_at, "
                    f"COALESCE(acknowledged_by, '') FROM {TABLE} WHERE "
                    + " AND ".join(clauses)
                    + " ORDER BY CASE severity WHEN 'alert' THEN 0 WHEN 'watch' THEN 1 "
                      "ELSE 2 END, last_seen_at DESC LIMIT %s",
                    params,
                )
                rows = cur.fetchall()
                conn.rollback()
            return [
                StoredSignal(
                    signal=Signal.model_validate(_json(row[0])),
                    status=row[1], first_seen_at=row[2], last_seen_at=row[3],
                    acknowledged_by=row[4],
                )
                for row in rows
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("signal read failed, falling back to memory: %s", exc)

    records = [s for s in _MEMORY.values() if s.status != "resolved"]
    if scopes:
        records = [s for s in records if s.signal.scope in scopes]
    if severities:
        records = [s for s in records if s.signal.severity in severities]
    rank = {"alert": 0, "watch": 1, "info": 2}
    records.sort(key=lambda s: (rank.get(s.signal.severity, 2), -s.last_seen_at.timestamp()))
    return records[:limit]


def set_status(fingerprint: str, status: str, *, user: str = "") -> StoredSignal:
    """Acknowledge or resolve one finding. Only a person calls this."""
    if status not in STATUSES:
        raise SignalStoreError(f"unknown status {status!r} — one of {', '.join(STATUSES)}")

    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(
                    f"UPDATE {TABLE} SET status = %s, acknowledged_by = %s "
                    "WHERE fingerprint = %s "
                    "RETURNING payload_json, status, first_seen_at, last_seen_at, "
                    "COALESCE(acknowledged_by, '')",
                    (status, user, fingerprint),
                )
                row = cur.fetchone()
                conn.commit()
            if row is None:
                raise SignalStoreError(f"unknown signal {fingerprint!r}")
            return StoredSignal(
                signal=Signal.model_validate(_json(row[0])),
                status=row[1], first_seen_at=row[2], last_seen_at=row[3],
                acknowledged_by=row[4],
            )
        except SignalStoreError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("signal status write failed: %s", exc)

    stored = _MEMORY.get(fingerprint)
    if stored is None:
        raise SignalStoreError(f"unknown signal {fingerprint!r}")
    stored.status = status
    stored.acknowledged_by = user
    return stored


def _json(value: Any) -> Any:
    if isinstance(value, (dict, list)) or value is None:
        return value
    return json.loads(value)


__all__ = [
    "STATUSES",
    "SignalStoreError",
    "StoredSignal",
    "open_signals",
    "record",
    "set_status",
]
