"""Governed execution boundary for validated native agent calls."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Awaitable, Callable

from app.core.config import settings
from app.services.nlq.catalog import Catalog
from app.services.nlq.executor import QueryResult
from app.services.nlq.llm import NativeToolCall
from app.services.workbench import facts
from app.services.workbench.access import SourceAccessPolicy
from app.services.workbench.agent_contracts import (
    SearchCuratedKnowledgeArguments,
    SearchPublicWebArguments,
    VisualizeQueryResultArguments,
)
from app.services.workbench.agent_tools import (
    authorize_local_tool_call,
    get_runtime_tool_policy,
)
from app.services.workbench.results import Evidence, SourceResult

logger = logging.getLogger(__name__)

_CHART_UNITS = frozenset({
    "inr", "percent", "count", "days", "months", "years", "year", "ratio",
    "text", "date", "datetime", "boolean",
})


def _chart_unit(value: Any, *, numeric: bool) -> str:
    unit = str(value or "").lower()
    return unit if unit in _CHART_UNITS else ("count" if numeric else "text")


class AgentExecutionError(RuntimeError):
    code = "SOURCE_UNAVAILABLE"
    retryable = True


class AgentToolTimeout(AgentExecutionError):
    code = "TOOL_TIMEOUT"


@dataclass(frozen=True, slots=True)
class RawQueryResult:
    """Durable database evidence that is never itself a renderable card."""

    payload: dict[str, Any]
    summary: str
    lineage: dict[str, Any]
    row_count: int
    complete: bool = True
    sensitive: bool = False


@dataclass(frozen=True, slots=True)
class AgentExecutionContext:
    user: str
    role: str
    conversation_id: str
    turn_id: str
    source_policy: SourceAccessPolicy
    deadline_s: float
    question: str = ""
    catalog: Catalog | None = None
    catalog_version: str = ""
    today: date | None = None
    private_entities: tuple[str, ...] = ()
    query_id: str | None = None
    attempt_id: str | None = None
    deadline_started_at: float = field(default_factory=time.monotonic)


@dataclass(slots=True)
class ExecutedAgentCall:
    call: NativeToolCall
    card: SourceResult | None = None
    raw_result: RawQueryResult | None = None
    terminal: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    duration_ms: int = 0
    query_id: str | None = None
    attempt_id: str | None = None

    def replay_payload(self) -> dict[str, Any]:
        query_reference = (
            {"query_id": self.query_id, "attempt_id": self.attempt_id}
            if self.query_id and self.attempt_id else None
        )
        if self.error is not None:
            payload = {"status": "error", **self.error}
            if query_reference is not None:
                payload["query_reference"] = query_reference
            return payload
        if self.terminal is not None:
            return {"status": "terminal", **self.terminal}
        if self.raw_result is not None:
            payload = {
                "status": "ok",
                "source": "db",
                "result_type": "raw_query",
                "payload": self.raw_result.payload,
                "summary": self.raw_result.summary,
                "complete": self.raw_result.complete,
                "lineage": self.raw_result.lineage,
                "row_count": self.raw_result.row_count,
            }
            if query_reference is not None:
                payload["query_reference"] = query_reference
            return payload
        assert self.card is not None
        payload = {
            "status": "ok",
            "source": self.card.source,
            "card_type": self.card.card_type,
            "card_reference": self.call.id,
            "payload": self.card.payload,
            "summary": self.card.summary,
            "complete": self.card.complete,
            "limitation": self.card.limitation,
            "citations": self.card.sources,
            "evidence": self.card.evidence_dicts(),
            "lineage": self.card.lineage,
            "facts": [
                {
                    "id": fact.id,
                    "label": fact.label,
                    "value": str(fact.value),
                    "display_value": fact.display_value,
                    "unit": fact.unit,
                    "period": fact.period,
                    "dimensions": dict(fact.dimensions),
                }
                for fact in facts.from_results([self.card], max_per_result=100)
            ],
        }
        if query_reference is not None:
            payload["query_reference"] = query_reference
        row_count = (self.card.lineage or {}).get("row_count")
        if isinstance(row_count, int):
            payload["row_count"] = row_count
        return payload

    def replay_message(self) -> dict[str, str]:
        """The complete, durable tool result. Never shaped."""
        return {
            "role": "tool",
            "tool_call_id": self.call.id,
            "content": json.dumps(self.replay_payload(), default=str, separators=(",", ":")),
        }

    def observation_message(self) -> dict[str, str]:
        """The bounded tool result the model sees in this and later turns."""
        return {
            "role": "tool",
            "tool_call_id": self.call.id,
            "content": shape_observation_text(
                self.replay_message()["content"], tool_name=self.call.name,
            ),
        }


def observation_limit_chars(tool_name: str | None) -> int:
    """Per-tool observation bound, falling back to the deployment default."""
    limit = settings.workbench_agent_observation_max_chars
    if tool_name:
        try:
            limit = min(limit, get_runtime_tool_policy(tool_name).max_result_chars)
        except Exception:  # noqa: BLE001 - unknown tool names keep the default bound
            logger.debug("no observation bound registered for tool %r", tool_name)
    return limit


def _encoded_size(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, default=str, separators=(",", ":")))


def shape_observation(
    payload: dict[str, Any], *, limit_chars: int, max_facts: int | None = None,
) -> dict[str, Any]:
    """Bound a replay payload for the model without touching the durable copy.

    Reductions are applied in order and each one is recorded under ``truncated`` so the
    model knows what it is not seeing: nested SQL prompts are always dropped, facts are
    capped, then result rows are cut to the largest count that fits, then evidence and
    lineage are dropped, and finally the summary is clipped.
    """
    if max_facts is None:
        max_facts = settings.workbench_agent_observation_max_facts
    shaped: dict[str, Any] = dict(payload)
    truncated: dict[str, Any] = {}
    facts = shaped.get("facts")
    if isinstance(facts, list) and len(facts) > max_facts:
        truncated["facts_omitted"] = len(facts) - max_facts
        shaped["facts"] = facts[:max_facts]
    if truncated:
        shaped["truncated"] = truncated
    if _encoded_size(shaped) <= limit_chars:
        return shaped

    truncated["reason"] = "observation_limit"
    shaped["truncated"] = truncated
    inner = shaped.get("payload")
    if isinstance(inner, dict):
        inner = dict(inner)
        shaped["payload"] = inner
        list_keys = sorted(
            (key for key, value in inner.items() if isinstance(value, list) and value),
            key=lambda key: -len(json.dumps(inner[key], default=str)),
        )
        for key in list_keys:
            items = inner[key]
            low, high = 0, len(items)
            while low < high:
                mid = (low + high + 1) // 2
                inner[key] = items[:mid]
                if _encoded_size(shaped) <= limit_chars:
                    low = mid
                else:
                    high = mid - 1
            inner[key] = items[:low]
            truncated[f"{key}_total"] = len(items)
            truncated[f"{key}_omitted"] = len(items) - low
            if key == "rows":
                truncated["rows_total"] = len(items)
                truncated["rows_omitted"] = len(items) - low
            if _encoded_size(shaped) <= limit_chars:
                return shaped
    dropped: list[str] = []
    for key in ("evidence", "lineage"):
        if key in shaped:
            shaped.pop(key)
            dropped.append(key)
            truncated["dropped"] = list(dropped)
            if _encoded_size(shaped) <= limit_chars:
                return shaped
    summary = shaped.get("summary")
    if isinstance(summary, str) and summary:
        suffix = " [clipped]"
        truncated["summary_clipped"] = True
        excess = _encoded_size(shaped) - limit_chars
        if excess > 0:
            keep = max(0, len(summary) - excess - len(suffix))
            shaped["summary"] = summary[:keep] + suffix
        else:
            del truncated["summary_clipped"]
    return shaped


def shape_observation_text(content: str, *, tool_name: str | None = None) -> str:
    """Shape a serialized tool message; non-JSON content is only cut to the bound."""
    limit = observation_limit_chars(tool_name)
    try:
        parsed = json.loads(content)
    except (TypeError, ValueError):
        return content if len(content) <= limit else content[:limit]
    if not isinstance(parsed, dict):
        return content if len(content) <= limit else content[:limit]
    shaped = shape_observation(parsed, limit_chars=limit)
    return json.dumps(shaped, default=str, separators=(",", ":"))


async def _execute_postgres_mcp(
    call: NativeToolCall, ctx: AgentExecutionContext,
) -> RawQueryResult:
    from app.mcp import postgres_client

    payload = await postgres_client.call_tool(
        call.name,
        call.arguments,
        meta={
            "workbench_user": ctx.user,
            "workbench_role": ctx.role,
            "workbench_conversation_id": ctx.conversation_id,
            "workbench_turn_id": ctx.turn_id,
            "source_policy_version": ctx.source_policy.version,
            "workbench_effective_sources": list(ctx.source_policy.effective_sources),
            "workbench_query_id": ctx.query_id,
            "workbench_attempt_id": ctx.attempt_id,
        },
    )
    returned_query_id = payload.get("query_id")
    returned_attempt_id = payload.get("attempt_id")
    if returned_query_id is not None and str(returned_query_id) != str(ctx.query_id):
        raise AgentExecutionError("PostgreSQL MCP returned a mismatched query identifier")
    if returned_attempt_id is not None and str(returned_attempt_id) != str(ctx.attempt_id):
        raise AgentExecutionError("PostgreSQL MCP returned a mismatched attempt identifier")
    if payload.get("status") == "error":
        message = str(payload.get("message") or "PostgreSQL MCP failed")
        detail = str(payload.get("detail") or "").strip()
        if detail:
            message = f"{message} Detail: {detail}"
        error = AgentExecutionError(message[:1500])
        error.code = str(payload.get("code") or "SOURCE_UNAVAILABLE")
        error.retryable = bool(payload.get("retryable", True))
        raise error

    rows = payload.get("rows")
    columns = payload.get("columns")
    if not isinstance(rows, list) or not isinstance(columns, list):
        raise AgentExecutionError("PostgreSQL MCP returned no tabular query result")
    result = QueryResult(
        rows=[dict(row) for row in rows if isinstance(row, dict)],
        columns=[str(column) for column in columns],
        status=str(payload.get("status") or ("ok" if rows else "empty")),
        duration_ms=int(payload.get("duration_ms") or 0),
        sql=str(payload.get("validated_sql") or ""),
        row_count=int(payload.get("row_count") or len(rows)),
        truncated=bool(payload.get("truncated")),
        plan_cost=payload.get("plan_cost"),
        warnings=[str(item) for item in payload.get("warnings", [])],
    )
    unit_hints = {
        str(key): str(value)
        for key, value in (payload.get("column_units") or {}).items()
    }
    raw_columns = [
        {
            "name": column,
            "label": column.replace("_", " ").title(),
            "unit": _chart_unit(unit_hints.get(column), numeric=any(
                isinstance(row.get(column), (int, float))
                and not isinstance(row.get(column), bool)
                for row in result.rows
            )),
            "sensitivity": "internal",
        }
        for column in result.columns
    ]
    lineage = {
        "path": "postgres_mcp",
        "sql": result.sql,
        "display_sql": result.sql,
        "parameters": {},
        "source_tables": [str(item) for item in payload.get("tables", [])],
        "formulas": {},
        "row_count": result.row_count,
        "duration_ms": result.duration_ms,
        "as_of": None,
        "warnings": result.warnings,
        "unverified": True,
        "requires_signoff": [],
    }
    return RawQueryResult(
        payload={
            "title": (ctx.question or "PostgreSQL query").strip().rstrip("?.!")[:120],
            "columns": raw_columns,
            "rows": result.rows,
            "lineage": lineage,
        },
        summary=f"Query returned {result.row_count:,} row(s).",
        sensitive=bool(payload.get("pii_columns")),
        lineage=lineage,
        row_count=result.row_count,
        complete=not result.truncated,
    )


async def _search_curated(
    args: SearchCuratedKnowledgeArguments, ctx: AgentExecutionContext,
) -> SourceResult:
    from app.services.workbench import nodes

    handlers: dict[str, Callable[[], Awaitable[SourceResult]]] = {
        "concepts": lambda: nodes.run_knowledge(args.query),
        "macro": lambda: nodes.run_macro(args.query, policy=ctx.source_policy),
        "competitive": lambda: nodes.run_competitive(args.query, policy=ctx.source_policy),
        "regulatory": lambda: nodes.run_regulatory(args.query, policy=ctx.source_policy),
    }
    return await handlers[args.domain]()


async def _search_public_web(
    args: SearchPublicWebArguments, ctx: AgentExecutionContext,
) -> SourceResult:
    from app.services.workbench import nodes

    return await nodes.run_web(
        args.search_query, user=ctx.user, policy=ctx.source_policy,
        raise_policy_denials=True,
        private_entities=ctx.private_entities,
    )


async def _visualize_query_result(
    args: VisualizeQueryResultArguments, ctx: AgentExecutionContext,
) -> SourceResult:
    from app.services.workbench import history
    from app.services.workbench.visualization import VisualizationError, build_visual

    source = history.query_result(
        ctx.conversation_id, user=ctx.user, query_id=args.query_id,
    )
    if source is None:
        raise VisualizationError(
            "query_id must reference a successful stored query in this conversation"
        )
    return build_visual(source, args)


def _source_result_from_mcp(data: dict[str, Any]) -> SourceResult:
    card = data.get("card")
    if data.get("kind") != "card" or not isinstance(card, dict):
        raise AgentExecutionError("Workbench MCP tool returned no card")
    raw_evidence = card.get("evidence") or []
    if not isinstance(raw_evidence, list):
        raise AgentExecutionError("Workbench MCP tool returned invalid evidence")
    return SourceResult(
        source=str(card.get("source") or ""),
        card_type=str(card.get("kind") or ""),
        payload=dict(card.get("payload") or {}),
        summary=str(card.get("summary") or ""),
        sources=list(card.get("sources") or []),
        evidence=[Evidence(**item) for item in raw_evidence if isinstance(item, dict)],
        complete=bool(card.get("complete", True)),
        limitation=str(card.get("limitation") or ""),
        sensitive=bool(card.get("sensitive")),
        lineage=(dict(card["lineage"]) if isinstance(card.get("lineage"), dict) else None),
    )


async def execute_agent_call(
    call: NativeToolCall, ctx: AgentExecutionContext,
) -> ExecutedAgentCall:
    """Validate, reauthorize, bound, and execute exactly one native call."""
    from app.mcp import postgres_client

    from app.mcp.tool_catalog import catalog as mcp_catalog

    if mcp_catalog.is_postgres(call.name) or postgres_client.is_model_tool(call.name):
        ctx.source_policy.require("db")
        remaining = ctx.deadline_s - (time.monotonic() - ctx.deadline_started_at)
        try:
            async with asyncio.timeout(max(0.001, remaining)):
                raw_result = await _execute_postgres_mcp(call, ctx)
        except TimeoutError as exc:
            raise AgentToolTimeout(f"{call.name} exceeded its execution deadline") from exc
        return ExecutedAgentCall(
            call=call, raw_result=raw_result,
            query_id=ctx.query_id, attempt_id=ctx.attempt_id,
        )

    authorize_local_tool_call(call.name, call.arguments, policy=ctx.source_policy)
    tool = get_runtime_tool_policy(call.name)
    remaining = ctx.deadline_s - (time.monotonic() - ctx.deadline_started_at)
    timeout = min(tool.timeout_s, max(0.001, remaining))
    try:
        async with asyncio.timeout(timeout):
            from app.mcp import workbench_client

            data = await workbench_client.call_tool(
                call.name,
                call.arguments,
                context=ctx,
            )
    except TimeoutError as exc:
        raise AgentToolTimeout(f"{call.name} exceeded its execution deadline") from exc
    if data.get("kind") == "terminal":
        terminal = data.get("terminal")
        if not isinstance(terminal, dict):
            raise AgentExecutionError("Workbench MCP tool returned an invalid terminal result")
        return ExecutedAgentCall(call=call, terminal=terminal)
    card = _source_result_from_mcp(data)
    if card.card_type == "error":
        return ExecutedAgentCall(
            call=call,
            card=card,
            error={
                "code": str(card.payload.get("code") or "SOURCE_UNAVAILABLE"),
                "message": str(card.payload.get("message") or "Source unavailable.")[:500],
            },
        )
    if card.card_type == "refusal" and card.payload.get("reason") == "not_in_data":
        return ExecutedAgentCall(
            call=call,
            card=card,
            error={
                "code": "NO_MATCHING_ROWS",
                "message": str(card.payload.get("message") or "No matching rows.")[:500],
            },
        )
    return ExecutedAgentCall(call=call, card=card)


__all__ = [
    "AgentExecutionContext",
    "AgentExecutionError",
    "AgentToolTimeout",
    "ExecutedAgentCall",
    "RawQueryResult",
    "execute_agent_call",
]
