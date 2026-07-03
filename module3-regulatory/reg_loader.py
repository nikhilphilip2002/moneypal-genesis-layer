"""Config-driven regulation registry. One JSON per category in ./regulations/."""
import json
import os
from pathlib import Path

REGULATIONS_DIR = os.path.join(os.path.dirname(__file__), "regulations")


def load_all() -> list[dict]:
    out = []
    for f in sorted(Path(REGULATIONS_DIR).glob("*.json")):
        out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def load_one(category_id: str) -> dict | None:
    path = Path(REGULATIONS_DIR) / f"{category_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
