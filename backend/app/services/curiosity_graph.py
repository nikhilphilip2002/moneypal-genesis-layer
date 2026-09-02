"""Gold-only portfolio relationship graph.

The graph is a business hierarchy, not a database-schema diagram.  Every amount and
relationship comes from the governed ``gold.semantic_*`` views.  The endpoint deliberately
returns only the selected node and its immediate children so high-cardinality customer and
agent populations remain usable.
"""

from __future__ import annotations

import os
from typing import Any, Iterable

from app.services.db_schema import db_cursor


GICC_ENTITY = os.environ.get("CURIOSITY_GRAPH_ENTITY_NUM", "1").strip() or "1"
GRAPH_LIMIT_MAX = 100
LEVELS = ("portfolio", "product", "branch", "scheme", "agent", "customer")
WEIGHTS = {"borrowers": "borrower_count", "outstanding": "principal_outstanding", "accounts": "account_count"}

# reporting_branch_code is the business-preferred key.  The live Gold audit on 2026-09-02
# found it empty on every loan, while application_branch_code is complete.  Keep the
# preference explicit and the fallback visible in response metadata.
BRANCH_SQL = (
    "COALESCE(NULLIF(BTRIM(l.reporting_branch_code::text), ''), "
    "NULLIF(BTRIM(l.application_branch_code::text), ''), 'UNASSIGNED')"
)

RISK_CTE = """
WITH latest_snapshot_date AS (
    SELECT MAX(snapshot_date) AS snapshot_date
    FROM gold.semantic_portfolio_snapshot
    WHERE entity_num = %s
), latest_risk AS (
    SELECT s.*
    FROM gold.semantic_portfolio_snapshot s
    JOIN latest_snapshot_date d ON d.snapshot_date = s.snapshot_date
    WHERE s.entity_num = %s
)
"""

METRIC_SQL = """
COUNT(*)::bigint AS account_count,
COUNT(*) FILTER (WHERE l.closure_date IS NULL)::bigint AS active_account_count,
COUNT(DISTINCT l.customer_id)::bigint AS borrower_count,
COALESCE(SUM(l.sanction_amount), 0) AS sanctioned_amount,
COALESCE(SUM(l.disbursed_amount), 0) AS disbursed_amount,
COALESCE(SUM(r.principal_outstanding), 0) AS principal_outstanding,
COALESCE(SUM(r.total_overdue), 0) AS total_overdue,
COALESCE(SUM(r.principal_outstanding) FILTER (WHERE r.is_par30), 0) AS par30_outstanding,
COALESCE(SUM(r.principal_outstanding) FILTER (WHERE r.is_npa), 0) AS npa_outstanding,
COUNT(r.loan_account_number)::bigint AS risk_covered_accounts,
MAX(l.data_as_of) AS loan_data_as_of
"""

