"""Project MCP JSON Schemas into strict provider-native tool definitions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class ProviderSchemaError(ValueError):
    """An MCP schema cannot be represented by the configured LLM provider."""


def _collapse_any_of(
    options: list[dict[str, Any]], *, path: str
) -> dict[str, Any]:
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
            raise ProviderSchemaError(
                f"provider schema at {path} would require a polymorphic object union"
            )
        if value_type not in types:
            types.append(value_type)
        if value_type == "array":
            array_constraints = {
                key: deepcopy(value)
                for key, value in option.items()
                if key != "type"
            }
        elif set(option) != {"type"}:
            raise ProviderSchemaError(
                f"provider schema at {path} contains an unsupported constrained union"
            )
    if has_null:
        types.append("null")
    return {"type": types, **array_constraints}


def provider_schema(raw_schema: dict[str, Any]) -> dict[str, Any]:
    """Dereference and close one MCP input schema for strict provider mode."""
    raw = deepcopy(raw_schema)
    definitions = raw.get("$defs", {})

    def project(
        node: Any,
        *,
        path: str = "$",
        resolving: frozenset[str] = frozenset(),
    ) -> Any:
        if isinstance(node, list):
            return [
                project(value, path=f"{path}[{index}]", resolving=resolving)
                for index, value in enumerate(node)
            ]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            ref = node["$ref"]
            prefix = "#/$defs/"
            if not isinstance(ref, str) or not ref.startswith(prefix):
                raise ProviderSchemaError(
                    f"unsupported schema reference {ref!r} at {path}"
                )
            if ref in resolving:
                raise ProviderSchemaError(
                    f"recursive schema reference {ref!r} at {path}"
                )
            name = ref.removeprefix(prefix)
            try:
                target = deepcopy(definitions[name])
            except KeyError as exc:
                raise ProviderSchemaError(
                    f"unknown schema reference {ref!r} at {path}"
                ) from exc
            target.update(
                {key: value for key, value in node.items() if key != "$ref"}
            )
            return project(target, path=path, resolving=resolving | {ref})

        unsupported = {"oneOf", "allOf", "if", "then", "else", "discriminator"}
        present = unsupported.intersection(node)
        if present:
            raise ProviderSchemaError(
                "provider schema contains unsupported keyword(s): "
                + ", ".join(sorted(present))
                + f" at {path}"
            )

        projected = {
            key: project(value, path=f"{path}.{key}", resolving=resolving)
            for key, value in node.items()
            if key not in {"$defs", "default", "title", "$schema"}
        }
        if "const" in projected:
            projected["enum"] = [projected.pop("const")]
        if "anyOf" in projected:
            options = projected.pop("anyOf")
            if not isinstance(options, list) or not all(
                isinstance(option, dict) for option in options
            ):
                raise ProviderSchemaError(
                    f"provider schema contains an invalid anyOf at {path}"
                )
            if options and all(
                option.get("type") == "object" for option in options
            ):
                projected["anyOf"] = options
            else:
                collapsed = _collapse_any_of(options, path=f"{path}.anyOf")
                collapsed.update(projected)
                projected = collapsed

        value_type = projected.get("type")
        if value_type == "object" or (
            isinstance(value_type, list) and "object" in value_type
        ):
            properties = projected.get("properties", {})
            if not isinstance(properties, dict):
                raise ProviderSchemaError(
                    f"object schema has invalid properties at {path}.properties"
                )
            projected["additionalProperties"] = False
            projected["required"] = list(properties)
        return projected

    schema = project(raw)
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ProviderSchemaError(
            "tool input schema is not a top-level object"
        )
    return schema


def provider_tool_definition(tool: Any) -> dict[str, Any]:
    """Convert one MCP tool descriptor into the configured provider function shape."""
    try:
        parameters = provider_schema(tool.input_schema)
    except ProviderSchemaError as exc:
        raise ProviderSchemaError(f"tool {tool.name!r}: {exc}") from exc
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "MCP tool",
            "parameters": parameters,
            "strict": True,
        },
    }


__all__ = [
    "ProviderSchemaError",
    "provider_schema",
    "provider_tool_definition",
]
