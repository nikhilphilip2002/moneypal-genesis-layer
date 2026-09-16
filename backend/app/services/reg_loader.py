"""Config-driven regulation registry (Team C). One JSON per category in backend/registry/regulations/."""
from app.core.config import REGISTRY_DIR
from app.services import json_registry

REGULATIONS_DIR = REGISTRY_DIR / "regulations"


def load_all() -> list[dict]:
    return json_registry.load_all(REGULATIONS_DIR)


def load_one(category_id: str) -> dict | None:
    return json_registry.load_one(REGULATIONS_DIR, category_id)


def save(regulation: dict) -> None:
    """Persist a new regulation category config."""
    json_registry.save(REGULATIONS_DIR, regulation)
