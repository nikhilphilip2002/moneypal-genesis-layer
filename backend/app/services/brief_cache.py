"""SQLite cache for LLM-generated briefs.

Generated briefs are expensive (~5-15s of Groq time), rate-limited, and
non-deterministic — an executive dashboard should not change content on every
tab switch. Each brief is cached by key with a TTL; `?refresh=1` on the route
forces regeneration.
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Callable

from fastapi.encoders import jsonable_encoder

from app.core.config import BASE_DIR

DB_PATH = BASE_DIR / "vector_store" / "genesis.db"
DEFAULT_TTL = 12 * 3600  # briefs stay stable for half a day

# Bump when prompt/format changes should invalidate previously generated briefs.
CACHE_VERSION = "v2"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS briefs ("
        "cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL, generated_at REAL NOT NULL)"
    )
    return conn


def get(cache_key: str, ttl: float = DEFAULT_TTL) -> Any | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT payload, generated_at FROM briefs WHERE cache_key = ?", (cache_key,)
        ).fetchone()
    if not row or time.time() - row[1] > ttl:
        return None
    return json.loads(row[0])


def put(cache_key: str, payload: Any) -> Any:
    encoded = jsonable_encoder(payload)
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO briefs (cache_key, payload, generated_at) VALUES (?, ?, ?)",
            (cache_key, json.dumps(encoded, ensure_ascii=False), time.time()),
        )
    return encoded


def cached(
    cache_key: str,
    producer: Callable[[], Any],
    refresh: bool = False,
    ttl: float = DEFAULT_TTL,
) -> Any:
    """Serve the cached brief unless expired or explicitly refreshed."""
    cache_key = f"{CACHE_VERSION}:{cache_key}"
    if not refresh:
        hit = get(cache_key, ttl)
        if hit is not None:
            return hit
    result = producer()
    if result is None:
        return None
    return put(cache_key, result)
