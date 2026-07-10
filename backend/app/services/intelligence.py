"""Dashboard aggregation for the executive landing page.

Two widgets on the leadership dashboard are derived here rather than hardcoded:

* **Recently Updated Intelligence** — driven by the brief cache: whenever a brief
  is (re)generated, its ``generated_at`` moves it to the top of this feed.
* **Action Items** — merges reviewer-flagged intelligence (from the GICC
  Administrator review queue) with high-severity RBI regulatory alerts.
"""
from __future__ import annotations

from app.services import brief_cache, regulatory, review_store
from app.services import institution_loader as il
from app.services import reg_loader as rl

# cache_key prefixes we never surface as "intelligence" on the dashboard.
_EXCLUDED_PREFIXES = ("ask:",)

_MODULE_HREF = {
    "Macro": "/macro",
    "Competitive": "/competitive",
    "Regulatory": "/regulatory",
}


def _resolve(cache_key: str) -> dict | None:
    """Map a brief cache key to a dashboard display item, or None to skip it.

    The stored key still has the ``CACHE_VERSION`` prefix (e.g. ``v2:macro:briefing``).
    """
    _, _, key = cache_key.partition(":")  # drop the version segment
    if not key or any(key.startswith(p) for p in _EXCLUDED_PREFIXES):
        return None

    macro_titles = {
        "macro:briefing": "AI Executive Brief",
        "macro:snapshot": "Economic Snapshot",
        "macro:karnataka": "Karnataka Economy",
        "macro:msme": "MSME Lending Trends",
    }
    if key in macro_titles:
        return {"title": macro_titles[key], "module": "Macro", "href": "/macro"}

    if key == "competitive:landscape":
        return {"title": "Karnataka Lending Landscape", "module": "Competitive", "href": "/competitive"}

    for kind, suffix in (("profile", " — institution profile"), ("swot", " — SWOT analysis")):
        prefix = f"competitive:{kind}:"
        if key.startswith(prefix):
            inst = il.load_one(key[len(prefix):])
            name = inst["name"] if inst else key[len(prefix):]
            return {"title": f"{name}{suffix}", "module": "Competitive", "href": "/competitive"}

    if key.startswith("regulatory:detail:"):
        reg = rl.load_one(key[len("regulatory:detail:"):])
        name = reg["display_name"] if reg else key[len("regulatory:detail:"):]
        return {"title": name, "module": "Regulatory", "href": "/regulatory"}

    return None


def _registry_fallback(limit: int) -> list[dict]:
    """Cold-cache fallback so a fresh demo never shows an empty feed."""
    items: list[dict] = [
        {"title": "MSME Lending Trends", "module": "Macro", "href": "/macro"},
        {"title": "Karnataka Lending Landscape", "module": "Competitive", "href": "/competitive"},
    ]
    for reg in rl.load_all()[:2]:
        items.append({"title": reg["display_name"], "module": "Regulatory", "href": "/regulatory", "last_updated": None})
    for item in items:
        item.setdefault("last_updated", None)
    return items[:limit]


def recent(limit: int = 5) -> list[dict]:
    """Recently updated intelligence, newest first, deduped by title."""
    out: list[dict] = []
    seen: set[str] = set()
    for cache_key, generated_at in brief_cache.recent(limit=limit * 3):
        item = _resolve(cache_key)
        if not item or item["title"] in seen:
            continue
        seen.add(item["title"])
        out.append({**item, "last_updated": generated_at})
        if len(out) >= limit:
            break
    return out or _registry_fallback(limit)


def action_items() -> list[dict]:
    """Reviewer-flagged intelligence + high-severity regulatory alerts."""
    items: list[dict] = []

    for entry in review_store.list_items():
        if entry.get("status") == "flagged":
            items.append({
                "title": entry["title"],
                "detail": entry.get("note") or "Flagged during intelligence review.",
                "priority": "High",
                "href": _MODULE_HREF.get(entry.get("module", ""), "/"),
            })

    for alert in regulatory.regulatory_alerts():
        if alert.severity == "high":
            items.append({
                "title": alert.action_required,
                "detail": alert.category,
                "priority": "High",
                "href": "/regulatory",
            })

    return items
