"""Regulatory intelligence endpoints (Team C) — thin handlers.

`/categories` and `/alerts` are declared before the parametric `/{category_id}`
so those literal paths take precedence.
"""
from fastapi import APIRouter, HTTPException

from genesis_core import IntelligenceResponse

from app.services import regulatory

router = APIRouter(prefix="/regulatory", tags=["regulatory"])


@router.get("/categories")
def list_categories():
    return regulatory.list_categories()


@router.get("/alerts")
def get_alerts():
    return regulatory.get_alerts()


@router.get("/{category_id}", response_model=IntelligenceResponse)
def regulation_detail(category_id: str):
    result = regulatory.detail(category_id)
    if result is None:
        raise HTTPException(404, "Regulation category not found")
    return result
