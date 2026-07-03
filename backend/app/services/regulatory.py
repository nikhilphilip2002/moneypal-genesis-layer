from datetime import date

from fastapi import HTTPException

from app.models.schema import IntelligenceResponse, RegulatoryAlert, RegulationCategory, Source
from app.registry import get_regulation_category, load_regulation_categories
from app.services.rag import (
    build_context,
    extractive_regulatory_summary,
    generate_with_groq,
    key_points_from_text,
    search_qdrant,
)


DETAIL_QUERY = (
    "For NBFCs below Rs. 500 crore, summarize applicability, business impact, "
    "compliance actions, effective date, operational obligations, board oversight, "
    "customer protection, reporting, governance, outsourcing, KYC, digital lending."
)


def list_categories() -> list[RegulationCategory]:
    return load_regulation_categories()


def regulation_detail(category_id: str) -> IntelligenceResponse:
    try:
        category = get_regulation_category(category_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    hits = search_qdrant(category.qdrant_collection, f"{category.display_name}. {DETAIL_QUERY}", limit=8)
    context = build_context(hits)
    prompt = (
        "Using only the source context below, write a director-level regulatory briefing. "
        "Follow exactly these five markdown section headings: Executive Summary, Applicability, "
        "Business Impact, Compliance Actions, Effective Date. Specifically address NBFCs below "
        f"Rs. 500 crore. Effective date from config: {category.effective_date}.\n\n"
        f"Category: {category.display_name}\n"
        f"Applicability from config: {category.applicability}\n\n"
        f"Source context:\n{context}"
    )
    summary = generate_with_groq(prompt) or extractive_regulatory_summary(
        category.display_name,
        context,
        category.effective_date,
    )

    source_doc = hits[0].get("document") if hits else (category.source_docs[0] if category.source_docs else category.display_name)
    confidence = "high" if hits else "low"
    return IntelligenceResponse(
        title=category.display_name,
        summary=summary,
        key_points=key_points_from_text(summary),
        source=Source(document=source_doc, url=category.rbi_url),
        ai_note=(
            "Summary generated from indexed RBI regulation PDFs. Compliance implications are AI interpretation; "
            "quoted obligations should be verified against the source document."
        ),
        last_updated=date.today().isoformat(),
        confidence=confidence,
    )


def regulatory_alerts() -> list[RegulatoryAlert]:
    categories = {item.id: item for item in load_regulation_categories()}

    def url(category_id: str) -> str:
        category = categories.get(category_id)
        return category.rbi_url if category else "https://www.rbi.org.in/"

    return [
        RegulatoryAlert(
            title="Digital lending controls review",
            category="Digital Lending",
            severity="high",
            summary="Ensure every digital lending journey has clear lender disclosure, consent capture, and customer grievance handling.",
            action_required="Review loan app and partner flows against the digital lending checklist.",
            source_url=url("digital_lending"),
            ai_note="Alert priority is AI interpretation based on the indexed RBI digital lending material.",
        ),
        RegulatoryAlert(
            title="KYC and AML evidence readiness",
            category="KYC / AML",
            severity="high",
            summary="Customer due diligence, periodic updation, and suspicious transaction controls need inspection-ready evidence.",
            action_required="Validate KYC policy, periodic refresh queues, and AML escalation logs.",
            source_url=url("kyc_aml"),
            ai_note="Alert priority is AI interpretation; factual requirements are in the linked RBI source.",
        ),
        RegulatoryAlert(
            title="Outsourcing risk governance",
            category="Outsourcing",
            severity="medium",
            summary="Material outsourced activities need board-approved controls, vendor oversight, and exit planning.",
            action_required="Refresh vendor inventory, risk ratings, SLAs, and exit plans.",
            source_url=url("outsourcing"),
            ai_note="Alert priority is AI interpretation based on RBI outsourcing expectations.",
        ),
        RegulatoryAlert(
            title="Board and governance reporting",
            category="Governance",
            severity="medium",
            summary="Governance directions raise the bar on documented oversight, policy approvals, and risk reporting.",
            action_required="Add regulatory compliance status to the next board or committee pack.",
            source_url=url("governance"),
            ai_note="Alert priority is AI interpretation based on the indexed governance directions.",
        ),
    ]
