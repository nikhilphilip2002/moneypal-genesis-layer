"""Gold-only portfolio relationship graph.

The graph is a business hierarchy, not a database-schema diagram.  Every amount and
relationship comes from the governed ``gold.semantic_*`` views.  The endpoint deliberately
returns only the selected node and its immediate children so high-cardinality customer and
agent populations remain usable.
"""

from __future__ import annotations

import copy
import os
import time
from typing import Any, Iterable

from app.services.db_schema import db_cursor


GICC_ENTITY = os.environ.get("CURIOSITY_GRAPH_ENTITY_NUM", "1").strip() or "1"
GRAPH_LIMIT_MAX = 100
LEVELS = ("portfolio", "product", "branch", "scheme", "agent", "tenure", "loan_size", "customer")
WEIGHTS = {"borrowers": "borrower_count", "outstanding": "principal_outstanding", "accounts": "account_count"}
CACHE_TTL_SECONDS = 120.0

TENURE_BANDS = {
    "tenure_0_12": ("≤ 12 Months", "COALESCE(l.number_of_emis, 0) <= 12"),
    "tenure_13_24": ("13–24 Months", "l.number_of_emis > 12 AND l.number_of_emis <= 24"),
    "tenure_25_36": ("25–36 Months", "l.number_of_emis > 24 AND l.number_of_emis <= 36"),
    "tenure_37_60": ("37–60 Months", "l.number_of_emis > 36 AND l.number_of_emis <= 60"),
    "tenure_60_plus": ("> 60 Months", "l.number_of_emis > 60"),
}

LOAN_SIZE_BUCKETS = {
    "bucket_0_10k": ("0 - 10k", "l.sanction_amount < 10000"),
    "bucket_10k_50k": ("10k - 50k", "l.sanction_amount >= 10000 AND l.sanction_amount < 50000"),
    "bucket_50k_1l": ("50k - 1L", "l.sanction_amount >= 50000 AND l.sanction_amount < 100000"),
    "bucket_1l_2l": ("1L - 2L", "l.sanction_amount >= 100000 AND l.sanction_amount < 200000"),
    "bucket_2l_5l": ("2L - 5L", "l.sanction_amount >= 200000 AND l.sanction_amount < 500000"),
    "bucket_5l_10l": ("5L - 10L", "l.sanction_amount >= 500000 AND l.sanction_amount < 1000000"),
    "bucket_10l_50l": ("10L - 50L", "l.sanction_amount >= 1000000 AND l.sanction_amount < 5000000"),
    "bucket_50l_plus": ("50L+", "l.sanction_amount >= 5000000"),
}

TENURE_KEY_SQL = """CASE
    WHEN COALESCE(l.number_of_emis, 0) <= 12 THEN 'tenure_0_12'
    WHEN l.number_of_emis <= 24 THEN 'tenure_13_24'
    WHEN l.number_of_emis <= 36 THEN 'tenure_25_36'
    WHEN l.number_of_emis <= 60 THEN 'tenure_37_60'
    ELSE 'tenure_60_plus'
END"""

TENURE_LABEL_SQL = """MAX(CASE
    WHEN COALESCE(l.number_of_emis, 0) <= 12 THEN '≤ 12 Months'
    WHEN l.number_of_emis <= 24 THEN '13–24 Months'
    WHEN l.number_of_emis <= 36 THEN '25–36 Months'
    WHEN l.number_of_emis <= 60 THEN '37–60 Months'
    ELSE '> 60 Months'
END)"""

LOAN_SIZE_KEY_SQL = """CASE
    WHEN l.sanction_amount < 10000 THEN 'bucket_0_10k'
    WHEN l.sanction_amount < 50000 THEN 'bucket_10k_50k'
    WHEN l.sanction_amount < 100000 THEN 'bucket_50k_1l'
    WHEN l.sanction_amount < 200000 THEN 'bucket_1l_2l'
    WHEN l.sanction_amount < 500000 THEN 'bucket_2l_5l'
    WHEN l.sanction_amount < 1000000 THEN 'bucket_5l_10l'
    WHEN l.sanction_amount < 5000000 THEN 'bucket_10l_50l'
    ELSE 'bucket_50l_plus'
END"""

