from types import SimpleNamespace

import pytest

from app.core import config
from app.services import db_schema
from app.services.nlq import db as nlq_db


@pytest.fixture
def configured(monkeypatch):
    values = {
        "POSTGRES_HOST": "http://warehouse.example/",
        "POSTGRES_PORT": "5433",
        "POSTGRES_DB": "configured_warehouse",
        "POSTGRES_USER": "app_role",
        "POSTGRES_PASSWORD": "test-app-password",
        "NLQ_DB_USER": "readonly_role",
        "NLQ_DB_PASSWORD": "test-readonly-password",
    }
    for key in values:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config, "_load_env_file", lambda: values)
    return values


def test_both_adapters_use_env_file_target_and_separate_roles(configured, monkeypatch):
    settings = config.Settings()
    monkeypatch.setattr(nlq_db, "settings", settings)
    monkeypatch.setattr(db_schema, "settings", settings)
    readonly = nlq_db._connect_kwargs()
    captured = {}
    def connect(**kwargs):
        captured.update(kwargs)
        return "connection"
    monkeypatch.setattr(db_schema, "_driver", SimpleNamespace(__name__="psycopg2", connect=connect))
    assert db_schema.get_connection() == "connection"
    for kwargs in (readonly, captured):
        assert kwargs["host"] == "warehouse.example"
        assert kwargs["port"] == 5433
        assert kwargs["database"] == "configured_warehouse"
    assert readonly["user"] == "readonly_role"
    assert readonly["password"] == "test-readonly-password"
    assert captured["user"] == "app_role"
    assert captured["password"] == "test-app-password"


def test_process_environment_overrides_env_file(configured, monkeypatch):
    overrides = {
        "POSTGRES_HOST": "override.example", "POSTGRES_PORT": "6543",
        "POSTGRES_DB": "override_warehouse", "POSTGRES_USER": "override_app",
        "POSTGRES_PASSWORD": "override-app-password", "NLQ_DB_USER": "override_readonly",
        "NLQ_DB_PASSWORD": "override-readonly-password",
    }
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    settings = config.Settings()
    monkeypatch.setattr(nlq_db, "settings", settings)
    readonly = nlq_db._connect_kwargs()
    assert (readonly["host"], readonly["port"], readonly["database"]) == ("override.example", 6543, "override_warehouse")
    assert (readonly["user"], readonly["password"]) == ("override_readonly", "override-readonly-password")
    assert (settings.postgres_user, settings.postgres_password) == ("override_app", "override-app-password")


def test_missing_readonly_password_still_rejects_app_role_fallback(configured, monkeypatch):
    configured.pop("NLQ_DB_PASSWORD")
    monkeypatch.setattr(nlq_db, "settings", config.Settings())
    with pytest.raises(nlq_db.ReadOnlyNotConfigured):
        nlq_db._connect_kwargs()
