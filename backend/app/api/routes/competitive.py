"""Competitive intelligence endpoints (Team B) — thin handlers."""
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from genesis_core import IntelligenceResponse

from app.services import competitive
from app.services import institution_loader as il

router = APIRouter(prefix="/competitive", tags=["competitive"])


class NewInstitution(BaseModel):
    name: str
    type: str
    website: str = ""
    headquarters: str = ""
    msme_focus: bool = True
    source_urls: dict[str, str] = Field(default_factory=dict)


@router.get("/institutions")
def list_institutions():
    return competitive.list_institutions()


@router.post("/institutions", status_code=201)
def add_institution(req: NewInstitution):
    """Config-driven registry: adding an institution writes a JSON file, no code changes."""
    slug = re.sub(r"[^a-z0-9]+", "_", req.name.lower()).strip("_")
    if not slug:
        raise HTTPException(400, "Institution name must contain letters or digits")
    if il.load_one(slug):
        raise HTTPException(409, f"Institution '{slug}' already exists")
    record = {
        "id": slug,
        "name": req.name,
        "type": req.type,
        "website": req.website,
        "headquarters": req.headquarters,
        "msme_focus": req.msme_focus,
        "confidence": "medium",
        "source_docs": [],
        "source_urls": req.source_urls or ({"website": req.website} if req.website else {}),
        "qdrant_collection": f"comp_{slug}",
    }
    il.save(record)
    return record


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
