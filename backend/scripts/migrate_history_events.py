#!/usr/bin/env python3
"""One-off migration: give every stored Workbench conversation its event stream.

Records at version 6 or earlier kept a turn's history sideways — `agent_exchanges`,
`cards`, `synthesis`, `answer`, `error` — and readers stitched them back together. Version
7 records carry one ordered `events` list per turn and readers use nothing else. This
script derives `events` for every turn that lacks them (see `history.derive_turn_events`
for the order) and stamps the row version 7. Turns that already have events, and rows
already at version 7, are left untouched, so the script is safe to re-run.

Nothing is deleted: the sideways fields stay on the row for the rollback window, and
`WORKBENCH_HISTORY_WRITE_LEGACY_EXCHANGES` keeps new turns writing them until that
window has passed.

Examples (from the repo root, with the backend's database settings in the environment):

  PYTHONPATH=backend python backend/scripts/migrate_history_events.py            # dry run
  PYTHONPATH=backend python backend/scripts/migrate_history_events.py --apply
  PYTHONPATH=backend python backend/scripts/migrate_history_events.py --apply --conversation abc123
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from typing import Any

from app.services.workbench import history

logger = logging.getLogger("migrate_history_events")


@dataclass(slots=True)
class Report:
    scanned: int = 0
    migrated: int = 0
    turns_changed: int = 0
    skipped_current: int = 0
    refused_unknown_version: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def render(self, *, applied: bool) -> str:
        verb = "migrated" if applied else "would migrate"
        lines = [
            f"scanned {self.scanned} conversation(s) not at record_version {history.RECORD_VERSION}",
            f"{verb} {self.migrated} conversation(s), {self.turns_changed} turn(s) given events",
            f"skipped {self.skipped_current} already carrying events on every turn (version stamped only)",
        ]
        if self.refused_unknown_version:
            lines.append(
                "refused (unknown record version): " + ", ".join(self.refused_unknown_version)
            )
        if self.failed:
            lines.append("failed: " + ", ".join(self.failed))
        return "\n".join(lines)


def _rows(cur, conversation_id: str | None) -> list[tuple[str, int, Any]]:
    # Every row not already at the current version: older ones are migrated, and any
    # written by a newer backend is reported and refused rather than silently skipped.
    sql = (
        f"SELECT conversation_id, record_version, record_json FROM {history.TABLE} "
        f"WHERE record_version <> %s"
    )
    params: list[Any] = [history.RECORD_VERSION]
    if conversation_id:
        sql += " AND conversation_id = %s"
        params.append(conversation_id)
    cur.execute(sql + " ORDER BY updated_at", params)
    return list(cur.fetchall())


def migrate(*, apply: bool, conversation_id: str | None = None) -> Report:
    from app.services.db_schema import db_cursor

    report = Report()
    with db_cursor() as (conn, cur):
        for cid, version, raw in _rows(cur, conversation_id):
            report.scanned += 1
            if version not in history.KNOWN_RECORD_VERSIONS:
                report.refused_unknown_version.append(f"{cid} (v{version})")
                continue
            try:
                payload = raw if isinstance(raw, dict) else json.loads(raw)
                migrated, changed = history.migrate_payload(payload)
            except Exception as exc:  # noqa: BLE001 - report, keep going
                logger.exception("conversation %s could not be migrated", cid)
                report.failed.append(f"{cid} ({exc})")
                continue
            if changed:
                report.migrated += 1
                report.turns_changed += changed
            else:
                report.skipped_current += 1
            logger.info(
                "%s %s: v%s -> v%s, %d turn(s) given events",
                "migrating" if apply else "would migrate", cid, version,
                history.RECORD_VERSION, changed,
            )
            if not apply:
                continue
            cur.execute(
                f"UPDATE {history.TABLE} SET record_version = %s, record_json = %s "
                "WHERE conversation_id = %s AND record_version = %s",
                (history.RECORD_VERSION, json.dumps(migrated, default=str), cid, version),
            )
        if apply:
            conn.commit()
        else:
            conn.rollback()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--apply", action="store_true",
        help="write the migrated rows; without it the script only reports",
    )
    parser.add_argument(
        "--conversation", default=None, help="migrate one conversation id only",
    )
    parser.add_argument("--verbose", action="store_true", help="log every conversation")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    report = migrate(apply=args.apply, conversation_id=args.conversation)
    print(report.render(applied=args.apply))
    if not args.apply:
        print("dry run: nothing written; re-run with --apply to migrate")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
