"""Config-driven institution registry.

Every institution is one JSON file in ./institutions/. Adding an institution =
adding a JSON file. No code changes. This satisfies the brief's "add institutions
without software changes" requirement.
"""
import json
import os
from pathlib import Path

INSTITUTIONS_DIR = os.path.join(os.path.dirname(__file__), "institutions")


def load_all() -> list[dict]:
    out = []
    for f in sorted(Path(INSTITUTIONS_DIR).glob("*.json")):
        out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def load_one(institution_id: str) -> dict | None:
    path = Path(INSTITUTIONS_DIR) / f"{institution_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
