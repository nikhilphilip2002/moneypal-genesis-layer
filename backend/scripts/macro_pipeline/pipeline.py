"""Orchestrator — one macro refresh.

    collect -> fingerprint -> extract -> structure -> embed -> upsert -> purge stale

Every run gets an id; every point it writes or re-confirms is stamped with it, and
once the run succeeds anything still carrying an older stamp is deleted. Files
already sitting in the data directory that the crawl did not return (manually
placed PDFs, or sources that are auth-gated this week) are re-stamped too, so the
purge never mistakes them for retired documents.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from genesis_core import rag

from app.core.config import settings

from . import collector, extractor, ingestor, structured

log = logging.getLogger("macro.pipeline")


def _read_state() -> dict:
    if not settings.macro_state_file.exists():
        return {"collections": {}, "last_run": None}
    try:
        return json.loads(settings.macro_state_file.read_text(encoding="utf-8"))
    except Exception:
        log.warning("state file unreadable; starting fresh")
        return {"collections": {}, "last_run": None}


def _save_state(state: dict) -> None:
    settings.macro_state_file.parent.mkdir(parents=True, exist_ok=True)
    settings.macro_state_file.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _files_state(state: dict) -> dict:
    """Per-collection manifest: switching MACRO_COLLECTION must not make the
    pipeline skip files it only ever ingested into a *different* collection."""
    return state.setdefault("collections", {}).setdefault(settings.macro_collection, {})


def _embed_and_upsert(paths: list[Path], slug: str, run_id: str, source_url: str = "") -> int:
    rows = extractor.extract_many(paths)
    for row in rows:
        row["source_url"] = source_url or row.get("source_url", "")
    if not rows:
        return 0
    enriched = list(structured.extract_snapshot(rows))
    vectors = rag.embed_batch([row["text"] for row in enriched])
    return ingestor.upsert_rows(zip(enriched, vectors), slug, run_id)


def _local_slug_dirs() -> dict[str, list[Path]]:
    """Files on disk grouped by source slug, including any placed there by hand.

    Loose files directly under the data dir (how ``backend/data/macro`` is laid out
    today) are attributed to the ``manual`` slug.
    """
    grouped: dict[str, list[Path]] = {}
    root = settings.macro_data_dir
    if not root.is_dir():
        return grouped
    for path in sorted(root.iterdir()):
        if path.is_dir():
            files = [p for p in sorted(path.iterdir()) if p.suffix.lower() in collector.DOWNLOAD_EXTENSIONS]
            if files:
                grouped[path.name] = files
        elif path.suffix.lower() in collector.DOWNLOAD_EXTENSIONS:
            grouped.setdefault("manual", []).append(path)
    return grouped


def run(force: bool = False) -> dict:
    started = time.monotonic()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    state = _read_state()
    files_state = _files_state(state)

    ingestor.ensure_collection()
    points_before = ingestor.count()

    summary = {
        "run_id": run_id,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "collection": settings.macro_collection,
        "sources": {},
        "files_new": 0,
        "files_changed": 0,
        "files_unchanged": 0,
        "points_upserted": 0,
        "points_restamped": 0,
        "points_before": points_before,
        "errors": 0,
    }

    # Previous-run HTTP validators, keyed by URL, so the crawl can send conditional GETs.
    known_by_url = {entry["url"]: {**entry, "path": path} for path, entry in files_state.items() if entry.get("url")}

    results = collector.collect(known_by_url)
    # A source that errored without yielding anything means we are looking at a partial
    # view of the world — never purge on the strength of that.
    safe_to_purge = not any(result.failed for result in results)
    handled: set[tuple[str, str]] = set()   # (slug, document) touched this run

    for result in results:
        meta = {
            "url": result.source_url,
            "pages_seen": result.pages_seen,
            "downloaded": len(result.downloaded),
            "blocked": len(result.blocked),
            "errors": result.errors,
            "new": 0,
            "changed": 0,
            "unchanged": 0,
            "points": 0,
        }

        for record in result.downloaded:
            key = str(record.path)
            previous = files_state.get(key)
            handled.add((result.source_slug, record.path.name))

            if previous and previous.get("sha256") == record.sha256 and not force:
                # Unchanged: keep the vectors, just move them onto this generation.
                restamped = ingestor.restamp_document(record.path.name, result.source_slug, run_id)
                summary["points_restamped"] += restamped
                meta["unchanged"] += 1
                summary["files_unchanged"] += 1
                # Refresh the validators even when the bytes did not move.
                previous.update({"etag": record.etag, "last_modified": record.last_modified})
                _save_state(state)
                continue

            # New or changed: clear the old chunks first so a shorter revision cannot
            # leave an orphaned tail behind, then re-embed.
            ingestor.delete_document(record.path.name, result.source_slug)
            sent = _embed_and_upsert([record.path], result.source_slug, run_id, record.url)

            files_state[key] = {
                "sha256": record.sha256,
                "size": record.size,
                "url": record.url,
                "content_type": record.content_type,
                "etag": record.etag,
                "last_modified": record.last_modified,
                "points": sent,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            # Persist after every file: an interrupted run must not reprocess documents
            # that already made it into the collection.
            _save_state(state)

            if previous:
                meta["changed"] += 1
                summary["files_changed"] += 1
            else:
                meta["new"] += 1
                summary["files_new"] += 1
            meta["points"] += sent
            summary["points_upserted"] += sent
            log.info(
                "[%s] %s (%s) -> %d points",
                result.source_slug, record.path.name, "changed" if previous else "new", sent,
            )

        summary["sources"][result.source_slug] = meta
        summary["errors"] += len(result.errors)

    # Files on disk the crawl did not return this week (manually placed, or a source
    # that was gated today). Ingest them if they are new, otherwise re-stamp so the
    # purge leaves them alone.
    for slug, paths in _local_slug_dirs().items():
        for path in paths:
            if (slug, path.name) in handled:
                continue
            key = str(path)
            previous = files_state.get(key)
            digest = _sha256(path)
            if previous and previous.get("sha256") == digest and not force:
                summary["points_restamped"] += ingestor.restamp_document(path.name, slug, run_id)
                summary["files_unchanged"] += 1
                continue
            ingestor.delete_document(path.name, slug)
            sent = _embed_and_upsert([path], slug, run_id)
            files_state[key] = {
                "sha256": digest,
                "size": path.stat().st_size,
                "url": "",
                "content_type": "",
                "points": sent,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            _save_state(state)
            summary["points_upserted"] += sent
            summary["files_new" if not previous else "files_changed"] += 1
            log.info("[%s] %s (local) -> %d points", slug, path.name, sent)

    stamped = summary["points_upserted"] + summary["points_restamped"]
    summary["purge"] = ingestor.purge_stale(run_id, stamped, points_before, safe_to_purge)

    state["last_run"] = summary["ran_at"]
    state["last_run_id"] = run_id
    _save_state(state)

    summary["duration_s"] = round(time.monotonic() - started, 1)
    summary["qdrant"] = ingestor.stats()
    return summary


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def print_summary(summary: dict) -> None:
    purge = summary.get("purge", {})
    print("\n================== Macro Refresh Summary ==================")
    print(f"Run id:     {summary['run_id']}")
    print(f"Collection: {summary['collection']}")
    print(f"Duration:   {summary['duration_s']}s")
    print(f"Files:      new={summary['files_new']} changed={summary['files_changed']} "
          f"unchanged={summary['files_unchanged']}")
    print(f"Points:     upserted={summary['points_upserted']} restamped={summary['points_restamped']} "
          f"(before={summary['points_before']})")
    if purge.get("ran"):
        print(f"Purge:      deleted {purge['deleted']} stale point(s)")
    else:
        print(f"Purge:      SKIPPED — {purge.get('reason', 'unknown')}")
    print(f"Errors:     {summary['errors']}")
    print(f"Qdrant:     {summary['qdrant']}")
    for slug, meta in summary["sources"].items():
        print(f"  [{slug}] pages={meta['pages_seen']} dl={meta['downloaded']} new={meta['new']} "
              f"chg={meta['changed']} same={meta['unchanged']} blocked={meta['blocked']} pts={meta['points']}")
    print("===========================================================\n")
