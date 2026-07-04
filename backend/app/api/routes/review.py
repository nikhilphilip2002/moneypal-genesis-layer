"""Intelligence review queue endpoints (GICC Administrator)."""
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import review_store

router = APIRouter(prefix="/review", tags=["review"])


class ReviewUpdate(BaseModel):
    status: Literal["pending", "reviewed", "flagged"]
    note: str = ""


@router.get("/items")
def list_items():
    return review_store.list_items()


@router.put("/items/{item_id}")
def update_item(item_id: str, req: ReviewUpdate):
    return review_store.update_item(item_id, req.status, req.note)
