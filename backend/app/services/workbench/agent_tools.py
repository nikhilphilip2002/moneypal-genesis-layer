"""Runtime policy and defense-in-depth validation for Workbench tools.

This registry is deliberately separate from ``workbench.tools``, which backs the UI's quick
actions. FastMCP owns model-visible contracts and handlers; this module owns orchestration
policy and the validation that must succeed before the executor dispatches a call.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.services.nlq.catalog import Catalog
from app.services.workbench.access import SourceAccessDenied, SourceAccessPolicy, source_group
from app.services.workbench.agent_contracts import (
    FinishWithoutDataArguments,
    FinalSynthesis,
    SearchCuratedKnowledgeArguments,
    SearchPublicWebArguments,
    VisualizeQueryResultArguments,
)


class AgentToolError(ValueError):
    """Base for registry and argument failures safe to classify at orchestration level."""


class AgentToolNotFound(AgentToolError):
    code = "INVALID_TOOL_ARGUMENTS"


class AgentToolArgumentsInvalid(AgentToolError):
    code = "INVALID_TOOL_ARGUMENTS"


class AgentToolAccessDenied(AgentToolArgumentsInvalid):
    code = "TOOL_ACCESS_DENIED"


CURATED_DOMAIN_SOURCES: dict[str, str] = {
    "concepts": "knowledge",
    "macro": "macro",
    "competitive": "competitive",
    "regulatory": "regulatory",
}


@dataclass(frozen=True, slots=True)
class AgentTool:
    name: str
    arguments_model: type[BaseModel]
    source_id: str | None
    sensitivity: str
    timeout_s: float
    max_result_chars: int
    parallel_safe: bool = True

    @property
    def requires_external_consent(self) -> bool:
        return bool(
            self.source_id
            and source_group(self.source_id).value in {"external_indexed", "live_external"}
        )


AGENT_TOOLS: dict[str, AgentTool] = {
    "search_curated_knowledge": AgentTool(
        name="search_curated_knowledge",
        arguments_model=SearchCuratedKnowledgeArguments,
        source_id=None,
        sensitivity="internal",
        timeout_s=20.0,
        max_result_chars=12_000,
    ),
    "search_public_web": AgentTool(
        name="search_public_web",
        arguments_model=SearchPublicWebArguments,
        source_id="web",
        sensitivity="public",
        timeout_s=30.0,
        max_result_chars=12_000,
    ),
    "visualize_query_result": AgentTool(
        name="visualize_query_result",
        arguments_model=VisualizeQueryResultArguments,
        source_id="db",
        sensitivity="internal",
        timeout_s=5.0,
        max_result_chars=12_000,
        parallel_safe=False,
    ),
    "finish_without_data": AgentTool(
        name="finish_without_data",
        arguments_model=FinishWithoutDataArguments,
        source_id=None,
        sensitivity="public",
        timeout_s=1.0,
        max_result_chars=1_000,
        parallel_safe=False,
    ),
    "submit_final_answer": AgentTool(
        name="submit_final_answer",
        arguments_model=FinalSynthesis,
        source_id=None,
        sensitivity="internal",
        timeout_s=1.0,
        max_result_chars=2_000,
        parallel_safe=False,
    ),
}


def _allowed_curated_domains(policy: SourceAccessPolicy) -> list[str]:
    return [
        domain
        for domain, source_id in CURATED_DOMAIN_SOURCES.items()
        if policy.allows(source_id)
    ]


def visible_agent_tools(policy: SourceAccessPolicy) -> list[AgentTool]:
    visible: list[AgentTool] = []
    for tool in AGENT_TOOLS.values():
        if tool.source_id is not None and not policy.allows(tool.source_id):
            continue
        if tool.name == "search_curated_knowledge" and not _allowed_curated_domains(policy):
            continue
        visible.append(tool)
    return visible


def get_agent_tool(name: str) -> AgentTool:
    try:
        return AGENT_TOOLS[name]
    except KeyError as exc:
        raise AgentToolNotFound(name) from exc


def validate_agent_arguments(
    name: str,
    arguments: dict[str, Any],
    *,
    policy: SourceAccessPolicy,
    catalog: Catalog | None = None,
) -> BaseModel:
    """Reauthorize and validate a call immediately before any future execution."""
    tool = get_agent_tool(name)
    if tool.source_id is not None:
        try:
            policy.require(tool.source_id)
        except SourceAccessDenied as exc:
            raise AgentToolAccessDenied(str(exc)) from exc

    try:
        parsed = tool.arguments_model.model_validate(arguments)
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first.get("loc", ())) or "arguments"
        raise AgentToolArgumentsInvalid(f"{location}: {first['msg']}") from exc

    if isinstance(parsed, SearchCuratedKnowledgeArguments):
        try:
            policy.require(CURATED_DOMAIN_SOURCES[parsed.domain])
        except SourceAccessDenied as exc:
            raise AgentToolAccessDenied(str(exc)) from exc
    return parsed


__all__ = [
    "AGENT_TOOLS",
    "CURATED_DOMAIN_SOURCES",
    "AgentTool",
    "AgentToolAccessDenied",
    "AgentToolArgumentsInvalid",
    "AgentToolError",
    "AgentToolNotFound",
    "get_agent_tool",
    "validate_agent_arguments",
    "visible_agent_tools",
]
