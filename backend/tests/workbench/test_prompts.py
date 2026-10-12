import pytest


@pytest.mark.anyio
async def test_database_tools_are_not_defined_in_the_local_registry(monkeypatch):
    from app.mcp.tool_catalog import ToolCatalog
    from app.services.workbench import access

    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", False)

    catalog = ToolCatalog()
    await catalog.discover_local()
    offered = [
        item["function"]["name"]
        for item in await catalog.model_tool_definitions(
            access.build_policy(role="admin", external_sources_enabled=True),
        )
    ]
    assert not (
        {"query_metrics", "run_validated_query", "query"} & set(offered)
    )
    assert set(offered) == {
        "search_customer_360",
        "search_curated_knowledge",
        "submit_final_answer",
    }
