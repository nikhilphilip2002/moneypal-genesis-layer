"""Runtime-only policy metadata for model-visible Workbench tools.

FastMCP owns names, descriptions, input schemas, argument validation, and handlers. This
module deliberately contains only orchestration policy that is not part of an MCP contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.workbench.access import (
    SourceAccessDenied,
    SourceAccessPolicy,
    source_group,
)


class AgentToolError(ValueError):
    """Base for tool classification failures safe to return to the agent."""


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
class RuntimeToolPolicy:
    source_id: str | None
    sensitivity: str
    timeout_s: float
    max_result_chars: int
    parallel_safe: bool = True

    @property
    def requires_external_consent(self) -> bool:
        return bool(
            self.source_id
            and source_group(self.source_id).value
            in {"external_indexed", "live_external"}
        )


RUNTIME_TOOL_POLICIES: dict[str, RuntimeToolPolicy] = {
    "search_curated_knowledge": RuntimeToolPolicy(
        source_id=None,
        sensitivity="internal",
        timeout_s=20.0,
        max_result_chars=12_000,
    ),
    "search_public_web": RuntimeToolPolicy(
        source_id="web",
        sensitivity="public",
        timeout_s=30.0,
        max_result_chars=12_000,
    ),
    "visualize_query_result": RuntimeToolPolicy(
        source_id="db",
        sensitivity="internal",
        timeout_s=5.0,
        max_result_chars=12_000,
        parallel_safe=False,
    ),
    "finish_without_data": RuntimeToolPolicy(
        source_id=None,
        sensitivity="public",
        timeout_s=1.0,
        max_result_chars=1_000,
        parallel_safe=False,
    ),
    "submit_final_answer": RuntimeToolPolicy(
        source_id="db",
        sensitivity="internal",
        timeout_s=1.0,
        max_result_chars=2_000,
        parallel_safe=False,
    ),
}


def allowed_curated_domains(policy: SourceAccessPolicy) -> list[str]:
    return [
        domain
        for domain, source_id in CURATED_DOMAIN_SOURCES.items()
        if policy.allows(source_id)
    ]


def visible_runtime_tool_names(policy: SourceAccessPolicy) -> list[str]:
    visible: list[str] = []
    for name, runtime_policy in RUNTIME_TOOL_POLICIES.items():
        if name == "visualize_query_result":
            continue
        if runtime_policy.source_id is not None and not policy.allows(
            runtime_policy.source_id
        ):
            continue
        if name == "search_curated_knowledge" and not allowed_curated_domains(
            policy
        ):
            continue
        visible.append(name)
    return visible


def get_runtime_tool_policy(name: str) -> RuntimeToolPolicy:
    try:
        return RUNTIME_TOOL_POLICIES[name]
    except KeyError as exc:
        raise AgentToolNotFound(name) from exc


def authorize_local_tool_call(
    name: str,
    arguments: Any,
    *,
    policy: SourceAccessPolicy,
) -> None:
    """Apply policy only; FastMCP remains the sole argument-validation boundary."""
    runtime_policy = get_runtime_tool_policy(name)
    if not isinstance(arguments, dict):
        raise AgentToolArgumentsInvalid(
            "MCP tool arguments must be a JSON object"
        )
    if runtime_policy.source_id is not None:
        try:
            policy.require(runtime_policy.source_id)
        except SourceAccessDenied as exc:
            raise AgentToolAccessDenied(str(exc)) from exc
    if name == "search_curated_knowledge":
        source_id = CURATED_DOMAIN_SOURCES.get(arguments.get("domain"))
        if source_id is not None:
            try:
                policy.require(source_id)
            except SourceAccessDenied as exc:
                raise AgentToolAccessDenied(str(exc)) from exc


__all__ = [
    "CURATED_DOMAIN_SOURCES",
    "RUNTIME_TOOL_POLICIES",
    "AgentToolAccessDenied",
    "AgentToolArgumentsInvalid",
    "AgentToolError",
    "AgentToolNotFound",
    "RuntimeToolPolicy",
    "allowed_curated_domains",
    "authorize_local_tool_call",
    "get_runtime_tool_policy",
    "visible_runtime_tool_names",
]
