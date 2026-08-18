"""Stage 4 — Ingestor: upsert into Qdrant and purge what the refresh superseded.

Point IDs are deterministic:

    uuid5(NAMESPACE_URL, "<source_slug>:<document>:<page>:<chunk_index>")

The source slug is part of the key because two portals can and do serve files
with the same name (``index.aspx.pdf``, ``Infographics English.pdf``) — keying on
the filename alone silently overwrites one source's chunks with another's.

Staleness is handled with a generation stamp rather than a wipe-and-rebuild, so
the collection is never empty while a refresh is in flight:

  * every point written or re-confirmed by a run carries ``ingest_run = <run id>``
  * a changed document has its old points deleted by filter before the new ones land
    (a shorter revision would otherwise leave an orphaned chunk tail behind)
  * after a successful run, points still carrying an older ``ingest_run`` are deleted

The payload shape mirrors ``backend/scripts/ingest.py`` so ``genesis_core.rag.search``
resolves ``source``/``page`` into real citations.
"""
from __future__ import annotations

import logging
import uuid
from typing import Iterable

from genesis_core import rag

from app.core.config import settings

log = logging.getLogger("macro.ingestor")

UPSERT_BATCH = 64
# Filtered delete/set_payload scan these, so they need keyword indexes to stay cheap.
INDEXED_FIELDS = ("module", "ingest_run", "document", "source_slug")


def collection() -> str:
    return settings.macro_collection


def client():
    return rag.get_qdrant()


def ensure_collection() -> None:
    """Create-if-missing (never recreate) plus the payload indexes the purge needs."""
    from qdrant_client.http import models

    rag.ensure_collection(collection())
    for field in INDEXED_FIELDS:
        try:
            client().create_payload_index(
                collection_name=collection(),
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            # Already indexed — Qdrant returns an error rather than a no-op.
            pass


def point_id(source_slug: str, document: str, page: int | None, chunk_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_slug}:{document}:{page}:{chunk_index}"))


def _macro_filter(**kwargs):
    """Filter over this module's points. Keyword args become equality conditions."""
    from qdrant_client.http import models

    must = [models.FieldCondition(key="module", match=models.MatchValue(value="macro"))]
    for key, value in kwargs.items():
        must.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))
    return models.Filter(must=must)


def delete_document(document: str, source_slug: str) -> None:
    """Drop every existing point for one document before re-ingesting it."""
    from qdrant_client.http import models

    client().delete(
        collection_name=collection(),
        points_selector=models.FilterSelector(
            filter=_macro_filter(document=document, source_slug=source_slug)
        ),
        wait=True,
    )


def restamp_document(document: str, source_slug: str, run_id: str) -> int:
    """Mark an unchanged document as seen by this run — no re-embedding.

    Without this, an unchanged file's points keep an older ``ingest_run`` and the
    end-of-run purge would delete perfectly good vectors.
    """
    client().set_payload(
        collection_name=collection(),
        payload={"ingest_run": run_id},
        points=_macro_filter(document=document, source_slug=source_slug),
        wait=True,
    )
    return count(document=document, source_slug=source_slug)


def upsert_rows(rows: Iterable[tuple[dict, list[float]]], source_slug: str, run_id: str) -> int:
    """Upsert (row, vector) pairs in batches. Returns the number of points written."""
    from qdrant_client.http import models

    points: list[models.PointStruct] = []
    sent = 0

    def flush() -> None:
        nonlocal sent, points
        if points:
            client().upsert(collection_name=collection(), points=points, wait=True)
            sent += len(points)
            points = []

    for row, vector in rows:
        points.append(
            models.PointStruct(
                id=point_id(source_slug, row["document"], row.get("page"), row["chunk_index"]),
                vector=vector,
                payload={
                    "module": "macro",
                    # `source` is what rag.search surfaces as the citation label, so it
                    # must be the document name — not the slug.
                    "source": row["document"],
                    "document": row["document"],
                    "source_url": row.get("source_url", ""),
                    "source_slug": source_slug,
                    "page": row.get("page"),
                    "chunk_index": row["chunk_index"],
                    "text": row["text"],
                    "topics": row.get("topics", []),
                    "figures": row.get("figures", []),
                    "ingest_run": run_id,
                },
            )
        )
        if len(points) >= UPSERT_BATCH:
            flush()
    flush()
    return sent


