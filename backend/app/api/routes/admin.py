"""Platform administration + cross-collection search (Moneypal Administrator)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import platform

router = APIRouter(tags=["admin"])


class SearchRequest(BaseModel):
    query: str


@router.get("/admin/status")
def status():
    return platform.status()


@router.post("/intelligence/search")
def search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(400, "Query must not be empty")
    try:
        return {"query": req.query, "results": platform.search(req.query)}
    except Exception:
        raise HTTPException(503, "Semantic search is unavailable — vector store not reachable")
