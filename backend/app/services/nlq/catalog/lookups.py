"""Enum values that live in a table rather than in YAML.

Dynamic labels are supported only when an active governed catalog explicitly declares a
lookup. The Gold catalog currently uses reviewed static dictionaries and deliberately
declares no raw-Silver lookup.

Cached for the process lifetime and keyed by catalog version, so a catalog edit cannot
leave a stale label behind.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.services.nlq.catalog.loader import Catalog, EnumBlock

logger = logging.getLogger(__name__)

_cache: dict[str, dict[str, str]] = {}
_lock = threading.Lock()


def dynamic_labels(catalog: Catalog, dimension_id: str) -> dict[str, str]:
    """Code -> label for a dimension whose enum block declares a `lookup` table.

    Returns {} on any failure: a missing label degrades to the bare code, which is a
    cosmetic loss. Raising here would take out an otherwise correct answer.
    """
    enum = catalog.enums.get(dimension_id)
    if enum is None or not enum.lookup:
        return {}

    key = f"{catalog.version}:{dimension_id}"
    with _lock:
        if key in _cache:
            return _cache[key]

    labels = _fetch(enum)
    with _lock:
        _cache[key] = labels
    return labels


def _fetch(enum: EnumBlock) -> dict[str, str]:
    from app.services.nlq import db as nlq_db

    table = enum.lookup.get("table")
    code_column = enum.lookup.get("code_column")
    label_column = enum.lookup.get("label_column")
    if not (table and code_column and label_column):
        return {}

    # Identifiers come from the catalog, never from user input, so they cannot be attacker
    # controlled — but they are still whitelisted against the catalog's own table list by
    # the caller before reaching here.
    sql = (
        f'SELECT DISTINCT "{code_column}", "{label_column}" FROM {table} '
        f'WHERE "{label_column}" IS NOT NULL'
    )
    try:
        with nlq_db.readonly_cursor() as (conn, cur):
            cur.execute(sql)
            rows = cur.fetchall()
            conn.rollback()
    except Exception as exc:  # noqa: BLE001 - cosmetic labels must not break an answer
        logger.warning("NLQ dynamic label lookup failed for %s: %s", enum.dimension, exc)
        return {}

    return {
        str(code).strip(): _titlecase(str(label).strip())
        for code, label in rows
        if code is not None and str(label or "").strip()
    }


def _titlecase(value: str) -> str:
    """The scheme master mixes 'Purchase of Site' with 'PURCHASE OF TWO WHEELERS'.

    Shouted names are title-cased so a chart axis reads consistently; names that already
    have mixed case are left exactly as the client wrote them.
    """
    if value.isupper():
        return " ".join(value.title().replace("/", " / ").split())
    return value


def label_for(catalog: Catalog, dimension_id: str, code: Any) -> str:
    """Resolve one code: YAML first (curated, authoritative), then the live table."""
    enum = catalog.enums.get(dimension_id)
    if enum is None:
        return str(code)
    key = str(code).strip()
    if key in enum.values:
        return enum.values[key].label
    dynamic = dynamic_labels(catalog, dimension_id).get(key)
    if dynamic:
        return dynamic
    return enum.fallback_label.replace("{code}", key)


def clear_cache() -> None:
    with _lock:
        _cache.clear()