def count(**kwargs) -> int:
    """Count this module's points, optionally narrowed by payload equality."""
    if not client().collection_exists(collection()):
        return 0
    return client().count(
        collection_name=collection(), count_filter=_macro_filter(**kwargs), exact=True
    ).count


def total_points() -> int:
    """Every point in the collection, including any not written by this pipeline."""
    if not client().collection_exists(collection()):
        return 0
    return client().count(collection_name=collection(), exact=True).count


def _stale_filter(run_id: str):
    """Points this pipeline should retire at the end of a successful run.

    By default that means points *this pipeline previously wrote* — they carry an
    `ingest_run`, just an older one. Points with no stamp at all predate the pipeline
    (the live macro_intel1 holds thousands, ingested from sources the crawler cannot
    reach today) and are left alone unless MACRO_PURGE_LEGACY opts in, because
    deleting them would shrink the macro corpus to whatever the crawl can re-fetch.
    """
    from qdrant_client.http import models

    conditions = [models.FieldCondition(key="ingest_run", match=models.MatchValue(value=run_id))]
    if not settings.macro_purge_legacy:
        conditions.append(models.IsEmptyCondition(is_empty=models.PayloadField(key="ingest_run")))
    return models.Filter(must_not=conditions)


def purge_stale(run_id: str, stamped: int, before: int, safe: bool) -> dict:
    """Delete points superseded by this run.

    The rails exist because three of the four configured sources are auth/JS/TLS
    gated: a week where the crawl comes back empty must not be allowed to empty the
    collection. ``safe`` is False when any source errored without yielding a file.
    """
    report = {"ran": False, "deleted": 0, "reason": ""}

    if not settings.macro_purge_stale:
        report["reason"] = "MACRO_PURGE_STALE=false"
        return report
    if not safe:
        report["reason"] = "a source failed this run; keeping existing points"
        return report
    if stamped == 0:
        report["reason"] = "run stamped no points at all"
        return report

    ratio = stamped / before if before else 1.0
    if ratio < settings.macro_purge_min_ratio:
        report["reason"] = (
            f"run stamped {stamped} of {before} pre-existing points "
            f"({ratio:.0%} < MACRO_PURGE_MIN_RATIO {settings.macro_purge_min_ratio:.0%})"
        )
        return report

    from qdrant_client.http import models

    stale = _stale_filter(run_id)
    doomed = client().count(collection_name=collection(), count_filter=stale, exact=True).count
    if doomed:
        client().delete(
            collection_name=collection(),
            points_selector=models.FilterSelector(filter=stale),
            wait=True,
        )
    report["ran"] = True
    report["deleted"] = doomed
    log.info("[purge] removed %d stale point(s) from %s", doomed, collection())
    return report


def _unstamped_filter():
    """Points with no ``ingest_run`` — everything ingested before this pipeline.

    Deliberately NOT scoped to ``module == "macro"``: the points already in
    macro_intel1 were written by an earlier ingest with a different payload schema
    (`content`/`document_name`/`page_number`, no `module` key), so a module-scoped
    filter matches none of them.
    """
    from qdrant_client.http import models

    return models.Filter(
        must=[models.IsEmptyCondition(is_empty=models.PayloadField(key="ingest_run"))]
    )


def count_unstamped() -> int:
    if not client().collection_exists(collection()):
        return 0
    return client().count(
        collection_name=collection(), count_filter=_unstamped_filter(), exact=True
    ).count


def delete_unstamped() -> int:
    """One-time migration: drop legacy macro points that predate the run stamp."""
    from qdrant_client.http import models

    doomed = count_unstamped()
    if doomed:
        client().delete(
            collection_name=collection(),
            points_selector=models.FilterSelector(filter=_unstamped_filter()),
            wait=True,
        )
    return doomed


def stats() -> dict:
    if not client().collection_exists(collection()):
        return {"collection": collection(), "exists": False, "points": 0, "macro_points": 0}
    return {
        "collection": collection(),
        "exists": True,
        "points": total_points(),
        "macro_points": count(),
    }
