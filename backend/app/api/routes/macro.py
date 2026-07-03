"""Macro-economic intelligence endpoints (Team A) — thin handlers."""
from fastapi import APIRouter

from genesis_core import IntelligenceResponse

from app.services import macro

router = APIRouter(prefix="/macro", tags=["macro"])


@router.get("/snapshot", response_model=IntelligenceResponse)
def snapshot():
    return macro.snapshot()


@router.get("/karnataka", response_model=IntelligenceResponse)
def karnataka():
    return macro.karnataka()


@router.get("/msme", response_model=IntelligenceResponse)
def msme():
    return macro.msme()


@router.get("/briefing", response_model=IntelligenceResponse)
def briefing():
    return macro.briefing()
