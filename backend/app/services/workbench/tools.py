"""The tool registry — the "+" menu's backend.

Tools are actions that are not a typed question: run a report, pull a fixed brief, export.
They are declared here as data, so the "+" menu is generated from the registry and a new
action is one entry, never a UI change.

Access is enforced in `run_tool`, not just hidden in the menu. Hiding a tool a role may not
use is a UX nicety; refusing to *run* it is the actual boundary, because the endpoint can be
called directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from app.services.workbench.nodes import SourceResult

if TYPE_CHECKING:
    from app.services.workbench.access import SourceAccessPolicy


class ToolError(RuntimeError):
    """Base for tool dispatch failures."""


class ToolNotFound(ToolError):
    pass


class ToolAccessError(ToolError):
    """The role may not run this tool."""


@dataclass(frozen=True, slots=True)
class Tool:
    id: str
    label: str
    description: str
    kind: str  # "card" — renders inline like a source card
    handler: Callable[[dict, "SourceAccessPolicy"], Awaitable[SourceResult]]
    source_id: str
    roles: frozenset[str] | None = None  # None = every role
    params: dict[str, Any] = field(default_factory=dict)  # JSON-schema-ish for the "+" form

    def visible_to(self, role: str) -> bool:
        return self.roles is None or role in self.roles


# --- handlers ---------------------------------------------------------------------------
# Thin wrappers over the source nodes, so a tool and the equivalent typed question can never
# drift. Referencing `nodes.run_*` at call time keeps them monkeypatchable in tests.

async def _show_schema(params: dict, _policy: "SourceAccessPolicy") -> SourceResult:
    from app.services.workbench import nodes

    return await nodes.run_schema(params.get("search", "") or "")


async def _competitor_landscape(params: dict, policy: "SourceAccessPolicy") -> SourceResult:
    from app.services.workbench import nodes

    return await nodes.run_competitive("competitive landscape", policy=policy)


async def _macro_brief(params: dict, policy: "SourceAccessPolicy") -> SourceResult:
    from app.services.workbench import nodes

    return await nodes.run_macro(
        "India and Karnataka macroeconomic outlook, MSME credit conditions, and interest rates",
        policy=policy,
    )


async def _regulatory_alerts(params: dict, policy: "SourceAccessPolicy") -> SourceResult:
    from app.services.workbench import nodes

    return await nodes.run_regulatory(
        "latest RBI regulatory guidelines, prudential norms, and MSME circulars",
        policy=policy,
    )


TOOLS: dict[str, Tool] = {
    "show_schema": Tool(
        id="show_schema",
        label="Show data schema",
        description="Render the loan-book schema: tables and how they relate.",
        kind="card",
        handler=_show_schema,
        source_id="schema",
        roles=frozenset({"admin", "gicc_admin", "gicc_director"}),
        params={"search": {"type": "string", "label": "Focus (optional)", "required": False}},
    ),
    "competitor_landscape": Tool(
        id="competitor_landscape",
        label="Competitor landscape",
        description="Pull the current Karnataka MSME lending landscape brief.",
        kind="card",
        handler=_competitor_landscape,
        source_id="competitive",
        roles=frozenset({"admin", "gicc_admin", "gicc_policy"}),
    ),
    "macro_brief": Tool(
        id="macro_brief",
        label="Macroeconomic brief",
        description="Fetch latest macroeconomic indicators and MSME credit conditions.",
        kind="card",
        handler=_macro_brief,
        source_id="macro",
        roles=None,
    ),
    "regulatory_alerts": Tool(
        id="regulatory_alerts",
        label="Regulatory compliance brief",
        description="Pull recent RBI circulars, MSME guidelines, and prudential norms.",
        kind="card",
        handler=_regulatory_alerts,
        source_id="regulatory",
        roles=frozenset({"admin", "gicc_admin", "gicc_policy"}),
    ),
}


def visible_tools(role: str) -> list[Tool]:
    return [t for t in TOOLS.values() if t.visible_to(role)]


def get_tool(tool_id: str) -> Tool | None:
    return TOOLS.get(tool_id)


async def run_tool(
    tool_id: str, *, role: str, params: dict | None = None,
    external_sources_enabled: bool = False,
) -> SourceResult:
    """Run a tool, enforcing role access. Raises ToolNotFound / ToolAccessError."""
    import time
    from app.core.logging import log_parsed_output

    tool = get_tool(tool_id)
    if tool is None:
        log_parsed_output(
            f"Tool not found: {tool_id}",
            event="tool_call",
            tool_name=tool_id,
            tool_args=params or {},
            status="error",
            error=f"ToolNotFound: {tool_id}",
        )
        raise ToolNotFound(tool_id)
    from app.services.workbench.access import build_policy

    policy = build_policy(role=role, external_sources_enabled=external_sources_enabled)
    if not tool.visible_to(role) or not policy.allows(tool.source_id):
        log_parsed_output(
            f"Tool access denied: {tool_id}",
            event="tool_call",
            tool_name=tool_id,
            status="denied",
            error=f"ToolAccessError for role {role}",
        )
        raise ToolAccessError(tool_id)

    t0 = time.perf_counter()
    try:
        result = await tool.handler(params or {}, policy)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        log_parsed_output(
            f"Tool {tool_id} executed successfully",
            event="tool_call",
            tool_name=tool_id,
            tool_args=params or {},
            tool_result={"kind": getattr(result, "kind", ""), "item_count": len(getattr(result, "items", []) or [])},
            duration_ms=duration_ms,
            status="success",
        )
        return result
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000.0
        log_parsed_output(
            f"Tool {tool_id} execution failed: {exc}",
            event="tool_call",
            tool_name=tool_id,
            tool_args=params or {},
            duration_ms=duration_ms,
            status="error",
            error=str(exc),
        )
        raise
