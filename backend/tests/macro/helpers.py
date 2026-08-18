"""Helpers for seeding points the pipeline itself would never write."""

from __future__ import annotations

from .conftest import FakePoint


def put_legacy_point(client, document: str) -> str:
    """A point as the pre-pipeline ingest wrote them into macro_intel1.

    Mirrors the real payload shape observed in the live collection: `content` and
    `document_name` rather than `document`, `page_number` as a string, a slug in
    `source`, no `module` key, and crucially no `ingest_run` stamp.
    """
    point_id = f"legacy-{document}"
    client.points[point_id] = FakePoint(
        point_id,
        [0.0, 0.0, 0.0],
        {
            "text": "old",
            "content": "old",
            "document_name": document,
            "source": "mospi",
            "source_url": f"data/mospi/{document}",
            "page_number": "4",
            "category": "GDP",
            "subcategory": "macro",
        },
    )
    return point_id


def put_foreign_point(client, module: str = "regulatory") -> str:
    """A point owned by another module, which the macro purge must never touch."""
    point_id = f"{module}-point"
    client.points[point_id] = FakePoint(
        point_id,
        [0.0, 0.0, 0.0],
        {"module": module, "document": "master_direction.pdf", "text": "not macro"},
    )
    return point_id