LOAN_SIZE_LABEL_SQL = """MAX(CASE
    WHEN l.sanction_amount < 10000 THEN '0 - 10k'
    WHEN l.sanction_amount < 50000 THEN '10k - 50k'
    WHEN l.sanction_amount < 100000 THEN '50k - 1L'
    WHEN l.sanction_amount < 200000 THEN '1L - 2L'
    WHEN l.sanction_amount < 500000 THEN '2L - 5L'
    WHEN l.sanction_amount < 1000000 THEN '5L - 10L'
    WHEN l.sanction_amount < 5000000 THEN '10L - 50L'
    ELSE '50L+'
END)"""


_META_CACHE: dict[str, tuple[Any, float]] = {}
_TITLE_CACHE: dict[str, tuple[str, float]] = {}
_GRAPH_CACHE: dict[tuple, tuple[dict[str, Any], float]] = {}
_SEARCH_CACHE: dict[tuple, tuple[list[dict[str, str]], float]] = {}


def clear_graph_cache() -> None:
    """Clear in-memory metadata, title, search, and query caches."""
    _META_CACHE.clear()
    _TITLE_CACHE.clear()
    _GRAPH_CACHE.clear()
    _SEARCH_CACHE.clear()

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
    if filters.get("tenure_band"):
        band = filters["tenure_band"]
        if band in TENURE_BANDS:
            clauses.append(f"({TENURE_BANDS[band][1]})")
    if filters.get("loan_size_bucket"):
        bucket = filters["loan_size_bucket"]
        if bucket in LOAN_SIZE_BUCKETS:
            clauses.append(f"({LOAN_SIZE_BUCKETS[bucket][1]})")
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
    now = time.time()
    cache_entry = _META_CACHE.get("snapshot_info")
    if cache_entry and now < cache_entry[1]:
        return dict(cache_entry[0])

    cur.execute(
        "SELECT MAX(snapshot_date), MAX(data_as_of), COUNT(DISTINCT entity_num) "
        "FROM gold.semantic_portfolio_snapshot WHERE entity_num = %s",
        (GICC_ENTITY,),
    )
    snapshot_date, data_as_of, entities = cur.fetchone()
    res = {
        "snapshot_date": snapshot_date.isoformat() if snapshot_date else None,
        "snapshot_data_as_of": data_as_of.isoformat() if data_as_of else None,
        "snapshot_entity_count": int(entities or 0),
    }
    _META_CACHE["snapshot_info"] = (res, now + CACHE_TTL_SECONDS)
    return res


def _branch_names(cur: Any) -> dict[str, str]:
    now = time.time()
    cache_entry = _META_CACHE.get("branch_names")
    if cache_entry and now < cache_entry[1]:
        return dict(cache_entry[0])

    cur.execute(
        "SELECT branch_code::text, branch_name FROM gold.semantic_branch "
        "WHERE entity_num = %s AND branch_code IS NOT NULL",
        (GICC_ENTITY,),
    )
    res = {_text(code): (_text(name) or f"Branch {code}") for code, name in cur.fetchall()}
    _META_CACHE["branch_names"] = (res, now + CACHE_TTL_SECONDS)
    return res


