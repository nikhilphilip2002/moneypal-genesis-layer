import pytest

from app.core.tool_names import (
    QUERY,
    READ_TOOL_OUTPUT,
    SEARCH_CURATED_KNOWLEDGE,
    SUBMIT_ANSWER,
)


@pytest.mark.anyio
async def test_database_tools_are_not_defined_in_the_local_registry():
    from app.mcp.tool_catalog import ToolCatalog
    from app.services.workbench import access

    catalog = ToolCatalog()
    await catalog.discover_local()
    offered = [
        item["function"]["name"]
        for item in await catalog.model_tool_definitions(
            access.build_policy(role="admin", external_sources_enabled=True),
        )
    ]
    assert not (
        {"query_metrics", "run_validated_query", QUERY} & set(offered)
    )
    assert set(offered) == {
        READ_TOOL_OUTPUT,
        SEARCH_CURATED_KNOWLEDGE,
        SUBMIT_ANSWER,
    }
