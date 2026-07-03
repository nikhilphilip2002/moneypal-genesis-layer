"""Config-driven institution registry (Team B).

Every institution is one JSON file in backend/registry/institutions/. Adding an
institution = adding a JSON file. No code changes.
"""
import json

from app.core.config import REGISTRY_DIR

INSTITUTIONS_DIR = REGISTRY_DIR / "institutions"


def load_all() -> list[dict]:
    return [
        json.loads(f.read_text(encoding="utf-8"))
        for f in sorted(INSTITUTIONS_DIR.glob("*.json"))
    ]


def load_one(institution_id: str) -> dict | None:
    path = INSTITUTIONS_DIR / f"{institution_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
