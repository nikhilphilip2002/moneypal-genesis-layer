"""Saved worklists: a list somebody is working, not a list somebody looked at.

"Today's collection priority list" is a durable object. It gets assigned, worked through over
a day, and reviewed the next morning against what actually happened — none of which is
possible if the list only exists inside one chat turn.

Two decisions worth stating:

**The rows are frozen at save time.** Re-running the rules tomorrow produces a different list,
which is correct for a fresh list and wrong for one already half-worked: an account that was
paid overnight would silently vanish along with the note saying who called it. The saved
snapshot is the record; `build` produces the next one.

**Status is per item, and only a person sets it.** Nothing here infers that an account was
contacted. The one thing worse than no collections tracking is collections tracking that
quietly marks work as done.

Falls back to memory when no database is configured, exactly as workbench history does, so a
dev box behaves the same as production minus durability.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.nlq.contracts import Worklist

logger = logging.getLogger(__name__)

TABLE = "public.saved_worklists"
DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    worklist_id  text PRIMARY KEY,
    preset_id    text NOT NULL,
    owner        text NOT NULL DEFAULT 'anonymous',
    title        text NOT NULL,
    payload_json jsonb NOT NULL,
    statuses     jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
"""

STATUSES = ("open", "in_progress", "contacted", "promised", "paid", "escalated", "closed")
"""The states a collections officer actually moves an account through. `promised` is separate
from `contacted` on purpose — a promise to pay is the thing worth chasing tomorrow, and
collapsing it into "we spoke to them" loses the only follow-up date the list has."""

_table_ready = False
_MEMORY: dict[str, "SavedWorklist"] = {}


@dataclass(slots=True)
class SavedWorklist:
    worklist_id: str
    preset_id: str
    title: str
    owner: str
    worklist: Worklist
    statuses: dict[str, dict[str, Any]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class SavedWorklistSummary:
    worklist_id: str
    preset_id: str
    title: str
    created_at: datetime
    item_count: int
    open_count: int


class WorklistStoreError(ValueError):
    """An operation that cannot be honoured — an unknown list, or a status nobody defined."""


def _ensure_table() -> bool:
    global _table_ready
    if _table_ready:
        return True
    try:
        from app.services.db_schema import db_cursor

        with db_cursor() as (conn, cur):
            cur.execute(DDL)
            conn.commit()
        _table_ready = True
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("saved worklist table unavailable, using memory: %s", exc)
        return False


def save(worklist: Worklist, *, owner: str = "anonymous") -> SavedWorklist:
    """Freeze a generated list so it can be worked and reviewed."""
    saved = SavedWorklist(
        worklist_id=str(uuid.uuid4()),
        preset_id=worklist.id,
        title=worklist.title,
        owner=owner,
        worklist=worklist,
        statuses={item.account: {"status": "open"} for item in worklist.items},
    )

    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(
                    f"INSERT INTO {TABLE} (worklist_id, preset_id, owner, title, payload_json, "
                    "statuses) VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        saved.worklist_id,
                        saved.preset_id,
                        owner,
                        saved.title,
                        json.dumps(worklist.model_dump(mode="json")),
                        json.dumps(saved.statuses),
                    ),
                )
                conn.commit()
            return saved
        except Exception as exc:  # noqa: BLE001
            logger.warning("saved worklist write failed, keeping in memory: %s", exc)

    _MEMORY[saved.worklist_id] = saved
    return saved


def get(worklist_id: str, *, owner: str = "anonymous") -> SavedWorklist | None:
    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(
                    f"SELECT preset_id, title, payload_json, statuses, created_at, updated_at "
                    f"FROM {TABLE} WHERE worklist_id = %s AND owner = %s",
                    (worklist_id, owner),
                )
                row = cur.fetchone()
                conn.rollback()
            if row is None:
                return None
            preset_id, title, payload, statuses, created_at, updated_at = row
            return SavedWorklist(
                worklist_id=worklist_id,
                preset_id=preset_id,
                title=title,
                owner=owner,
                worklist=Worklist.model_validate(_json(payload)),
                statuses=_json(statuses) or {},
                created_at=created_at,
                updated_at=updated_at,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("saved worklist read failed, falling back to memory: %s", exc)

    saved = _MEMORY.get(worklist_id)
    return saved if saved and saved.owner == owner else None


def list_recent(*, owner: str = "anonymous", limit: int = 20) -> list[SavedWorklistSummary]:
    records: list[SavedWorklist] = []

    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(
                    f"SELECT worklist_id, preset_id, title, payload_json, statuses, created_at "
                    f"FROM {TABLE} WHERE owner = %s ORDER BY created_at DESC LIMIT %s",
                    (owner, limit),
                )
                rows = cur.fetchall()
                conn.rollback()
            return [
                SavedWorklistSummary(
                    worklist_id=row[0],
                    preset_id=row[1],
                    title=row[2],
                    created_at=row[5],
                    item_count=len((_json(row[3]) or {}).get("items", [])),
                    open_count=sum(
                        1 for s in (_json(row[4]) or {}).values()
                        if s.get("status") == "open"
                    ),
                )
                for row in rows
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("saved worklist listing failed, falling back to memory: %s", exc)

    records = [s for s in _MEMORY.values() if s.owner == owner]
    records.sort(key=lambda s: s.created_at, reverse=True)
    return [
        SavedWorklistSummary(
            worklist_id=s.worklist_id,
            preset_id=s.preset_id,
            title=s.title,
            created_at=s.created_at,
            item_count=len(s.worklist.items),
            open_count=sum(1 for v in s.statuses.values() if v.get("status") == "open"),
        )
        for s in records[:limit]
    ]


def set_status(
    worklist_id: str,
    account: str,
    status: str,
    *,
    owner: str = "anonymous",
    note: str = "",
    assigned_to: str = "",
) -> SavedWorklist:
    """Record what a person did about one account. Only a person calls this."""
    if status not in STATUSES:
        raise WorklistStoreError(
            f"unknown status {status!r} — one of {', '.join(STATUSES)}"
        )
    saved = get(worklist_id, owner=owner)
    if saved is None:
        raise WorklistStoreError(f"unknown worklist {worklist_id!r}")
    if account not in saved.statuses:
        raise WorklistStoreError(f"account {account!r} is not on this list")

    entry: dict[str, Any] = {"status": status, "updated_at": _now().isoformat()}
    if note:
        entry["note"] = note
    if assigned_to:
        entry["assigned_to"] = assigned_to
    saved.statuses[account] = entry
    saved.updated_at = _now()

    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(
                    f"UPDATE {TABLE} SET statuses = %s, updated_at = now() "
                    "WHERE worklist_id = %s AND owner = %s",
                    (json.dumps(saved.statuses), worklist_id, owner),
                )
                conn.commit()
            return saved
        except Exception as exc:  # noqa: BLE001
            logger.warning("saved worklist status write failed: %s", exc)

    _MEMORY[worklist_id] = saved
    return saved


def _json(value: Any) -> Any:
    """psycopg returns jsonb as a dict already; a text column comes back as a string."""
    if isinstance(value, (dict, list)) or value is None:
        return value
    return json.loads(value)


def _now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "STATUSES",
    "SavedWorklist",
    "SavedWorklistSummary",
    "WorklistStoreError",
    "get",
    "list_recent",
    "save",
    "set_status",
]
