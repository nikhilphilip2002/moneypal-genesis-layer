"""Policy-filtered registry for provider-native Workbench tools.

This registry is deliberately separate from ``workbench.tools``, which backs the UI's quick
actions. Nothing in this module executes a tool. It defines the model-visible contracts and
performs the validation that must succeed before the later executor may dispatch a call.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.services.nlq.catalog import Catalog, get_catalog
from app.services.workbench.access import SourceAccessDenied, SourceAccessPolicy, source_group
from app.services.workbench.agent_contracts import (
    FinishWithoutDataArguments,
    SearchCuratedKnowledgeArguments,
    SearchPublicWebArguments,
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
    description: str
    arguments_model: type[BaseModel]
    handler_key: str
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
        description=(
            "Search policy documents, definitions, catalog documentation, macro, competitive, "
            "or regulatory evidence. Never use this to query customer, KYC, loan, agent, or "
            "other database rows named in Gold TABLE hints."
        ),
        arguments_model=SearchCuratedKnowledgeArguments,
        handler_key="search_curated_knowledge",
        source_id=None,
        sensitivity="internal",
        timeout_s=20.0,
        max_result_chars=12_000,
    ),
    "search_public_web": AgentTool(
        name="search_public_web",
        description="Search the live public web; never include private bank or customer data.",
        arguments_model=SearchPublicWebArguments,
        handler_key="search_public_web",
        source_id="web",
        sensitivity="public",
        timeout_s=30.0,
        max_result_chars=12_000,
    ),
    "finish_without_data": AgentTool(
        name="finish_without_data",
        description=(
            "End the turn with a clarifying question or governed refusal when no data tool "
            "should run."
        ),
        arguments_model=FinishWithoutDataArguments,
        handler_key="finish_without_data",
        source_id=None,
        sensitivity="public",
        timeout_s=1.0,
        max_result_chars=1_000,
        parallel_safe=False,
    ),
}


def _collapse_any_of(options: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse Pydantic's value unions into portable multi-type schemas.

    Object-shape unions are rejected rather than leaked into a provider tool schema. The
    flat contracts only need nullable objects and scalar/list value unions.
    """
    non_null = [option for option in options if option.get("type") != "null"]
    has_null = len(non_null) != len(options)
    if len(non_null) == 1:
        result = deepcopy(non_null[0])
        value_type = result.get("type")
        if has_null and isinstance(value_type, str):
            result["type"] = [value_type, "null"]
        return result

    allowed = {"string", "number", "integer", "boolean", "array"}
    types: list[str] = []
    array_constraints: dict[str, Any] = {}
    for option in non_null:
        value_type = option.get("type")
        if not isinstance(value_type, str) or value_type not in allowed:
            raise AgentToolError("provider schema would require a polymorphic object union")
        if value_type not in types:
            types.append(value_type)
        if value_type == "array":
            array_constraints = {
                key: deepcopy(value)
                for key, value in option.items()
                if key != "type"
            }
        elif set(option) != {"type"}:
            raise AgentToolError("provider schema contains an unsupported constrained union")
    if has_null:
        types.append("null")
    return {"type": types, **array_constraints}


def _portable_schema(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    definitions = raw.get("$defs", {})

    def project(node: Any) -> Any:
        if isinstance(node, list):
            return [project(value) for value in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            ref = node["$ref"]
            prefix = "#/$defs/"
            if not isinstance(ref, str) or not ref.startswith(prefix):
                raise AgentToolError(f"unsupported schema reference {ref!r}")
            name = ref.removeprefix(prefix)
            try:
                target = deepcopy(definitions[name])
            except KeyError as exc:
                raise AgentToolError(f"unknown schema reference {ref!r}") from exc
            target.update({key: value for key, value in node.items() if key != "$ref"})
            return project(target)

        projected = {
            key: project(value)
            for key, value in node.items()
            if key not in {"$defs", "default", "title"}
        }
        if "anyOf" in projected:
            options = projected.pop("anyOf")
            collapsed = _collapse_any_of(options)
            collapsed.update(projected)
            projected = collapsed

        value_type = projected.get("type")
        if value_type == "object" or (
            isinstance(value_type, list) and "object" in value_type
        ):
            properties = projected.get("properties", {})
            projected["additionalProperties"] = False
            projected["required"] = list(properties)
        return projected

    schema = project(raw)
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise AgentToolError(f"{model.__name__} does not project to a top-level object")
    return schema


def _allowed_curated_domains(policy: SourceAccessPolicy) -> list[str]:
    return [
        domain
        for domain, source_id in CURATED_DOMAIN_SOURCES.items()
        if policy.allows(source_id)
    ]


def _parameters_for(
    tool: AgentTool, *, catalog: Catalog, policy: SourceAccessPolicy,
) -> dict[str, Any]:
    schema = _portable_schema(tool.arguments_model)
    properties = schema["properties"]
    if tool.name == "search_curated_knowledge":
        properties["domain"]["enum"] = _allowed_curated_domains(policy)
    return schema


def visible_agent_tools(policy: SourceAccessPolicy) -> list[AgentTool]:
    visible: list[AgentTool] = []
    for tool in AGENT_TOOLS.values():
        if tool.source_id is not None and not policy.allows(tool.source_id):
            continue
        if tool.name == "search_curated_knowledge" and not _allowed_curated_domains(policy):
            continue
        visible.append(tool)
    return visible


def native_tool_definitions(
    policy: SourceAccessPolicy,
    *,
    catalog: Catalog | None = None,
    tool_names: tuple[str, ...] | list[str] | None = None,
) -> list[dict[str, Any]]:
    """Complete provider definitions for every tool the policy allows."""
    cat = catalog or get_catalog()
    allowed_names = set(tool_names or AGENT_TOOLS)
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": _parameters_for(tool, catalog=cat, policy=policy),
                "strict": True,
            },
        }
        for tool in visible_agent_tools(policy)
        if tool.name in allowed_names
    ]


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
    "native_tool_definitions",
    "validate_agent_arguments",
    "visible_agent_tools",
]
