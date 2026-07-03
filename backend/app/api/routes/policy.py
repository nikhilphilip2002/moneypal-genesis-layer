"""Policy formulation endpoints (GICC Policy Maker)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from genesis_core import IntelligenceResponse

from app.services import policy

router = APIRouter(prefix="/policy", tags=["policy"])


class PolicyBriefRequest(BaseModel):
    regulation_ids: list[str] = Field(default_factory=list)
    institution_ids: list[str] = Field(default_factory=list)
    focus: str = ""


@router.post("/brief", response_model=IntelligenceResponse)
def brief(req: PolicyBriefRequest):
    if not req.regulation_ids and not req.institution_ids:
        raise HTTPException(400, "Select at least one regulation or institution")
    try:
        result = policy.brief(req.regulation_ids, req.institution_ids, req.focus)
    except Exception:
        raise HTTPException(503, "Policy synthesis is unavailable — intelligence services not reachable")
    if result is None:
        raise HTTPException(404, "No matching regulations or institutions found")
    return result
