"""Config-driven institution registry (Team B).

Every institution is one JSON file in backend/registry/institutions/. Adding an
institution = adding a JSON file. No code changes.
"""
from app.core.config import REGISTRY_DIR
from app.services import json_registry

INSTITUTIONS_DIR = REGISTRY_DIR / "institutions"


def load_all() -> list[dict]:
    return json_registry.load_all(INSTITUTIONS_DIR)


def load_one(institution_id: str) -> dict | None:
    return json_registry.load_one(INSTITUTIONS_DIR, institution_id)


def save(institution: dict) -> None:
    """Persist a new institution config. Adding an institution = adding a JSON file."""
    json_registry.save(INSTITUTIONS_DIR, institution)