def _title(cur: Any, level: str, filters: dict[str, str], branch_names: dict[str, str]) -> str:
    if level == "portfolio":
        return "GICC Loan Book"
    if level == "branch":
        code = filters.get("branch_code", "UNASSIGNED")
        return branch_names.get(code, "Unassigned branch" if code == "UNASSIGNED" else f"Branch {code}")
    if level == "tenure":
        band = filters.get("tenure_band", "")
        return TENURE_BANDS.get(band, (band or "Tenure",))[0]
    if level == "loan_size":
        bucket = filters.get("loan_size_bucket", "")
        return LOAN_SIZE_BUCKETS.get(bucket, (bucket or "Loan Size",))[0]

    code = filters.get(f"{level}_code") or filters.get("customer_id", "")
    cache_key = f"{level}:{code}:{filters.get('product_code', '')}:{filters.get('branch_code', '')}"
    now = time.time()
    cached = _TITLE_CACHE.get(cache_key)
    if cached and now < cached[1]:
        return cached[0]

    where, params = _where(filters, None)
    field = {
        "product": "MAX(NULLIF(BTRIM(l.product_name), ''))",
        "scheme": "MAX(NULLIF(BTRIM(l.scheme_name), ''))",
        "agent": "MAX(NULLIF(BTRIM(l.agent_name), ''))",
        "customer": "MAX(NULLIF(BTRIM(l.customer_name), ''))",
    }[level]
    cur.execute(f"SELECT {field} FROM gold.semantic_loan_account l WHERE {where}", tuple(params))
    label = _text(cur.fetchone()[0])
    title = label or (f"Unassigned {level}" if code == "UNASSIGNED" else f"{level.title()} {code}")
    _TITLE_CACHE[cache_key] = (title, now + CACHE_TTL_SECONDS)
    return title


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
        "tenure": (TENURE_KEY_SQL, TENURE_LABEL_SQL),
        "loan_size": (LOAN_SIZE_KEY_SQL, LOAN_SIZE_LABEL_SQL),
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
        elif child_level == "tenure":
            label = TENURE_BANDS.get(code, (raw_label or code,))[0]
        elif child_level == "loan_size":
            label = LOAN_SIZE_BUCKETS.get(code, (raw_label or code,))[0]
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
    tenure_band: str | None = None,
    loan_size_bucket: str | None = None,
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
            "tenure_band": tenure_band, "loan_size_bucket": loan_size_bucket,
            "customer_id": customer_id,
        }.items()
        if value is not None and _text(value)
    }

    required = {
        "product": ("product_code",), "branch": ("product_code", "branch_code"),
        "scheme": (),
        "agent": ("agent_code",),
        "tenure": ("tenure_band",),
        "loan_size": ("loan_size_bucket",),
        "customer": ("customer_id",),
    }
    is_valid = True
    if level == "scheme":
        if not filters.get("scheme_code") or (not filters.get("branch_code") and not filters.get("agent_code")):
            is_valid = False
    elif level != "portfolio" and any(not filters.get(field) for field in required.get(level, ())):
        is_valid = False

    if not is_valid:
        level = "portfolio"
        filters = {}

    cache_key = (
        level,
        tuple(sorted(filters.items())),
        month or "",
        weight_by,
        limit,
        offset,
    )
    now = time.time()
    cached_graph = _GRAPH_CACHE.get(cache_key)
    if cached_graph and now < cached_graph[1]:
        return copy.deepcopy(cached_graph[0])

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
        current_code = filters.get(f"{level}_code") or filters.get("customer_id") or filters.get("tenure_band") or filters.get("loan_size_bucket") or GICC_ENTITY
        current = _node(f"{level}:{current_code}", level, current_title, current_metrics, code=current_code)
        nodes = [current]
        edges: list[dict[str, str]] = []
        children_total = 0

        if level == "portfolio":
            next_level = "product"
        elif level == "product":
            next_level = "branch"
        elif level == "branch":
            next_level = "scheme"
        elif level == "scheme":
            next_level = "tenure" if filters.get("agent_code") else "agent"
        elif level == "agent":
            next_level = "tenure" if filters.get("scheme_code") else "scheme"
        elif level == "tenure":
            next_level = "loan_size"
        elif level == "loan_size":
            next_level = "customer"
        elif level == "customer":
            next_level = None
        else:
            next_level = None

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
        is_agent_originated = bool(filters.get("agent_code") and not filters.get("branch_code"))
        if is_agent_originated:
            path_keys = (
                ("agent", "agent_code"), ("scheme", "scheme_code"),
                ("tenure", "tenure_band"), ("loan_size", "loan_size_bucket"),
            )
        else:
            path_keys = (
                ("product", "product_code"), ("branch", "branch_code"),
                ("scheme", "scheme_code"), ("agent", "agent_code"),
                ("tenure", "tenure_band"), ("loan_size", "loan_size_bucket"),
            )

        for path_level, key in path_keys:
            if filters.get(key):
                if path_level == level:
                    path_label = current_title
                elif path_level == "branch":
                    path_label = branch_names.get(filters[key], f"Branch {filters[key]}")
                elif path_level == "tenure":
                    path_label = TENURE_BANDS.get(filters[key], (filters[key],))[0]
                elif path_level == "loan_size":
                    path_label = LOAN_SIZE_BUCKETS.get(filters[key], (filters[key],))[0]
                else:
                    scoped = {k: v for k, v in filters.items() if k not in ("customer_id", "tenure_band", "loan_size_bucket")}
                    path_label = _title(cur, path_level, scoped, branch_names)
                path.append({
                    "level": path_level, "code": filters[key],
                    "label": path_label,
                })
        if filters.get("customer_id"):
            path.append({"level": "customer", "code": filters["customer_id"], "label": current_title})

    result = {
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
    if len(_GRAPH_CACHE) > 500:
        _GRAPH_CACHE.clear()
    _GRAPH_CACHE[cache_key] = (result, now + CACHE_TTL_SECONDS)
    return result


def search_curiosity_entities(query: str, limit: int = 15) -> list[dict[str, str]]:
    """Search governed hierarchy entities without exposing unrestricted SQL."""
    term = " ".join((query or "").split())
    if len(term) < 2:
        return []
    cache_key = (term.lower(), min(limit, 50))
    now = time.time()
    cached = _SEARCH_CACHE.get(cache_key)
    if cached and now < cached[1]:
        return [dict(item) for item in cached[0]]

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
    if len(_SEARCH_CACHE) > 300:
        _SEARCH_CACHE.clear()
    _SEARCH_CACHE[cache_key] = (results, now + CACHE_TTL_SECONDS)
    return results


def get_customer_360_details(customer_id: str) -> dict[str, Any]:
    """Retrieve full 360 customer profile, active loans, and complete repayment ledger."""
    clean_id = _text(customer_id)
    if not clean_id:
        return {"error": "Invalid customer ID"}

    with db_cursor() as (_conn, cur):
        cur.execute("SET LOCAL enable_nestloop = off")

        # 1. Profile
        cur.execute(
            """
            SELECT customer_id::text, full_name, mobile_primary, mobile_secondary, email,
                   address_line1, address_line2, landmark, city, district, state, pincode,
                   pan_number, aadhaar_number, kyc_verified_flag, kyc_document_count,
                   yearly_income, monthly_income, occupation_name, occupation_type, risk_rating,
                   home_branch_code::text, home_branch_name
            FROM gold.semantic_customer_profile
            WHERE entity_num = %s AND customer_id::text = %s
            LIMIT 1
            """,
            (GICC_ENTITY, clean_id),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                SELECT customer_id::text, MAX(customer_name)
                FROM gold.semantic_loan_account
                WHERE entity_num = %s AND customer_id::text = %s
                GROUP BY customer_id
                """,
                (GICC_ENTITY, clean_id),
            )
            fallback = cur.fetchone()
            if not fallback:
                return {"error": f"Customer {clean_id} not found"}
            profile = {
                "customer_id": clean_id,
                "full_name": _text(fallback[1]),
                "mobile_primary": None,
                "mobile_secondary": None,
                "email": None,
                "address": "",
                "pan_number": None,
                "aadhaar_masked": None,
                "kyc_verified": False,
                "kyc_document_count": 0,
                "yearly_income": 0.0,
                "monthly_income": 0.0,
                "occupation_name": None,
                "occupation_type": None,
                "risk_rating": "STANDARD",
                "home_branch_code": None,
                "home_branch_name": None,
            }
        else:
            pan = _text(row[12])
            pan_masked = f"{pan[:2]}XXXXX{pan[-2:]}" if len(pan) >= 6 else pan
            aadhaar = _text(row[13])
            aadhaar_masked = f"XXXX-XXXX-{aadhaar[-4:]}" if len(aadhaar) >= 4 else aadhaar
            address_parts = [
                _text(part) for part in [row[5], row[6], row[7], row[8], row[9], row[10], row[11]]
                if _text(part)
            ]
            profile = {
                "customer_id": _text(row[0]),
                "full_name": _text(row[1]),
                "mobile_primary": _text(row[2]) or None,
                "mobile_secondary": _text(row[3]) or None,
                "email": _text(row[4]) or None,
                "address": ", ".join(address_parts),
                "pan_number": pan_masked or None,
                "aadhaar_masked": aadhaar_masked or None,
                "kyc_verified": (_text(row[14]) or "").upper() == "Y",
                "kyc_document_count": int(row[15] or 0),
                "yearly_income": _money(row[16]),
                "monthly_income": _money(row[17]),
                "occupation_name": _text(row[18]) or None,
                "occupation_type": _text(row[19]) or None,
                "risk_rating": _text(row[20]) or "STANDARD",
                "home_branch_code": _text(row[21]) or None,
                "home_branch_name": _text(row[22]) or None,
            }

        # 2. Loans
        cur.execute(
            RISK_CTE + """
            SELECT l.loan_account_number::text, l.product_code::text, l.product_name,
                   l.scheme_code::text, l.scheme_name, l.sanction_date, l.closure_date,
                   l.sanction_amount, l.disbursed_amount, l.principal_repaid, l.interest_repaid,
                   l.interest_rate, l.number_of_emis, l.emi_amount, l.loan_status,
                   l.agent_code::text, l.agent_name,
                   r.principal_outstanding, r.total_overdue, r.dpd_days, r.is_par30, r.is_npa,
                   r.asset_classification
            FROM gold.semantic_loan_account l
            LEFT JOIN latest_risk r
              ON r.entity_num = l.entity_num
             AND r.loan_account_number = l.loan_account_number
            WHERE l.entity_num = %s AND l.customer_id::text = %s
            ORDER BY l.sanction_date DESC NULLS LAST, l.loan_account_number
            """,
            (GICC_ENTITY, GICC_ENTITY, GICC_ENTITY, clean_id),
        )
        loan_rows = cur.fetchall()
        loans: list[dict[str, Any]] = []
        total_sanctioned = 0.0
        total_disbursed = 0.0
        total_outstanding = 0.0
        total_overdue = 0.0
        total_principal_repaid = 0.0
        active_count = 0

        for r in loan_rows:
            is_active = r[6] is None
            if is_active:
                active_count += 1
            sanc = _money(r[7])
            disb = _money(r[8])
            p_rep = _money(r[9])
            outst = _money(r[17])
            od = _money(r[18])
            total_sanctioned += sanc
            total_disbursed += disb
            total_principal_repaid += p_rep
            total_outstanding += outst
            total_overdue += od

            loans.append({
                "loan_account_number": _text(r[0]),
                "product_code": _text(r[1]),
                "product_name": _text(r[2]),
                "scheme_code": _text(r[3]),
                "scheme_name": _text(r[4]),
                "sanction_date": r[5].isoformat() if r[5] else None,
                "closure_date": r[6].isoformat() if r[6] else None,
                "sanction_amount": sanc,
                "disbursed_amount": disb,
                "principal_repaid": p_rep,
                "interest_repaid": _money(r[10]),
                "interest_rate": round(float(r[11] or 0), 2),
                "number_of_emis": int(r[12] or 0),
                "emi_amount": _money(r[13]),
                "loan_status": _text(r[14]),
                "active": is_active,
                "agent_code": _text(r[15]),
                "agent_name": _text(r[16]),
                "principal_outstanding": outst,
                "total_overdue": od,
                "dpd_days": int(r[19] or 0),
                "is_par30": bool(r[20]),
                "is_npa": bool(r[21]),
                "asset_classification": _text(r[22]) or ("NPA" if r[21] else "STANDARD"),
            })

        # 3. Repayment Events
        cur.execute(
            """
            SELECT loan_account_number::text, repayment_sequence, repayment_date,
                   principal_due, interest_due, total_due,
                   principal_paid, interest_paid, total_paid,
                   collection_shortfall, collection_efficiency
            FROM gold.semantic_repayment_event
            WHERE entity_num = %s AND customer_id::text = %s
            ORDER BY repayment_date DESC NULLS LAST, repayment_sequence DESC
            """,
            (GICC_ENTITY, clean_id),
        )
        repayment_rows = cur.fetchall()
        repayments: list[dict[str, Any]] = []
        total_due_sum = 0.0
        total_paid_sum = 0.0

        for rep in repayment_rows:
            t_due = _money(rep[5])
            t_paid = _money(rep[8])
            s_fall = _money(rep[9])
            eff = round(float(rep[10] or 0), 2)
            total_due_sum += t_due
            total_paid_sum += t_paid

            if t_due <= 0:
                status = "PAID"
            elif t_paid >= t_due:
                status = "PAID"
            elif t_paid > 0:
                status = "PARTIAL"
            else:
                status = "MISSED"

            repayments.append({
                "loan_account_number": _text(rep[0]),
                "sequence": int(rep[1] or 0),
                "repayment_date": rep[2].isoformat() if rep[2] else None,
                "principal_due": _money(rep[3]),
                "interest_due": _money(rep[4]),
                "total_due": t_due,
                "principal_paid": _money(rep[6]),
                "interest_paid": _money(rep[7]),
                "total_paid": t_paid,
                "collection_shortfall": s_fall,
                "collection_efficiency": eff,
                "status": status,
            })

        overall_efficiency = round(total_paid_sum / total_due_sum * 100, 2) if total_due_sum > 0 else 100.0

        return {
            "profile": profile,
            "summary": {
                "total_accounts": len(loans),
                "active_accounts": active_count,
                "closed_accounts": len(loans) - active_count,
                "total_sanctioned": round(total_sanctioned, 2),
                "total_disbursed": round(total_disbursed, 2),
                "total_principal_repaid": round(total_principal_repaid, 2),
                "principal_outstanding": round(total_outstanding, 2),
                "total_overdue": round(total_overdue, 2),
                "total_due": round(total_due_sum, 2),
                "total_paid": round(total_paid_sum, 2),
                "overall_collection_efficiency": overall_efficiency,
            },
            "loans": loans,
            "repayment_history": repayments,
        }

