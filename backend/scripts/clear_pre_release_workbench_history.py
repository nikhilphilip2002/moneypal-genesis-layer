#!/usr/bin/env python3
"""Delete unsupported pre-release Workbench conversations.

Run without ``--apply`` to report the count. The apply mode deletes only records whose
version predates the current raw-query/explicit-visual contract.
"""

from __future__ import annotations

import argparse
import sys

from app.services.workbench import history


def clear(*, apply: bool) -> int:
    from app.services.db_schema import db_cursor

    with db_cursor() as (conn, cur):
        cur.execute(
            f"SELECT count(*) FROM {history.TABLE} WHERE record_version < %s",
            (history.RECORD_VERSION,),
        )
        count = int(cur.fetchone()[0])
        if apply:
            cur.execute(
                f"DELETE FROM {history.TABLE} WHERE record_version < %s",
                (history.RECORD_VERSION,),
            )
            conn.commit()
        else:
            conn.rollback()
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="delete unsupported records; without this flag nothing is changed",
    )
    args = parser.parse_args(argv)
    count = clear(apply=args.apply)
    verb = "deleted" if args.apply else "would delete"
    print(f"{verb} {count} unsupported Workbench conversation(s)")
    if not args.apply:
        print("dry run: nothing deleted; re-run with --apply after verification")
    return 0


if __name__ == "__main__":
    sys.exit(main())
