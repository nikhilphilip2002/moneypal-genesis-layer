"""Macro-economic intelligence endpoints (Team A) — thin handlers.

Briefs are LLM-generated, so each is served from the SQLite brief cache;
pass ?refresh=1 to force regeneration.
"""
from fastapi import APIRouter

from genesis_core import IntelligenceResponse

from app.services import brief_cache, macro

router = APIRouter(prefix="/macro", tags=["macro"])


@router.get("/snapshot", response_model=IntelligenceResponse)
def snapshot(refresh: bool = False):
    return brief_cache.cached("macro:snapshot", macro.snapshot, refresh)


@router.get("/karnataka", response_model=IntelligenceResponse)
def karnataka(refresh: bool = False):
    return brief_cache.cached("macro:karnataka", macro.karnataka, refresh)


@router.get("/msme", response_model=IntelligenceResponse)
def msme(refresh: bool = False):
    return brief_cache.cached("macro:msme", macro.msme, refresh)


@router.get("/briefing", response_model=IntelligenceResponse)
def briefing(refresh: bool = False):
    return brief_cache.cached("macro:briefing", macro.briefing, refresh)
