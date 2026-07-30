"""Dedicated read-only database access for the NLQ pipeline.

Separate credentials and a separate pool from the application role. The privilege set of
`nlq_readonly` — SELECT on `silver.*` and nothing else — is the security boundary; the SQL
validator is defence in depth on top of it. See docs/GENESIS_NLQ_BUILD_PLAN.md §7.1 and
scripts/sql/nlq_readonly_role.sql.

Session guards are re-applied on every checkout rather than trusted from the role's
defaults, because `ALTER ROLE ... SET` sets a *default* that any session can override.
"""

from __future__ import annotations

import contextlib
import logging
import os
import queue
import threading
from typing import Any, Generator

from app.core.config import settings
from app.services.db_schema import _driver as _pg_driver

logger = logging.getLogger(__name__)

POOL_SIZE = 5


class ReadOnlyNotConfigured(RuntimeError):
    """Raised when NLQ_DB_PASSWORD is absent.

    Deliberately fatal rather than falling back to POSTGRES_USER: silently running NLQ as
    the owning role would hand a prompt-injection payload write access to the warehouse.
    """


def _connect_kwargs() -> dict[str, Any]:
    if not settings.nlq_db_password:
        raise ReadOnlyNotConfigured(
            "NLQ_DB_PASSWORD is not set. Create the nlq_readonly role first "
            "(backend/scripts/sql/nlq_readonly_role.sql), then set NLQ_DB_USER/"
            "NLQ_DB_PASSWORD in .env. NLQ will not fall back to the app role."
        )
    host = os.environ.get("POSTGRES_HOST", "192.168.1.183")
    if host.startswith("http://"):
        host = host[7:]
    host = host.rstrip("/")
    kwargs: dict[str, Any] = {
        "host": host,
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "database": os.environ.get("POSTGRES_DB", "moneypaldb"),
        "user": settings.nlq_db_user,
        "password": settings.nlq_db_password,
    }
    # psycopg2 and pg8000 spell the connect timeout differently (mirrors db_schema.py).
    kwargs["connect_timeout" if _pg_driver.__name__.startswith("psycopg2") else "timeout"] = 5
    return kwargs


def _new_connection():
    if _pg_driver is None:
        raise RuntimeError("No PostgreSQL driver available (psycopg2-binary or pg8000).")
    conn = _pg_driver.connect(**_connect_kwargs())
    _apply_session_guards(conn)
    return conn


def _apply_session_guards(conn: Any) -> None:
    cur = conn.cursor()
    try:
        cur.execute(f"SET statement_timeout = {int(settings.nlq_statement_timeout_ms)}")
        cur.execute("SET idle_in_transaction_session_timeout = 10000")
        cur.execute("SET default_transaction_read_only = on")
        cur.execute("SET search_path = silver")  # unqualified names cannot reach bronze/public
        conn.commit()
    finally:
        with contextlib.suppress(Exception):
            cur.close()


class _ReadOnlyPool:
    """Small fixed pool with pre-ping. Volumes are tiny; correctness beats cleverness."""

    def __init__(self, size: int = POOL_SIZE) -> None:
        self._idle: queue.LifoQueue = queue.LifoQueue(maxsize=size)
        self._lock = threading.Lock()
        self._created = 0
        self._size = size

    def acquire(self, timeout: float = 10.0):
        while True:
            try:
                conn = self._idle.get_nowait()
            except queue.Empty:
                with self._lock:
                    if self._created < self._size:
                        self._created += 1
                        break_out = True
                    else:
                        break_out = False
                if break_out:
                    try:
                        return _new_connection()
                    except Exception:
                        with self._lock:
                            self._created -= 1
                        raise
                return self._idle.get(timeout=timeout)  # all in use — wait for a return
            if self._is_alive(conn):
                return conn
            with contextlib.suppress(Exception):
                conn.close()
            with self._lock:
                self._created -= 1

    @staticmethod
    def _is_alive(conn: Any) -> bool:
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            conn.commit()
            return True
        except Exception:
            return False

    def release(self, conn: Any) -> None:
        try:
            conn.rollback()  # never leave a transaction open on a pooled connection
        except Exception:
            with contextlib.suppress(Exception):
                conn.close()
            with self._lock:
                self._created -= 1
            return
        try:
            self._idle.put_nowait(conn)
        except queue.Full:
            with contextlib.suppress(Exception):
                conn.close()
            with self._lock:
                self._created -= 1

    def close_all(self) -> None:
        while True:
            try:
                conn = self._idle.get_nowait()
            except queue.Empty:
                return
            with contextlib.suppress(Exception):
                conn.close()
            with self._lock:
                self._created -= 1


_pool = _ReadOnlyPool()


@contextlib.contextmanager
def readonly_cursor() -> Generator[tuple[Any, Any], None, None]:
    """Yield (connection, cursor) on the read-only pool, always returning the connection."""
    conn = _pool.acquire()
    cur = None
    try:
        cur = conn.cursor()
        yield conn, cur
    finally:
        if cur is not None:
            with contextlib.suppress(Exception):
                cur.close()
        _pool.release(conn)


def health() -> dict[str, Any]:
    """Never raises — `/nlq/health` degrades the UI on this rather than erroring."""
    try:
        with readonly_cursor() as (_conn, cur):
            cur.execute("SELECT current_user, current_setting('statement_timeout')")
            user, timeout = cur.fetchone()
            cur.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'silver'"
            )
            tables = cur.fetchone()[0]
        return {"status": "ok", "role": user, "statement_timeout": timeout, "silver_tables": tables}
    except ReadOnlyNotConfigured as exc:
        return {"status": "unconfigured", "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001 - health must always answer
        logger.warning("NLQ read-only DB health check failed: %s", exc)
        return {"status": "down", "detail": f"{type(exc).__name__}: {exc}"[:200]}


def close_pool() -> None:
    _pool.close_all()
