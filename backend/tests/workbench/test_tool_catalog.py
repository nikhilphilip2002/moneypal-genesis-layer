from __future__ import annotations

from copy import deepcopy

import pytest

from app.mcp.tool_catalog import ToolCatalog, ToolCatalogError
from app.services.workbench import access


def _definition(name: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": name,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }


@pytest.mark.anyio
async def test_catalog_filters_policy_without_mutating_canonical_definitions():
    catalog = ToolCatalog()
    await catalog.discover_local()
    before = catalog.schema_fingerprint()
    policy = access.build_policy(role="admin", external_sources_enabled=False)

    definitions = await catalog.model_tool_definitions(policy)
    offered = {item["function"]["name"] for item in definitions}
    curated = next(
        item
        for item in definitions
        if item["function"]["name"] == "search_curated_knowledge"
    )

    assert "search_public_web" not in offered
    assert curated["function"]["parameters"]["properties"]["domain"][
        "enum"
    ] == ["concepts"]
    assert catalog.schema_fingerprint() == before


@pytest.mark.anyio
async def test_catalog_rejects_duplicate_names_across_servers():
    catalog = ToolCatalog()
    await catalog.discover_local()
    duplicate = deepcopy(catalog._entries["submit_final_answer"].definition)

    with pytest.raises(ToolCatalogError, match="duplicate MCP tool name"):
        catalog.register_postgres_definitions([duplicate])


@pytest.mark.anyio
async def test_catalog_fails_when_discovered_local_tool_has_no_runtime_policy(
    monkeypatch,
):
    from app.mcp import workbench_client

    catalog = ToolCatalog()
    real = workbench_client.canonical_model_definitions
    await workbench_client.discover_model_tools()
    definitions = real()
    monkeypatch.setattr(
        workbench_client,
        "canonical_model_definitions",
        lambda: [*definitions, _definition("unclassified")],
    )

    with pytest.raises(
        ToolCatalogError, match="missing runtime policy: unclassified"
    ):
        await catalog.discover_local()


@pytest.mark.anyio
async def test_catalog_readiness_has_ownership_versions_and_fingerprint():
    catalog = ToolCatalog()
    await catalog.discover_local()
    catalog.register_postgres_definitions([_definition("query")])

    readiness = catalog.readiness()
    assert readiness["status"] == "ok"
    assert readiness["owners"]["postgres"] == ["query"]
    assert readiness["owners"]["workbench"]
    assert len(readiness["schema_fingerprint"]) == 64
    assert readiness["mcp_sdk_version"].startswith("2.")
    assert readiness["fastmcp_version"].startswith("4.")
