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
from typing import Any, Awaitable, Callable

from app.services.workbench.nodes import SourceResult


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
    handler: Callable[[dict], Awaitable[SourceResult]]
    roles: frozenset[str] | None = None  # None = every role
    params: dict[str, Any] = field(default_factory=dict)  # JSON-schema-ish for the "+" form

    def visible_to(self, role: str) -> bool:
        return self.roles is None or role in self.roles


# --- handlers ---------------------------------------------------------------------------
# Thin wrappers over the source nodes, so a tool and the equivalent typed question can never
# drift. Referencing `nodes.run_*` at call time keeps them monkeypatchable in tests.

async def _show_schema(params: dict) -> SourceResult:
    from app.services.workbench import nodes

    return await nodes.run_schema(params.get("search", "") or "")


async def _competitor_landscape(params: dict) -> SourceResult:
    from app.services.workbench import nodes

    return await nodes.run_competitive("competitive landscape")


TOOLS: dict[str, Tool] = {
    "show_schema": Tool(
        id="show_schema",
        label="Show data schema",
        description="Render the loan-book schema: tables and how they relate.",
        kind="card",
        handler=_show_schema,
        roles=frozenset({"admin", "gicc_admin", "gicc_director"}),
        params={"search": {"type": "string", "label": "Focus (optional)", "required": False}},
    ),
    "competitor_landscape": Tool(
        id="competitor_landscape",
        label="Competitor landscape",
        description="Pull the current Karnataka MSME lending landscape brief.",
        kind="card",
        handler=_competitor_landscape,
        roles=frozenset({"admin", "gicc_admin", "gicc_policy"}),
    ),
}


def visible_tools(role: str) -> list[Tool]:
    return [t for t in TOOLS.values() if t.visible_to(role)]


def get_tool(tool_id: str) -> Tool | None:
    return TOOLS.get(tool_id)


async def run_tool(tool_id: str, *, role: str, params: dict | None = None) -> SourceResult:
    """Run a tool, enforcing role access. Raises ToolNotFound / ToolAccessError."""
    tool = get_tool(tool_id)
    if tool is None:
        raise ToolNotFound(tool_id)
    if not tool.visible_to(role):
        raise ToolAccessError(tool_id)
    return await tool.handler(params or {})
