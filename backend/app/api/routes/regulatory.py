import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from genesis_core import IntelligenceResponse

from app.services import brief_cache, regulatory
from app.services import reg_loader as rl
from app.services import dnbs02_service

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
        "source_docs": ["*.pdf"],
        "qdrant_collection": f"reg_{slug}",
        "applicability": req.applicability,
        "effective_date": req.effective_date,
        "priority": req.priority,
    }
    rl.save(record)
    return record


@router.get("/alerts")
def get_alerts():
    return regulatory.regulatory_alerts()


@router.get("/dnbs02")
def get_dnbs02_report(frequency: str = "monthly", period: str = "2026-05"):
    """Retrieve RBI DNBS-02 Return metrics for specified date frequency (monthly/quarterly/yearly) and period."""
    return dnbs02_service.get_dnbs02_report_data(frequency=frequency, period=period)


@router.get("/dnbs02/export")
def export_dnbs02_excel(frequency: str = "monthly", period: str = "2026-05"):
    """Export RBI DNBS-02 Return as an Excel workbook (.xlsx)."""
    excel_bytes = dnbs02_service.generate_dnbs02_excel(frequency=frequency, period=period)
    filename = f"RBI_DNBS02_Return_{period}_{frequency}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{category_id}", response_model=IntelligenceResponse)
def get_regulation_detail(category_id: str, refresh: bool = False):
    return brief_cache.cached(
        f"regulatory:detail:{category_id}", lambda: regulatory.regulation_detail(category_id), refresh
    )

