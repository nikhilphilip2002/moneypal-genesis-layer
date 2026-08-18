"""CLI for the Macro Intelligence refresh pipeline.

    python -m scripts.macro_pipeline.run once [--force]   # refresh now
    python -m scripts.macro_pipeline.run schedule         # weekly worker (Sun 10:00 IST)
    python -m scripts.macro_pipeline.run analyze <file>   # topics/figures, no ingest
    python -m scripts.macro_pipeline.run sources          # show configured sources
    python -m scripts.macro_pipeline.run stats            # collection point counts
    python -m scripts.macro_pipeline.run migrate [--apply]  # drop legacy unstamped points

Run from the ``backend/`` directory, or invoke the file directly from anywhere —
the sys.path bootstrap below mirrors ``backend/scripts/ingest.py``.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):  # invoked as a path, not with -m
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "scripts.macro_pipeline"

from app.core.config import settings  # noqa: E402

from . import collector, ingestor, pipeline, structured  # noqa: E402


def _setup_logging(verbose: bool) -> None:
    log_dir = settings.macro_data_dir.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "macro_pipeline.log", encoding="utf-8"),
        ],
    )


def _cmd_once(args) -> int:
    summary = pipeline.run(force=args.force)
    pipeline.print_summary(summary)
    return 0


def _cmd_schedule(args) -> int:
    from . import scheduler

    return scheduler.main()


def _cmd_sources(args) -> int:
    for source in collector.load_sources():
        print(f"{source['slug']:24} <- {source['url']}")
    return 0


def _cmd_stats(args) -> int:
    stats = ingestor.stats()
    stats["legacy_unstamped"] = ingestor.count_unstamped()
    print(json.dumps(stats, indent=2))
    return 0


def _cmd_analyze(args) -> int:
    from . import extractor

    rows = list(structured.extract_snapshot(extractor.extract(Path(args.file))))
    for row in rows:
        print("\n" + "=" * 70)
        print(f"[chunk {row['chunk_index']}] page={row['page']} topics={row['topics']}")
        print("figures:", json.dumps(row["figures"], ensure_ascii=False)[:700])
        print("-" * 70)
        print(row["text"][:500])
    print(f"\nTotal chunks: {len(rows)}")
    return 0


def _cmd_migrate(args) -> int:
    """Drop macro points written by the legacy ingest script (no ``ingest_run``).

    Their IDs use a different scheme, so without this the first refresh adds a
    second copy of every chunk instead of replacing it.
    """
    doomed = ingestor.count_unstamped()
    print(f"Collection: {settings.macro_collection}")
    print(f"Points with no ingest_run stamp (predate this pipeline): {doomed}")
    if not args.apply:
        print(
            "\nThese cover sources the crawler cannot reach (mospi / msme / karnataka_des\n"
            "are TLS-, auth- or manual-only). Deleting them without first restoring their\n"
            "PDFs into the data directory shrinks the macro corpus.\n"
        )
        print("Dry run. Snapshot the collection, then re-run with --apply:")
        print(f"  curl -X POST \"$QDRANT_URL/collections/{settings.macro_collection}/snapshots\"")
        print("  python -m scripts.macro_pipeline.run migrate --apply")
        print("  python -m scripts.macro_pipeline.run once --force")
        return 0
    deleted = ingestor.delete_unstamped()
    print(f"Deleted {deleted} legacy point(s). Now run: once --force")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="macro-pipeline", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    once = sub.add_parser("once", help="run a refresh now")
    once.add_argument("--force", action="store_true", help="re-embed every file")
    once.set_defaults(func=_cmd_once)

    sub.add_parser("schedule", help="start the weekly worker").set_defaults(func=_cmd_schedule)
    sub.add_parser("sources", help="list configured sources").set_defaults(func=_cmd_sources)
    sub.add_parser("stats", help="collection point counts").set_defaults(func=_cmd_stats)

    analyze = sub.add_parser("analyze", help="show topics/figures for one file")
    analyze.add_argument("file")
    analyze.set_defaults(func=_cmd_analyze)

    migrate = sub.add_parser("migrate", help="drop legacy unstamped macro points")
    migrate.add_argument("--apply", action="store_true", help="actually delete (default: dry run)")
    migrate.set_defaults(func=_cmd_migrate)

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