METRIC_COLUMNS = (
    "account_count", "active_account_count", "borrower_count", "sanctioned_amount",
    "disbursed_amount", "principal_outstanding", "total_overdue", "par30_outstanding",
    "npa_outstanding", "risk_covered_accounts", "loan_data_as_of",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def _money(value: Any) -> float:
    return round(float(value or 0), 2)


def _metrics(values: Iterable[Any]) -> dict[str, Any]:
    row = dict(zip(METRIC_COLUMNS, values))
    outstanding = _money(row["principal_outstanding"])
    accounts = int(row["account_count"] or 0)
    covered = int(row["risk_covered_accounts"] or 0)
    par30 = _money(row["par30_outstanding"])
    npa = _money(row["npa_outstanding"])
    return {
        "account_count": accounts,
        "active_account_count": int(row["active_account_count"] or 0),
        "borrower_count": int(row["borrower_count"] or 0),
        "sanctioned_amount": _money(row["sanctioned_amount"]),
        "disbursed_amount": _money(row["disbursed_amount"]),
        "principal_outstanding": outstanding,
        "total_overdue": _money(row["total_overdue"]),
        "par30_outstanding": par30,
        "par30_ratio": round(par30 / outstanding * 100, 4) if outstanding else 0.0,
        "npa_outstanding": npa,
        "npa_ratio": round(npa / outstanding * 100, 4) if outstanding else 0.0,
        "risk_covered_accounts": covered,
        "risk_coverage_pct": round(covered / accounts * 100, 1) if accounts else 0.0,
        "loan_data_as_of": row["loan_data_as_of"].isoformat() if row["loan_data_as_of"] else None,
    }


def _where(filters: dict[str, str], month: str | None = None) -> tuple[str, list[Any]]:
    clauses = ["l.entity_num = %s"]
    params: list[Any] = [GICC_ENTITY]
    if filters.get("product_code"):
        clauses.append("l.product_code::text = %s")
        params.append(filters["product_code"])
    if filters.get("branch_code"):
        clauses.append(f"{BRANCH_SQL} = %s")
        params.append(filters["branch_code"])
    if filters.get("scheme_code"):
        clauses.append("COALESCE(NULLIF(BTRIM(l.scheme_code::text), ''), 'UNASSIGNED') = %s")
        params.append(filters["scheme_code"])
    if "agent_code" in filters:
        if filters["agent_code"] == "UNASSIGNED":
            clauses.append("NULLIF(BTRIM(l.agent_code::text), '') IS NULL")
        else:
            clauses.append("l.agent_code::text = %s")
            params.append(filters["agent_code"])
    if filters.get("customer_id"):
        clauses.append("l.customer_id::text = %s")
        params.append(filters["customer_id"])
    if month:
        clauses.append("TO_CHAR(l.sanction_date, 'YYYY-MM') = %s")
        params.append(month)
    return " AND ".join(clauses), params


def _aggregate(cur: Any, filters: dict[str, str], month: str | None) -> dict[str, Any]:
    where, params = _where(filters, month)
    cur.execute(
        RISK_CTE + f"""
        SELECT {METRIC_SQL}
        FROM gold.semantic_loan_account l
        LEFT JOIN latest_risk r
          ON r.entity_num = l.entity_num
         AND r.loan_account_number = l.loan_account_number
        WHERE {where}
        """,
        (GICC_ENTITY, GICC_ENTITY, *params),
    )
    return _metrics(cur.fetchone())


def _snapshot_info(cur: Any) -> dict[str, Any]:
    cur.execute(
        "SELECT MAX(snapshot_date), MAX(data_as_of), COUNT(DISTINCT entity_num) "
        "FROM gold.semantic_portfolio_snapshot WHERE entity_num = %s",
        (GICC_ENTITY,),
    )
    snapshot_date, data_as_of, entities = cur.fetchone()
    return {
        "snapshot_date": snapshot_date.isoformat() if snapshot_date else None,
        "snapshot_data_as_of": data_as_of.isoformat() if data_as_of else None,
        "snapshot_entity_count": int(entities or 0),
    }


def _branch_names(cur: Any) -> dict[str, str]:
    cur.execute(
        "SELECT branch_code::text, branch_name FROM gold.semantic_branch "
        "WHERE entity_num = %s AND branch_code IS NOT NULL",
        (GICC_ENTITY,),
    )
    return {_text(code): (_text(name) or f"Branch {code}") for code, name in cur.fetchall()}


def _title(cur: Any, level: str, filters: dict[str, str], branch_names: dict[str, str]) -> str:
    if level == "portfolio":
        return "GICC Loan Book"
    if level == "branch":
        code = filters.get("branch_code", "UNASSIGNED")
        return branch_names.get(code, "Unassigned branch" if code == "UNASSIGNED" else f"Branch {code}")
    where, params = _where(filters, None)
    field = {
        "product": "MAX(NULLIF(BTRIM(l.product_name), ''))",
        "scheme": "MAX(NULLIF(BTRIM(l.scheme_name), ''))",
        "agent": "MAX(NULLIF(BTRIM(l.agent_name), ''))",
        "customer": "MAX(NULLIF(BTRIM(l.customer_name), ''))",
    }[level]
    cur.execute(f"SELECT {field} FROM gold.semantic_loan_account l WHERE {where}", tuple(params))
    label = _text(cur.fetchone()[0])
    code = filters.get(f"{level}_code") or filters.get("customer_id", "")
    return label or (f"Unassigned {level}" if code == "UNASSIGNED" else f"{level.title()} {code}")


def _node(node_id: str, node_type: str, label: str, metrics: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": node_type,
        "label": label,
        "metrics": metrics,
        **extra,
    }


def _children(
    cur: Any,
    child_level: str,
    filters: dict[str, str],
    month: str | None,
    weight_by: str,
    limit: int,
    offset: int,
    branch_names: dict[str, str],
) -> tuple[list[dict[str, Any]], int]:
    where, params = _where(filters, month)
    key_sql, label_sql = {
        "product": ("COALESCE(NULLIF(BTRIM(l.product_code::text), ''), 'UNASSIGNED')", "MAX(NULLIF(BTRIM(l.product_name), ''))"),
        "branch": (BRANCH_SQL, "NULL"),
        "scheme": ("COALESCE(NULLIF(BTRIM(l.scheme_code::text), ''), 'UNASSIGNED')", "MAX(NULLIF(BTRIM(l.scheme_name), ''))"),
        "agent": ("COALESCE(NULLIF(BTRIM(l.agent_code::text), ''), 'UNASSIGNED')", "MAX(NULLIF(BTRIM(l.agent_name), ''))"),
        "customer": ("l.customer_id::text", "MAX(NULLIF(BTRIM(l.customer_name), ''))"),
    }[child_level]
    order_alias = WEIGHTS[weight_by]
    sql = RISK_CTE + f"""
        SELECT {key_sql} AS node_key, {label_sql} AS node_label, {METRIC_SQL},
               COUNT(*) OVER ()::bigint AS total_groups
        FROM gold.semantic_loan_account l
        LEFT JOIN latest_risk r
          ON r.entity_num = l.entity_num
         AND r.loan_account_number = l.loan_account_number
        WHERE {where}
        GROUP BY {key_sql}
        ORDER BY {order_alias} DESC, node_key
        LIMIT %s OFFSET %s
    """
    cur.execute(sql, (GICC_ENTITY, GICC_ENTITY, *params, limit, offset))
    rows = cur.fetchall()
    total_returned = int(rows[0][-1] or 0) if rows else 0
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        code = _text(row[0])
        raw_label = _text(row[1])
        if child_level == "branch":
            label = branch_names.get(code, "Unassigned branch" if code == "UNASSIGNED" else f"Branch {code}")
        else:
            label = raw_label or (f"Unassigned {child_level}" if code == "UNASSIGNED" else f"{child_level.title()} {code}")
        metrics = _metrics(row[2:-1])
        result.append(_node(
            f"{child_level}:{code}", child_level, label, metrics,
            code=code,
            weight_value=metrics[order_alias],
            is_leader=offset + index == 0,
            rank=offset + index + 1,
        ))
    return result, total_returned


def _accounts_and_agents(
    cur: Any,
    customer_id: str,
    selected_agent_code: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    cur.execute(
        RISK_CTE + """
        SELECT l.loan_account_number::text, l.product_code::text, l.product_name,
               l.application_branch_code::text, l.scheme_code::text, l.scheme_name,
               l.agent_code::text, l.agent_name, l.sanction_amount, l.disbursed_amount,
               l.closure_date, l.loan_status, r.principal_outstanding, r.total_overdue,
               r.dpd_days, r.is_par30, r.is_npa
        FROM gold.semantic_loan_account l
        LEFT JOIN latest_risk r
          ON r.entity_num = l.entity_num
         AND r.loan_account_number = l.loan_account_number
        WHERE l.entity_num = %s AND l.customer_id::text = %s
        ORDER BY l.sanction_date DESC NULLS LAST, l.loan_account_number
        """,
        (GICC_ENTITY, GICC_ENTITY, GICC_ENTITY, customer_id),
    )
    rows = cur.fetchall()
    account_nodes: list[dict[str, Any]] = []
    related: dict[str, dict[str, Any]] = {}
    links: list[dict[str, str]] = []
    for row in rows:
        account = _text(row[0])
        agent_code = _text(row[6]) or "UNASSIGNED"
        agent_name = _text(row[7]) or "Unassigned agent"
        account_nodes.append({
            "id": f"account:{account}", "type": "account", "code": account,
            "label": f"Loan {account}",
            "metrics": {
                "account_count": 1, "active_account_count": 1 if row[10] is None else 0,
                "borrower_count": 1,
                "sanctioned_amount": _money(row[8]), "disbursed_amount": _money(row[9]),
                "active": row[10] is None, "loan_status": _text(row[11]),
                "principal_outstanding": _money(row[12]), "total_overdue": _money(row[13]),
                "dpd_days": int(row[14] or 0), "is_par30": bool(row[15]),
                "is_npa": bool(row[16]),
                "par30_ratio": 100.0 if row[15] else 0.0,
                "npa_ratio": 100.0 if row[16] else 0.0,
                "risk_coverage_pct": 100.0 if row[12] is not None else 0.0,
            },
            "product_code": _text(row[1]), "product_name": _text(row[2]),
            "branch_code": _text(row[3]), "scheme_code": _text(row[4]),
            "scheme_name": _text(row[5]), "agent_code": agent_code,
        })
        related.setdefault(agent_code, {
            "id": f"related-agent:{agent_code}", "type": "related_agent", "code": agent_code,
            "label": agent_name, "account_count": 0,
            "is_selected_path": agent_code == selected_agent_code,
        })["account_count"] += 1
        links.append({"source": f"related-agent:{agent_code}", "target": f"account:{account}", "label": "HANDLES"})
    return account_nodes, list(related.values()), links


def get_curiosity_graph(
    *,
    level: str = "portfolio",
    product_code: str | None = None,
    branch_code: str | None = None,
    scheme_code: str | None = None,
    agent_code: str | None = None,
    customer_id: str | None = None,
    month: str | None = None,
    weight_by: str = "borrowers",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Return one navigable Gold hierarchy slice with reconciled contextual KPIs."""
    if level not in LEVELS:
        level = "portfolio"
    if weight_by not in WEIGHTS:
        weight_by = "borrowers"
    limit = max(1, min(int(limit), GRAPH_LIMIT_MAX))
    offset = max(0, int(offset))
    filters = {
        key: _text(value)
        for key, value in {
            "product_code": product_code, "branch_code": branch_code,
            "scheme_code": scheme_code, "agent_code": agent_code,
            "customer_id": customer_id,
        }.items()
        if value is not None and _text(value)
    }

    required = {
        "product": ("product_code",), "branch": ("product_code", "branch_code"),
        "scheme": ("product_code", "branch_code"),
        "agent": ("agent_code",),
        "customer": ("customer_id",),
    }
    if level != "portfolio" and any(not filters.get(field) for field in required[level]):
        level = "portfolio"
        filters = {}

    with db_cursor() as (_conn, cur):
        # These small Gold views have incomplete planner statistics in the current
        # warehouse. PostgreSQL otherwise chooses a nested loop for the latest-snapshot
        # account join (minutes for ~5k rows); the equivalent hash join completes in
        # about a second. This is transaction-local and does not alter server settings.
        cur.execute("SET LOCAL enable_nestloop = off")
        branch_names = _branch_names(cur)
        snapshot = _snapshot_info(cur)
        metric_filters = (
            {"customer_id": filters["customer_id"]}
            if level == "customer" and filters.get("customer_id")
            else filters
        )
        current_metrics = _aggregate(cur, metric_filters, month)
        current_title = _title(cur, level, filters, branch_names)
        current_code = filters.get(f"{level}_code") or filters.get("customer_id") or GICC_ENTITY
        current = _node(f"{level}:{current_code}", level, current_title, current_metrics, code=current_code)
        nodes = [current]
        edges: list[dict[str, str]] = []
        children_total = 0

        next_level = {
            "portfolio": "product", "product": "branch", "branch": "scheme",
            "scheme": "agent", "agent": "customer",
        }.get(level)
        if next_level:
            effective_weight = "outstanding" if next_level == "customer" and weight_by == "borrowers" else weight_by
            children, children_total = _children(
                cur, next_level, filters, month, effective_weight, limit, offset, branch_names,
            )
            nodes.extend(children)
            edges.extend({"source": current["id"], "target": child["id"], "label": f"HAS_{next_level.upper()}"} for child in children)
        elif level == "customer" and filters.get("customer_id"):
            accounts, agents, account_links = _accounts_and_agents(
                cur, filters["customer_id"], filters.get("agent_code"),
            )
            nodes.extend(agents)
            visible_accounts = accounts[offset:offset + limit]
            nodes.extend(visible_accounts)
            edges.extend({"source": agent["id"], "target": current["id"], "label": "SERVES"} for agent in agents)
            visible_account_ids = {node["id"] for node in visible_accounts}
            edges.extend(link for link in account_links if link["target"] in visible_account_ids)
            children_total = len(accounts)

        path = [{"level": "portfolio", "code": GICC_ENTITY, "label": "GICC Loan Book"}]
        for path_level, key in (
            ("product", "product_code"), ("branch", "branch_code"),
            ("scheme", "scheme_code"), ("agent", "agent_code"),
        ):
            if filters.get(key):
                scoped = {k: v for k, v in filters.items() if k != "customer_id"}
                path.append({
                    "level": path_level, "code": filters[key],
                    "label": _title(cur, path_level, scoped, branch_names),
                })
        if filters.get("customer_id"):
            path.append({"level": "customer", "code": filters["customer_id"], "label": current_title})

    return {
        "version": 2,
        "level": level,
        "current": current,
        "nodes": nodes,
        "edges": edges,
        "path": path,
        "kpis": current_metrics,
        "children_total": children_total,
        "visible_children": max(0, len(nodes) - 1),
        "limit": limit,
        "offset": offset,
        "weight_by": weight_by,
        "month": month,
        "coverage": {
            **snapshot,
            "entity_num": GICC_ENTITY,
            "entity_basis": "Entity 1 is the complete GICC Gold loan book with risk and agent coverage.",
            "excluded_entity_note": "Entity 9 is excluded: 44 partial accounts, no agent links, disbursements, or portfolio snapshots.",
            "requested_branch_basis": "reporting_branch_code",
            "effective_branch_basis": "reporting_branch_code with application_branch_code fallback",
            "branch_basis_note": "Reporting branch is currently empty in Gold; application branch supplies the hierarchy until remediation.",
            "source_schema": "gold",
            "source_views": [
                "gold.semantic_loan_account", "gold.semantic_portfolio_snapshot",
                "gold.semantic_branch",
            ],
        },
    }


def search_curiosity_entities(query: str, limit: int = 15) -> list[dict[str, str]]:
    """Search governed hierarchy entities without exposing unrestricted SQL."""
    term = " ".join((query or "").split())
    if len(term) < 2:
        return []
    like = f"%{term.lower()}%"
    results: list[dict[str, str]] = []
    with db_cursor() as (_conn, cur):
        cur.execute(
            """
            SELECT kind, code, label FROM (
                SELECT 'agent' AS kind, agent_code::text AS code, MAX(agent_name) AS label
                FROM gold.semantic_loan_account
                WHERE entity_num = %s AND (LOWER(agent_name) LIKE %s OR LOWER(agent_code::text) LIKE %s)
                GROUP BY agent_code
                UNION ALL
                SELECT 'customer', customer_id::text, MAX(customer_name)
                FROM gold.semantic_loan_account
                WHERE entity_num = %s AND (LOWER(customer_name) LIKE %s OR LOWER(customer_id::text) LIKE %s)
                GROUP BY customer_id
            ) matches
            ORDER BY kind, label NULLS LAST
            LIMIT %s
            """,
            (GICC_ENTITY, like, like, GICC_ENTITY, like, like, min(limit, 50)),
        )
        for kind, code, label in cur.fetchall():
            results.append({"type": kind, "code": _text(code), "label": _text(label) or f"{kind.title()} {code}"})
    return results
