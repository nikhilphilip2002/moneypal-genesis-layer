"""Competitive intelligence endpoints (Team B) — thin handlers."""
from fastapi import APIRouter, HTTPException

from genesis_core import IntelligenceResponse

from app.services import competitive

router = APIRouter(prefix="/competitive", tags=["competitive"])


@router.get("/institutions")
def list_institutions():
    return competitive.list_institutions()


@router.get("/landscape", response_model=IntelligenceResponse)
def landscape():
    return competitive.landscape()


@router.get("/institutions/{institution_id}", response_model=IntelligenceResponse)
def institution_profile(institution_id: str):
    result = competitive.profile(institution_id)
    if result is None:
        raise HTTPException(404, "Institution not found")
    return result


@router.get("/institutions/{institution_id}/swot")
def institution_swot(institution_id: str):
    result = competitive.swot(institution_id)
    if result is None:
        raise HTTPException(404, "Institution not found")
    return result
