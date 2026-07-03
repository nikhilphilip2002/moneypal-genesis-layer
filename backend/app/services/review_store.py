"""Intelligence review queue (GICC Administrator).

Every AI-generated intelligence item on the platform can be marked
Pending / Reviewed / Flagged with a reviewer note. Statuses persist in a
small JSON file — no database needed for the buildathon.
"""
import json
from datetime import datetime, timezone

from app.core.config import BASE_DIR
from app.services import institution_loader as il
from app.services import reg_loader as rl

STORE_PATH = BASE_DIR / "registry" / "review_store.json"

# Fixed intelligence items produced by the macro module + dashboard widgets.
STATIC_ITEMS = [
    ("macro:briefing", "AI Executive Brief", "Macro"),
    ("macro:snapshot", "Economic Snapshot", "Macro"),
    ("macro:karnataka", "Karnataka Economy", "Macro"),
    ("macro:msme", "MSME Lending Trends", "Macro"),
    ("competitive:landscape", "Karnataka Lending Landscape", "Competitive"),
]


def _load_store() -> dict:
    if STORE_PATH.exists():
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_store(store: dict) -> None:
    STORE_PATH.write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")


def list_items() -> list[dict]:
    """All reviewable intelligence items, merged with their stored review state."""
    items = [
        {"id": id_, "title": title, "module": module}
        for id_, title, module in STATIC_ITEMS
    ]
    for inst in il.load_all():
        items.append({
            "id": f"competitive:{inst['id']}",
            "title": f"{inst['name']} — profile & SWOT",
            "module": "Competitive",
        })
    for reg in rl.load_all():
        items.append({
            "id": f"regulatory:{reg['id']}",
            "title": reg["display_name"],
            "module": "Regulatory",
        })

    store = _load_store()
    for item in items:
        state = store.get(item["id"], {})
        item["status"] = state.get("status", "pending")
        item["note"] = state.get("note", "")
        item["reviewed_at"] = state.get("reviewed_at")
    return items


def update_item(item_id: str, status: str, note: str) -> dict:
    store = _load_store()
    store[item_id] = {
        "status": status,
        "note": note,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_store(store)
    return {"id": item_id, **store[item_id]}
