"""Shared filesystem operations for config-driven JSON registries."""
from __future__ import annotations

import json
import re
from pathlib import Path

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def load_all(directory: Path) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def load_one(directory: Path, item_id: str) -> dict | None:
    if not _SAFE_ID.fullmatch(item_id):
        return None
    path = directory / f"{item_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save(directory: Path, item: dict) -> None:
    item_id = str(item.get("id", ""))
    if not _SAFE_ID.fullmatch(item_id):
        raise ValueError("registry id must contain only letters, digits, underscores, or hyphens")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{item_id}.json"
    path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
