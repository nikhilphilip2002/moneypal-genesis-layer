"""Every question, plan, and statement, recorded.

Two audiences. Compliance needs to know who asked what and which rows were touched — every
query crossing a PII table is flagged. Engineering needs the failure record: each refusal,
each validator rejection, each thumbs-down is a catalog gap, and this table is where the
improvement backlog actually comes from (§7.5).

Writes go through the APPLICATION role, never `nlq_readonly` — the read-only role has no
INSERT privilege, which is the point of it. Reads of loan data and writes of audit rows are
deliberately different connections with different rights.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

TABLE = "public.nlq_audit_log"

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    turn_id          text PRIMARY KEY,
    conversation_id  text,
    ts               timestamptz NOT NULL DEFAULT now(),
    username         text,
    role             text,
    question         text NOT NULL,
    resolved_question text,
    route            text,
    outcome          text,
    plan_json        jsonb,
    sql              text,
    row_count        integer,
    duration_ms      integer,
    prompt_version   text,
    model            text,
    provider         text,
    touches_pii      boolean NOT NULL DEFAULT false,
    detail           text,
    feedback         text,
    feedback_comment text
);
CREATE INDEX IF NOT EXISTS ix_nlq_audit_ts ON {TABLE} (ts DESC);
CREATE INDEX IF NOT EXISTS ix_nlq_audit_outcome ON {TABLE} (outcome);
CREATE INDEX IF NOT EXISTS ix_nlq_audit_pii ON {TABLE} (touches_pii) WHERE touches_pii;
"""

_ready = False
_lock = threading.Lock()
_fallback: list[dict[str, Any]] = []


def ensure_table() -> bool:
    """Create the audit table if absent. Returns False when the database is unavailable."""
    global _ready
    with _lock:
        if _ready:
            return True
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(DDL)
                conn.commit()
            _ready = True
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("NLQ audit table unavailable, buffering in memory: %s", exc)
            return False


def record(
    *,
    turn_id: str,
    ctx: Any,
    resolved: str,
    route: str,
    outcome: str,
    plan: Any = None,
    spec: Any = None,
    sql: str = "",
    row_count: int = 0,
    duration_ms: int = 0,
    touches_pii: bool = False,
    detail: str = "",
) -> None:
    """Persist one turn. Never raises — losing an answer to a failed audit write would be
    a worse outcome than a gap in the log, and the gap is visible in the fallback buffer."""
    entry = {
        "turn_id": turn_id,
        "conversation_id": getattr(ctx, "conversation_id", ""),
        "ts": datetime.now(timezone.utc),
        "username": getattr(ctx, "user", "anonymous"),
        "role": getattr(ctx, "role", ""),
        "question": getattr(ctx, "question", ""),
        "resolved_question": resolved,
        "route": route,
        "outcome": outcome,
        "plan_json": _plan_json(plan, spec),
        "sql": sql,
        "row_count": row_count,
        "duration_ms": duration_ms,
        "prompt_version": getattr(plan, "prompt_version", ""),
        "model": getattr(plan, "model", ""),
        "provider": getattr(plan, "provider", ""),
        "touches_pii": touches_pii,
        "detail": detail[:2000],
    }

    if touches_pii:
        logger.info("NLQ query touched PII tables (turn %s, user %s)", turn_id, entry["username"])

    if not ensure_table():
        _fallback.append(entry)
        return

    try:
        from app.services.db_schema import db_cursor

        columns = list(entry)
        placeholders = ", ".join(["%s"] * len(columns))
        with db_cursor() as (conn, cur):
            cur.execute(
                f"INSERT INTO {TABLE} ({', '.join(columns)}) VALUES ({placeholders}) "
                "ON CONFLICT (turn_id) DO NOTHING",
                [entry[c] for c in columns],
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLQ audit write failed for turn %s: %s", turn_id, exc)
        _fallback.append(entry)


def _plan_json(plan: Any, spec: Any) -> str | None:
    payload: dict[str, Any] = {}
    if plan is not None and hasattr(plan, "plan"):
        try:
            payload["plan"] = plan.plan.model_dump(mode="json")
            payload["attempts"] = plan.attempts
            payload["repaired"] = plan.repaired
        except Exception:  # noqa: BLE001
            pass
    if spec is not None:
        try:
            payload["spec"] = spec.model_dump(mode="json")
        except Exception:  # noqa: BLE001
            pass
    return json.dumps(payload, default=str) if payload else None


def record_feedback(turn_id: str, verdict: str, comment: str = "") -> bool:
    """A thumbs-down is the start of a golden-set case, not just a rating."""
    if not ensure_table():
        return False
    try:
        from app.services.db_schema import db_cursor

        with db_cursor() as (conn, cur):
            cur.execute(
                f"UPDATE {TABLE} SET feedback = %s, feedback_comment = %s WHERE turn_id = %s",
                (verdict, comment[:2000], turn_id),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLQ feedback write failed for turn %s: %s", turn_id, exc)
        return False


def recent(limit: int = 50) -> list[dict[str, Any]]:
    """Recent turns, newest first. Powers the ops view and the catalog backlog."""
    if not ensure_table():
        return list(reversed(_fallback[-limit:]))
    try:
        from app.services.db_schema import db_cursor

        with db_cursor() as (conn, cur):
            cur.execute(
                "SELECT turn_id, ts, username, question, route, outcome, row_count, "
                f"duration_ms, touches_pii, feedback FROM {TABLE} ORDER BY ts DESC LIMIT %s",
                (limit,),
            )
            columns = [d[0] for d in cur.description]
            rows = [dict(zip(columns, r)) for r in cur.fetchall()]
            conn.rollback()
            return rows
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLQ audit read failed: %s", exc)
        return []


def buffered() -> list[dict[str, Any]]:
    """Entries that could not be persisted. Non-empty means the log has holes."""
    return list(_fallback)
