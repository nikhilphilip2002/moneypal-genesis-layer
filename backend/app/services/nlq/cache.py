"""Result and plan caches (§8).

Two caches with different keys and different reasons to exist:

* **Result cache** — key is hash(compiled SQL + data version). The warehouse is snapshot
  data reloaded by ingestion, so between loads the same SQL cannot return different rows;
  the hit rate is high and the answers stay correct by construction. The data version is
  what makes that safe: it is bumped on ingestion, so a reload invalidates everything
  rather than serving yesterday's numbers.

* **Plan cache** — key is the normalised question text. A repeated or demo question skips
  the LLM entirely, which turns a 3-second answer into a 100-millisecond one.

In-process LRU, not Redis. The plan allows either; at this data volume and with one backend
process, adding an infrastructure dependency to cache a 60 ms query would be the wrong
trade. The interface is narrow enough that swapping the storage later touches only this
file.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

RESULT_TTL_S = 900.0    # 15 minutes: a safety net under the data-version key, not the key
PLAN_TTL_S = 3600.0
RESULT_CAPACITY = 256
PLAN_CAPACITY = 512

T = TypeVar("T")


@dataclass(slots=True)
class _Entry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    """Small thread-safe LRU with per-entry expiry."""

    def __init__(self, capacity: int, ttl: float) -> None:
        self._data: OrderedDict[str, _Entry[T]] = OrderedDict()
        self._capacity = capacity
        self._ttl = ttl
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> T | None:
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self.misses += 1
                return None
            if entry.expires_at < now:
                del self._data[key]
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return entry.value

    def put(self, key: str, value: T) -> None:
        with self._lock:
            self._data[key] = _Entry(value, time.monotonic() + self._ttl)
            self._data.move_to_end(key)
            while len(self._data) > self._capacity:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self.hits = self.misses = 0

    def stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "entries": len(self._data),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 3) if total else 0.0,
        }


_results: TTLCache[Any] = TTLCache(RESULT_CAPACITY, RESULT_TTL_S)
_plans: TTLCache[Any] = TTLCache(PLAN_CAPACITY, PLAN_TTL_S)

_data_version = "0"
_version_lock = threading.Lock()


def data_version() -> str:
    return _data_version


def bump_data_version(version: str | None = None) -> str:
    """Invalidate every cached result. Call after ingestion.

    Bumping the version rather than clearing the cache means an in-flight request that
    already holds an old key still completes consistently instead of half-reading a
    cleared cache.
    """
    global _data_version
    with _version_lock:
        _data_version = version or str(int(time.time()))
    logger.info("NLQ result cache invalidated, data version now %s", _data_version)
    return _data_version


def result_key(sql: str, params: Any) -> str:
    payload = f"{_data_version}|{sql}|{params!r}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def get_result(key: str) -> Any | None:
    return _results.get(key)


def put_result(key: str, value: Any) -> None:
    _results.put(key, value)


def cached_result(sql: str, params: Any, compute: Callable[[], T]) -> T:
    key = result_key(sql, params)
    hit = _results.get(key)
    if hit is not None:
        return hit
    value = compute()
    _results.put(key, value)
    return value


_WHITESPACE = re.compile(r"\s+")


def normalise_question(question: str) -> str:
    """Key for the plan cache.

    Case and punctuation are noise — "What is our PAR 30?" and "what is our par 30" are the
    same question. Word order is NOT normalised: "disbursement by branch" and "branch by
    disbursement" mean different things, and collapsing them would serve a wrong plan.
    """
    lowered = question.strip().lower().rstrip("?.!")
    return _WHITESPACE.sub(" ", lowered)


def plan_key(question: str, catalog_version: str) -> str:
    # The catalog version is in the key: a catalog edit changes what a question should
    # plan to, so cached plans from before the edit must not survive it.
    return hashlib.sha256(
        f"{catalog_version}|{normalise_question(question)}".encode()
    ).hexdigest()[:32]


def get_plan(question: str, catalog_version: str) -> Any | None:
    return _plans.get(plan_key(question, catalog_version))


def put_plan(question: str, catalog_version: str, plan: Any) -> None:
    _plans.put(plan_key(question, catalog_version), plan)


def stats() -> dict[str, Any]:
    return {
        "data_version": _data_version,
        "results": _results.stats(),
        "plans": _plans.stats(),
    }


def clear_all() -> None:
    _results.clear()
    _plans.clear()
