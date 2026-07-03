"""Config-driven regulation registry (Team C). One JSON per category in backend/registry/regulations/."""
import json

from app.core.config import REGISTRY_DIR

REGULATIONS_DIR = REGISTRY_DIR / "regulations"


def load_all() -> list[dict]:
    return [
        json.loads(f.read_text(encoding="utf-8"))
        for f in sorted(REGULATIONS_DIR.glob("*.json"))
    ]


def load_one(category_id: str) -> dict | None:
    path = REGULATIONS_DIR / f"{category_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save(regulation: dict) -> None:
    """Persist a new regulation category config."""
    path = REGULATIONS_DIR / f"{regulation['id']}.json"
    path.write_text(json.dumps(regulation, indent=2) + "\n", encoding="utf-8")
