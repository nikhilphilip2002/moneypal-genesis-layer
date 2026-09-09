"""Governed execution boundary for validated native agent calls."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from app.core.config import settings
from app.services.nlq import charts
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.contracts import Lineage
from app.services.nlq.executor import QueryResult
from app.services.nlq.llm import NativeToolCall
from app.services.workbench import facts
from app.services.workbench.access import SourceAccessPolicy
from app.services.workbench.agent_contracts import (
    FinishWithoutDataArguments,
    SearchCuratedKnowledgeArguments,
    SearchPublicWebArguments,
)
from app.services.workbench.agent_tools import get_agent_tool, validate_agent_arguments
from app.services.workbench.results import SourceResult

logger = logging.getLogger(__name__)


class AgentExecutionError(RuntimeError):
    code = "SOURCE_UNAVAILABLE"
    retryable = True


class AgentToolTimeout(AgentExecutionError):
    code = "TOOL_TIMEOUT"


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
    deadline_started_at: float = field(default_factory=time.monotonic)


@dataclass(slots=True)
class ExecutedAgentCall:
    call: NativeToolCall
    card: SourceResult | None = None
    terminal: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def replay_payload(self) -> dict[str, Any]:
        if self.error is not None:
            return {"status": "error", **self.error}
        if self.terminal is not None:
            return {"status": "terminal", **self.terminal}
        assert self.card is not None
        return {
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


_SQL_TRACE_KEYS = (
    "round", "call_purpose", "model", "provider", "candidate_sql", "validated_sql",
    "validation", "error",
)


def observation_limit_chars(tool_name: str | None) -> int:
    """Per-tool observation bound, falling back to the deployment default."""
    limit = settings.workbench_agent_observation_max_chars
    if tool_name:
        try:
            limit = min(limit, get_agent_tool(tool_name).max_result_chars)
        except Exception:  # noqa: BLE001 - unknown tool names keep the default bound
            logger.debug("no observation bound registered for tool %r", tool_name)
    return limit


def _encoded_size(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, default=str, separators=(",", ":")))


def _strip_sql_trace(lineage: Any) -> Any:
    """Keep the SQL decisions of every round, drop the prompts that produced them."""
    if not isinstance(lineage, dict):
        return lineage
    nested = lineage.get("text_to_sql")
    if not isinstance(nested, dict):
        return lineage
    trace = nested.get("trace")
    if not isinstance(trace, list):
        return lineage
    return {
        **lineage,
        "text_to_sql": {
            **nested,
            "trace": [
                {key: item[key] for key in _SQL_TRACE_KEYS if key in item}
                if isinstance(item, dict) else item
                for item in trace
            ],
        },
    }


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
    if "lineage" in shaped:
        shaped["lineage"] = _strip_sql_trace(shaped["lineage"])
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
) -> SourceResult:
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
        },
    )
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
    lineage = Lineage(
        path="text_to_sql",
        sql=result.sql,
        display_sql=result.sql,
        source_tables=[str(item) for item in payload.get("tables", [])],
        row_count=result.row_count,
        duration_ms=result.duration_ms,
        warnings=result.warnings,
        unverified=True,
    )
    chart = charts.build_from_rows(
        question=ctx.question or "PostgreSQL query",
        result=result,
        lineage=lineage,
        catalog=ctx.catalog,
        unit_hints={
            str(key): str(value)
            for key, value in (payload.get("column_units") or {}).items()
        },
        description="Executed through the read-only PostgreSQL MCP server.",
    )
    return SourceResult(
        source="db",
        card_type="chart",
        payload=chart.model_dump(mode="json"),
        summary=chart.summary,
        sensitive=bool(payload.get("pii_columns")),
        lineage=chart.lineage.model_dump(mode="json"),
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


Handler = Callable[[Any, AgentExecutionContext], Awaitable[SourceResult]]
_HANDLERS: dict[str, Handler] = {
    "search_curated_knowledge": _search_curated,
    "search_public_web": _search_public_web,
}


async def execute_agent_call(
    call: NativeToolCall, ctx: AgentExecutionContext,
) -> ExecutedAgentCall:
    """Validate, reauthorize, bound, and execute exactly one native call."""
    from app.mcp import postgres_client

    if postgres_client.is_model_tool(call.name):
        ctx.source_policy.require("db")
        remaining = ctx.deadline_s - (time.monotonic() - ctx.deadline_started_at)
        try:
            async with asyncio.timeout(max(0.001, remaining)):
                card = await _execute_postgres_mcp(call, ctx)
        except TimeoutError as exc:
            raise AgentToolTimeout(f"{call.name} exceeded its execution deadline") from exc
        return ExecutedAgentCall(call=call, card=card)

    catalog = ctx.catalog or get_catalog()
    parsed: BaseModel = validate_agent_arguments(
        call.name, call.arguments, policy=ctx.source_policy, catalog=catalog,
    )
    if isinstance(parsed, FinishWithoutDataArguments):
        return ExecutedAgentCall(
            call=call,
            terminal=parsed.model_dump(mode="json"),
        )

    tool = get_agent_tool(call.name)
    handler = _HANDLERS[tool.handler_key]
    remaining = ctx.deadline_s - (time.monotonic() - ctx.deadline_started_at)
    timeout = min(tool.timeout_s, max(0.001, remaining))
    try:
        async with asyncio.timeout(timeout):
            card = await handler(parsed, ctx)
    except TimeoutError as exc:
        raise AgentToolTimeout(f"{call.name} exceeded its execution deadline") from exc
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
    "execute_agent_call",
]
