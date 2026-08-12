import re
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from genesis_core import IntelligenceResponse

from app.services import brief_cache, regulatory
from app.services import reg_loader as rl
from app.services import dnbs02_service, dnbs02_lineage, regulatory_reports

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


@router.get("/dnbs02/periods")
def list_dnbs02_periods():
    """Reporting periods the warehouse can actually back with data."""
    return dnbs02_service.get_reportable_periods()


@router.get("/dnbs02")
def get_dnbs02_report(
    frequency: str = "monthly",
    period: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Retrieve RBI DNBS-02 Return metrics for specified date frequency (monthly/quarterly/yearly) or custom date range."""
    try:
        return dnbs02_service.get_dnbs02_report_data(
            frequency=frequency, period=period, start_date=start_date, end_date=end_date
        )
    except dnbs02_service.PeriodError as exc:
        # A period we cannot back with data is a client error, not a reason to invent one.
        raise HTTPException(400, str(exc)) from exc


@router.get("/dnbs02/export")
def export_dnbs02_excel(
    frequency: str = "monthly",
    period: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    format: str = "filing",
):
    """Export the RBI DNBS-02 Return as an Excel workbook (.xlsx).

    `format=lineage` returns the audit companion instead: the same completed template,
    with the source table, columns, filter, derivation and query for every field
    alongside it. It is a separate workbook so the filed return stays untouched.
    """
    if format not in ("filing", "lineage"):
        raise HTTPException(400, f"Unknown format {format!r}; expected 'filing' or 'lineage'.")
    try:
        if format == "lineage":
            excel_bytes = dnbs02_lineage.generate_dnbs02_lineage_excel(
                frequency=frequency, period=period, start_date=start_date, end_date=end_date
            )
        else:
            excel_bytes = dnbs02_service.generate_dnbs02_excel(
                frequency=frequency, period=period, start_date=start_date, end_date=end_date
            )
    except dnbs02_service.PeriodError as exc:
        raise HTTPException(400, str(exc)) from exc
    fn_period = f"{start_date}_to_{end_date}" if (start_date and end_date) else period
    stem = "RBI_DNBS02_Return" if format == "filing" else "RBI_DNBS02_Lineage"
    filename = f"{stem}_{fn_period}_{frequency}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/reports")
def list_report_generators():
    """The five PostgreSQL-backed report outputs available in the DNBS generator."""
    return regulatory_reports.list_reports()


@router.get("/reports/{report_id}/periods")
def list_report_periods(report_id: str):
    try:
        return regulatory_reports.get_periods(report_id)
    except regulatory_reports.ReportError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/reports/{report_id}")
def get_regulatory_report(
    report_id: str,
    frequency: str = "",
    period: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    try:
        return regulatory_reports.get_report_data(
            report_id, frequency, period, start_date, end_date
        )
    except (regulatory_reports.ReportError, dnbs02_service.PeriodError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/reports/{report_id}/export")
def export_regulatory_report(
    report_id: str,
    frequency: str = "",
    period: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    try:
        content = regulatory_reports.generate_report_excel(
            report_id, frequency, period, start_date, end_date
        )
    except (regulatory_reports.ReportError, dnbs02_service.PeriodError) as exc:
        raise HTTPException(400, str(exc)) from exc
    selected_period = (
        f"{start_date}_to_{end_date}" if start_date and end_date else (period or "report")
    )
    safe_period = selected_period.replace("/", "-")
    filename = f"RBI_{report_id.upper()}_{safe_period}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )



@router.get("/{category_id}", response_model=IntelligenceResponse)
def get_regulation_detail(category_id: str, refresh: bool = False):
    return brief_cache.cached(
        f"regulatory:detail:{category_id}", lambda: regulatory.regulation_detail(category_id), refresh
    )
