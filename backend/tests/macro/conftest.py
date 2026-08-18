"""Fixtures for the macro ingestion suite.

Every test here runs offline. `FakeQdrant` stands in for the real client with an
in-memory point store that understands just enough filter semantics to exercise the
refresh/purge cycle: equality conditions in `must`, negated equality in `must_not`,
and `IsEmpty` for the legacy-migration path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class FakePoint:
    id: str
    vector: list[float]
    payload: dict


@dataclass
class CountResult:
    count: int


def _field_matches(payload: dict, condition: Any) -> bool:
    """True when one condition holds for a payload.

    IsEmptyCondition nests the field name under `is_empty`, unlike FieldCondition
    which carries `key` directly.
    """
    is_empty = getattr(condition, "is_empty", None)
    if is_empty is not None:
        return not payload.get(is_empty.key)
    return payload.get(condition.key) == condition.match.value


def _matches(payload: dict, flt: Any) -> bool:
    if flt is None:
        return True
    for condition in (flt.must or []):
        if not _field_matches(payload, condition):
            return False
    for condition in (flt.must_not or []):
        if _field_matches(payload, condition):
            return False
    return True


@dataclass
class FakeQdrant:
    points: dict[str, FakePoint] = field(default_factory=dict)
    collections: set[str] = field(default_factory=set)
    indexes: list[str] = field(default_factory=list)

    # --- collection management ---
    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def get_collections(self):
        @dataclass
        class _Named:
            name: str

        return type("Result", (), {"collections": [_Named(n) for n in self.collections]})()

    def create_collection(self, collection_name: str, **_) -> None:
        self.collections.add(collection_name)

    def create_payload_index(self, collection_name: str, field_name: str, **_) -> None:
        self.indexes.append(field_name)

    # --- points ---
    def upsert(self, collection_name: str, points: list, **_) -> None:
        for point in points:
            self.points[point.id] = FakePoint(point.id, point.vector, dict(point.payload))

    def set_payload(self, collection_name: str, payload: dict, points: Any, **_) -> None:
        for point in self.points.values():
            if _matches(point.payload, points):
                point.payload.update(payload)

    def delete(self, collection_name: str, points_selector: Any, **_) -> None:
        flt = points_selector.filter
        doomed = [pid for pid, p in self.points.items() if _matches(p.payload, flt)]
        for pid in doomed:
            del self.points[pid]

    def count(self, collection_name: str, count_filter: Any = None, **_) -> CountResult:
        return CountResult(sum(1 for p in self.points.values() if _matches(p.payload, count_filter)))

    # --- helpers for assertions ---
    def payloads(self) -> list[dict]:
        return [p.payload for p in self.points.values()]

    def documents(self) -> set[str]:
        # Legacy points name the file in `document_name`, mirroring the fallback in
        # genesis_core.rag.search.
        return {
            p.payload.get("document") or p.payload.get("document_name")
            for p in self.points.values()
        }


@pytest.fixture
def fake_qdrant(monkeypatch):
    from genesis_core import rag

    from scripts.macro_pipeline import ingestor

    client = FakeQdrant()
    monkeypatch.setattr(ingestor, "client", lambda: client)
    monkeypatch.setattr(rag, "get_qdrant", lambda: client)
    monkeypatch.setattr(rag, "ensure_collection", lambda name: client.collections.add(name))
    return client


@pytest.fixture
def macro_collection(monkeypatch):
    """Point the pipeline at a scratch collection name for the duration of a test."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "macro_collection", "macro_pytest")
    return "macro_pytest"
