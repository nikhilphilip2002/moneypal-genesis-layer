from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.mcp.provider_schema import (
    ProviderSchemaError,
    provider_schema,
    provider_tool_definition,
)


def test_projects_refs_nullable_nested_objects_and_constraints_deterministically():
    raw = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {
            "Filter": {
                "title": "Filter",
                "type": "object",
                "properties": {
                    "field": {"type": "string", "minLength": 1},
                    "value": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                },
            }
        },
        "title": "Arguments",
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["a", "b"]},
            "filters": {
                "type": "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {"$ref": "#/$defs/Filter"},
            },
        },
    }

    expected = {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["a", "b"]},
            "filters": {
                "type": "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "minLength": 1},
                        "value": {"type": ["number", "null"]},
                    },
                    "additionalProperties": False,
                    "required": ["field", "value"],
                },
            },
        },
        "additionalProperties": False,
        "required": ["mode", "filters"],
    }
    assert provider_schema(raw) == expected
    assert provider_schema(raw) == expected
    assert raw["properties"]["filters"]["items"] == {"$ref": "#/$defs/Filter"}


def test_projects_nested_object_union():
    raw = {
        "type": "object",
        "properties": {
            "submission": {
                "anyOf": [
                    {
                        "type": "object",
                        "properties": {
                            "outcome": {"type": "string", "const": "answer"},
                            "query_id": {"type": "integer", "minimum": 1},
                        },
                    },
                    {
                        "type": "object",
                        "properties": {
                            "outcome": {
                                "type": "string",
                                "enum": ["clarify", "refuse"],
                            },
                            "message": {"type": "string"},
                        },
                    },
                ]
            }
        },
    }

    projected = provider_schema(raw)
    variants = projected["properties"]["submission"]["anyOf"]
    assert [variant["required"] for variant in variants] == [
        ["outcome", "query_id"],
        ["outcome", "message"],
    ]
    assert all(
        variant["additionalProperties"] is False for variant in variants
    )
    assert variants[0]["properties"]["outcome"]["enum"] == ["answer"]
    assert "oneOf" not in projected["properties"]["submission"]


@pytest.mark.parametrize(
    "schema,message",
    [
        ({"type": "string"}, "top-level object"),
        (
            {
                "type": "object",
                "properties": [],
            },
            "invalid properties",
        ),
        (
            {
                "type": "object",
                "properties": {"value": {"$ref": "#/components/Value"}},
            },
            "unsupported schema reference",
        ),
        (
            {
                "type": "object",
                "properties": {"value": {"$ref": "#/$defs/Missing"}},
            },
            "unknown schema reference",
        ),
        (
            {
                "$defs": {"Node": {"$ref": "#/$defs/Node"}},
                "type": "object",
                "properties": {"node": {"$ref": "#/$defs/Node"}},
            },
            "recursive schema reference",
        ),
        (
            {
                "type": "object",
                "properties": {
                    "value": {
                        "anyOf": [
                            {"type": "object", "properties": {}},
                            {"type": "string"},
                        ]
                    }
                },
            },
            "polymorphic object union",
        ),
        (
            {
                "type": "object",
                "properties": {
                    "submission": {
                        "oneOf": [
                            {
                                "type": "object",
                                "properties": {"outcome": {"const": "answer"}},
                            },
                            {
                                "type": "object",
                                "properties": {"outcome": {"const": "answer"}},
                            },
                        ]
                    }
                },
            },
            "unsupported keyword",
        ),
        (
            {
                "type": "object",
                "properties": {"value": {"if": {}, "then": {}}},
            },
            "unsupported keyword",
        ),
    ],
)
def test_rejects_unsupported_or_invalid_schemas(schema, message):
    with pytest.raises(ProviderSchemaError, match=message):
        provider_schema(schema)


def test_tool_definition_uses_mcp_descriptor_fields():
    tool = SimpleNamespace(
        name="lookup",
        description="Look something up.",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "integer"}},
        },
    )
    assert provider_tool_definition(tool) == {
        "type": "function",
        "function": {
            "name": "lookup",
            "description": "Look something up.",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "additionalProperties": False,
                "required": ["id"],
            },
            "strict": True,
        },
    }


def test_tool_definition_errors_include_tool_name_and_json_path():
    tool = SimpleNamespace(
        name="broken",
        description="Broken.",
        input_schema={
            "type": "object",
            "properties": {"value": {"$ref": "#/$defs/Missing"}},
        },
    )
    with pytest.raises(
        ProviderSchemaError,
        match=r"tool 'broken'.*\$\.properties\.value",
    ):
        provider_tool_definition(tool)
