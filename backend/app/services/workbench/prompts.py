from __future__ import annotations

import functools

from app.core.tool_names import (
    ASK_CLARIFICATION,
    REFUSE_REQUEST,
    VISUALIZE_RESULT,
)
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.llm.messages import ChatMessage

AGENT_SYSTEM_PROMPT = f"""You are helpful assistant helping bank users understand and analyze their data.

## Instructions
- Ground every answer in evidence from the available tools and the governed schema.
- Use {ASK_CLARIFICATION} for missing or ambiguous information; it ends the turn and waits for a reply.
- Use {REFUSE_REQUEST} to decline a request; it ends the turn without a visual.
- Explain findings through ordinary assistant content. It streams independently of tools; do not repeat text already delivered.
- Use {VISUALIZE_RESULT}(query_id, view) for successful answer query results. Use a table when another chart is unsuitable. It renders all stored rows, including rows omitted from previews, and lets you continue explaining.
- Text-only answers are valid when there are no answer query results to visualize, including empty results and knowledge/web explanations.
- Cite knowledge/web evidence using [source label](#evidence-CARD_REFERENCE), replacing CARD_REFERENCE with the exact card_reference returned by a successful retrieval. Only cite sources used in your explanation.
- Be transparent about uncertainty, missing evidence, and limitations. Never bypass required visualization with prose.

"""


@functools.lru_cache(maxsize=4)
def _agent_gold_schema_for_version(version: str) -> str:
    """Complete, compact Gold schema used as the stable agent prompt prefix.

    The catalog version is the cache key. Column synonyms and repeated prose stay out of this
    projection so the complete physical schema and declared joins leave room for conversation
    history and tool observations in the deployed 32K context.
    """
    cat = get_catalog()
    if cat.version != version:
        raise ValueError(
            f"requested Gold catalog version {version!r}, active version is {cat.version!r}"
        )

    lines = [
        f"GOVERNED GOLD SCHEMA version={cat.version}",
        "Use only the qualified tables, physical columns, and joins declared below. ",
        "All database access must use the PostgreSQL MCP tools supplied with this request.",
        "TABLES AND COLUMNS",
    ]
    join_columns: dict[str, set[str]] = {}
    for join in cat.joins:
        for left, right in join.on:
            join_columns.setdefault(join.left, set()).add(left)
            join_columns.setdefault(join.right, set()).add(right)
    for table in cat.tables.values():
        details = [f"grain={table.grain}", table.description]
        if table.restrictions:
            details.append(f"restriction={table.restrictions}")
        if table.coverage_warning:
            details.append(f"coverage={table.coverage_warning}")
        lines.append(f"- {table.table} | " + " | ".join(details))
        columns = []
        listed: set[str] = set()
        for column in cat.columns_for(table.table):
            listed.add(column.column)
            flags: list[str] = [column.unit]
            if column.is_pii:
                flags.append("pii")
            label = column.label.strip()
            suffix = (
                f"={label}"
                if label and label.lower() != column.column.lower()
                else ""
            )
            columns.append(f"{column.column}{suffix}[{','.join(flags)}]")
        structural = {
            *table.key,
            *table.date_columns.values(),
            *join_columns.get(table.table, set()),
        }
        structural.discard(None)
        if table.as_of_column:
            structural.add(table.as_of_column)
        if table.year_column:
            structural.add(table.year_column)
        columns.extend(
            f"{column}[internal]" for column in sorted(structural - listed)
        )
        lines.append("  columns: " + "; ".join(columns))

    lines.append("DECLARED JOINS")
    for join in cat.joins:
        pairs = ",".join(f"{left}={right}" for left, right in join.on)
        detail = f" | {join.description}" if join.description else ""
        lines.append(
            f"- {join.left} -> {join.right} on {pairs} | {join.cardinality}{detail}"
        )

    lines.append("GOVERNED METRICS")
    for metric in cat.metrics.values():
        lines.append(
            f"- {metric.id} | {metric.formula} | unit={metric.unit} | "
            f"grain={metric.grain} | table={metric.base_table}"
        )

    lines.append("GOVERNED DIMENSIONS")
    for dimension in cat.dimensions.values():
        location = (
            f"{dimension.table}.{dimension.column}"
            if dimension.table and dimension.column
            else "derived"
        )
        lines.append(
            f"- {dimension.id} | {dimension.label} | type={dimension.type} | {location}"
        )

    lines.append("COMPACT FILTER VALUES")
    for block in cat.enums.values():
        values = ",".join(
            f"{code}={value.label}" for code, value in block.values.items()
        )
        lines.append(f"- {block.dimension}: {values}")
    return "\n".join(lines)


def build_agent_gold_schema(catalog: Catalog | None = None) -> str:
    cat = catalog or get_catalog()
    return _agent_gold_schema_for_version(cat.version)


def build_agent_system_prompt(catalog: Catalog | None = None) -> ChatMessage:
    return {
        "role": "system",
        "content": [
            {"type": "text", "text": AGENT_SYSTEM_PROMPT},
            {"type": "text", "text": build_agent_gold_schema(catalog)},
        ],
    }


def warm_agent_gold_schema() -> tuple[str, int]:
    """Build and cache the startup prefix; return version and character count for telemetry."""
    cat = get_catalog()
    block = build_agent_gold_schema(cat)
    return cat.version, len(block)
