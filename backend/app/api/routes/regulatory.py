"""Regulatory intelligence endpoints (Team C) — thin handlers.

`/categories` and `/alerts` are declared before the parametric `/{category_id}`
so those literal paths take precedence.
"""
import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from genesis_core import IntelligenceResponse

from app.services import regulatory
from app.services import reg_loader as rl

router = APIRouter(prefix="/regulatory", tags=["regulatory"])


class NewRegulation(BaseModel):
    display_name: str
    category: str = ""
    rbi_url: str = ""
    applicability: str = ""
    effective_date: str = ""
    priority: Literal["high", "medium", "low"] = "medium"


@router.get("/categories")
def list_categories():
    return regulatory.list_categories()


@router.post("/categories", status_code=201)
def add_category(req: NewRegulation):
    """Config-driven registry: adding a regulation category writes a JSON file."""
    slug = re.sub(r"[^a-z0-9]+", "_", req.display_name.lower()).strip("_")
    if not slug:
        raise HTTPException(400, "Display name must contain letters or digits")
    if rl.load_one(slug):
        raise HTTPException(409, f"Regulation category '{slug}' already exists")
    record = {
        "id": slug,
        "display_name": req.display_name,
        "category": req.category or req.display_name,
        "rbi_url": req.rbi_url,
        "source_doc": "",
        "qdrant_collection": f"reg_{slug}",
        "applicability": req.applicability,
        "effective_date": req.effective_date,
        "priority": req.priority,
    }
    rl.save(record)
    return record


@router.get("/alerts")
def get_alerts():
    return regulatory.get_alerts()


@router.get("/{category_id}", response_model=IntelligenceResponse)
def regulation_detail(category_id: str):
    result = regulatory.detail(category_id)
    if result is None:
        raise HTTPException(404, "Regulation category not found")
    return result
