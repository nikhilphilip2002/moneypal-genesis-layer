"""Platform administration + cross-collection search (Moneypal Administrator)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import brief_cache, platform
from app.services.db_schema import get_db_schema_graph

router = APIRouter(tags=["admin"])


class SearchRequest(BaseModel):
    query: str


@router.get("/admin/status")
def status():
    return platform.status()


@router.get("/admin/db-schema")
def db_schema(search: str = None):
    """Retrieve the PostgreSQL database relation graph for a specific customer or loan account."""
    return get_db_schema_graph(search_term=search)


@router.post("/intelligence/search")
def search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(400, "Query must not be empty")
    try:
        return {"query": req.query, "results": platform.search(req.query)}
    except Exception:
        raise HTTPException(503, "Semantic search is unavailable — vector store not reachable")


@router.post("/intelligence/ask")
def ask(req: SearchRequest):
    """Ask Genesis: natural-language question -> grounded, cited answer + sources.

    Answers are cached (same question asked twice costs zero LLM tokens)."""
    if not req.query.strip():
        raise HTTPException(400, "Question must not be empty")
    cache_key = "ask:" + " ".join(req.query.lower().split())
    try:
        return brief_cache.cached(cache_key, lambda: platform.ask(req.query))
    except Exception:
        raise HTTPException(503, "Ask Genesis is unavailable — intelligence services not reachable")
