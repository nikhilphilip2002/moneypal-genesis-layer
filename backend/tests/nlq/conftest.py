import contextlib
import os

import pytest

from app.core.config import _load_env_file, settings


@pytest.fixture
def anyio_backend():
    """The app runs on asyncio; there is no reason to also exercise trio here."""
    return "asyncio"


def _db_configured() -> bool:
    # Credentials normally live in the repo's .env rather than the process environment,
    # which is how these tests silently skipped the first time they were written.
    return bool(
        os.environ.get("POSTGRES_PASSWORD")
        or _load_env_file().get("POSTGRES_PASSWORD")
        or settings.nlq_db_password
    )


requires_db = pytest.mark.skipif(
    not _db_configured(),
    reason="no database credentials available",
)

requires_readonly_role = pytest.mark.skipif(
    not settings.nlq_db_password,
    reason="nlq_readonly not provisioned — run scripts/sql/nlq_readonly_role.sql",
)


@pytest.fixture(scope="session")
def warehouse_cursor():
    """A cursor for tests that inspect the warehouse itself rather than the NLQ role.

    Catalog introspection and metric fixtures are checking that the *data* matches what the
    catalog claims, which is true regardless of which role reads it. They therefore run on
    the app credential and stay useful before nlq_readonly is provisioned; the read-only
    role has its own dedicated suite in test_readonly_role.py.
    """
    from app.services.db_schema import get_connection

    try:
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"warehouse unreachable: {exc}")

    cur = conn.cursor()
    try:
        yield cur
    finally:
        with contextlib.suppress(Exception):
            conn.rollback()
        with contextlib.suppress(Exception):
            cur.close()
        with contextlib.suppress(Exception):
            conn.close()


@pytest.fixture(autouse=True)
def _rollback_between_tests(request):
    """Postgres aborts the whole transaction on any error, so one bad statement would
    cascade into every later test on the shared session cursor as
    InFailedSqlTransaction — hiding the real failure behind a wall of false ones."""
    yield
    if "warehouse_cursor" in request.fixturenames:
        cursor = request.getfixturevalue("warehouse_cursor")
        with contextlib.suppress(Exception):
            cursor.connection.rollback()


@pytest.fixture
def readonly_via_warehouse(monkeypatch, warehouse_cursor):
    """Point the NLQ executor at the warehouse cursor.

    Lets the full compile -> execute -> chart path be exercised before nlq_readonly exists.
    It deliberately does NOT prove anything about privileges — that is what
    test_readonly_role.py is for, and those tests skip until the role is real.
    """
    import contextlib

    from app.services.nlq import db as nlq_db

    @contextlib.contextmanager
    def _cursor():
        yield warehouse_cursor.connection if hasattr(
            warehouse_cursor, "connection"
        ) else None, warehouse_cursor

    monkeypatch.setattr(nlq_db, "readonly_cursor", _cursor)
    yield
