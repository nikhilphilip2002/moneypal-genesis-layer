"""Platform status for the Moneypal administrator dashboard."""

from genesis_core import rag
from genesis_core.config import settings

from app.core.config import MACRO_COLLECTION
from app.services import institution_loader as il
from app.services import reg_loader as rl

# GICC onboarding journey — Genesis phases from the developer brief (section 9).
ONBOARDING = {
    "client": "GICC",
    "client_url": "https://GICCLtd.com",
    "platform": "Moneypal Genesis Layer",
    "phases": [
        {"name": "Institutional Intelligence", "status": "active",
         "detail": "Macro, competitive and regulatory intelligence via the Aroha RAG framework"},
        {"name": "Prosper & Tally Migration", "status": "upcoming",
         "detail": "Migrate operational data into Canonical Business Objects"},
        {"name": "NEST Platform", "status": "upcoming",
         "detail": "Aggregate Block creation, BI, RIM and DNBS reporting"},
    ],
}


def _all_collections() -> list[tuple[str, str, str]]:
    """(collection, label, module) for every configured intelligence collection."""
    out = [(MACRO_COLLECTION, "Macro-economic Intelligence", "Macro")]
    for inst in il.load_all():
        out.append((inst["qdrant_collection"], inst["name"], "Competitive"))
    for reg in rl.load_all():
        out.append((reg["qdrant_collection"], reg["display_name"], "Regulatory"))
    out.append(("External_customer_details", "External Customer Details", "External Customer"))
    return out


def status() -> dict:
    """Health + registry + vector-store status for the admin panel."""
    collections: list[dict] = []
    qdrant_ok = True
    try:
        client = rag.get_qdrant()
        existing = {c.name for c in client.get_collections().collections}
        for name, label, module in _all_collections():
            count = None
            if name in existing:
                count = client.count(collection_name=name).count
            collections.append({
                "collection": name,
                "label": label,
                "module": module,
                "indexed": name in existing,
                "vectors": count,
            })
    except Exception:
        qdrant_ok = False
        collections = [
            {"collection": name, "label": label, "module": module, "indexed": False, "vectors": None}
            for name, label, module in _all_collections()
        ]

    return {
        "qdrant": {"ok": qdrant_ok, "host": settings.qdrant_host, "port": settings.qdrant_port},
        "llm": {"model": settings.llm_model, "configured": bool(settings.llm_base_url)},
        "embeddings": {"model": settings.embed_model},
        "registries": {"institutions": len(il.load_all()), "regulations": len(rl.load_all())},
        "collections": collections,
        "onboarding": ONBOARDING,
    }
