"""Platform administration + cross-collection search (Moneypal Administrator)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import brief_cache, platform
from app.services.curiosity_graph import (
    get_curiosity_graph,
    get_customer_360_details,
    search_curiosity_entities,
)
from app.services.db_schema import (
    get_monthly_breakdown,
    get_mom_loan_start_analysis,
)

router = APIRouter(tags=["admin"])


class SearchRequest(BaseModel):
    query: str


@router.get("/admin/status")
def status():
    return platform.status()


@router.get("/admin/db-schema")
def db_schema(
    search: str = None,
    entity_type: str = "all",
    view_level: str = "executive",
    zonal_id: str = None,
    manager_id: str = None,
    agent_id: str = None,
    customer_id: str = None,
    month: str = None,
    level: str = None,
    product_code: str = None,
    branch_code: str = None,
    scheme_code: str = None,
    agent_code: str = None,
    tenure_band: str = None,
    loan_size_bucket: str = None,
    weight_by: str = "borrowers",
    limit: int = 20,
    offset: int = 0,
):
    """Retrieve a Gold-only GICC portfolio hierarchy slice.

    The legacy parameter names remain accepted while old clients roll forward.
    """
    effective_level = level or {
        "executive": "portfolio", "zonal": "product", "manager": "branch",
    }.get(view_level, view_level)
    return get_curiosity_graph(
        level=effective_level,
        product_code=product_code or (zonal_id or "").removeprefix("product:"),
        branch_code=branch_code or (manager_id or "").removeprefix("branch:"),
        scheme_code=scheme_code,
        agent_code=agent_code or (agent_id or "").removeprefix("agent:"),
        tenure_band=tenure_band,
        loan_size_bucket=loan_size_bucket,
        customer_id=customer_id,
        month=month,
        weight_by=weight_by,
        limit=limit,
        offset=offset,
    )


@router.get("/admin/customers/{customer_id}/details")
def customer_details(customer_id: str):
    """Retrieve full 360 customer profile, linked active loans, and repayment history."""
    result = get_customer_360_details(customer_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.get("/admin/monthly-breakdown")
def monthly_breakdown(month: str = None):
    """Retrieve monthly basis aggregates (sanctions, disbursements, repayments, efficiency)."""
    return get_monthly_breakdown(selected_month=month)


@router.get("/admin/mom-loan-analysis")
def mom_loan_analysis():
    """Month-on-month loan start date analysis tracking institution growth and improvement over time."""
    return get_mom_loan_start_analysis()


@router.get("/admin/db-schema/search")
def db_schema_search(q: str = "", entity_type: str = "all"):
    """Instant Gold-layer autocomplete for agents and borrowers."""
    results = search_curiosity_entities(q)
    if entity_type not in ("", "all"):
        results = [row for row in results if row["type"] == entity_type]
    return {"query": q, "entity_type": entity_type, "results": results}


@router.post("/intelligence/search")
def search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(400, "Query must not be empty")
    try:
        return {"query": req.query, "results": platform.search(req.query)}
    except Exception:
        raise HTTPException(503, "Semantic search is unavailable — vector store not reachable")


@router.post("/intelligence/ask")
def ask(req: SearchRequest):
    """Ask Genesis: natural-language question -> grounded, cited answer + sources.

    Answers are cached (same question asked twice costs zero LLM tokens)."""
    if not req.query.strip():
        raise HTTPException(400, "Question must not be empty")
    cache_key = "ask:" + " ".join(req.query.lower().split())
    try:
        return brief_cache.cached(cache_key, lambda: platform.ask(req.query))
    except Exception:
        raise HTTPException(503, "Ask Genesis is unavailable — intelligence services not reachable")
