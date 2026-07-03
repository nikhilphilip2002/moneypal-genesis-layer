from fastapi import APIRouter

from app.models.schema import IntelligenceResponse, RegulatoryAlert, RegulationCategory
from app.services.regulatory import list_categories, regulation_detail, regulatory_alerts


router = APIRouter()


@router.get("/categories", response_model=list[RegulationCategory])
def get_categories() -> list[RegulationCategory]:
    return list_categories()


@router.get("/alerts", response_model=list[RegulatoryAlert])
def get_alerts() -> list[RegulatoryAlert]:
    return regulatory_alerts()


@router.get("/{category_id}", response_model=IntelligenceResponse)
def get_regulation_detail(category_id: str) -> IntelligenceResponse:
    return regulation_detail(category_id)
