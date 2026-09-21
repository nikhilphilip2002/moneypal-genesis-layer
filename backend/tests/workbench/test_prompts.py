import pytest

from app.services.workbench import prompts


def test_workbench_has_one_answer_system_prompt():
    assert hasattr(prompts, "AGENT_SYSTEM_PROMPT")
    assert not hasattr(prompts, "COMPOSER_SYSTEM_PROMPT")


def test_workbench_system_prompts_do_not_duplicate_json_schema_prose():
    content = prompts.build_agent_prompt(question="q").messages[0]["content"]
    assert isinstance(content, list)
    agent = content[0]["text"]
    assert '"additionalProperties"' not in agent
    assert '"properties"' not in agent


def test_answer_prompts_do_not_duplicate_structured_result_rows():
    assert "Structured result rows are rendered separately" in prompts.AGENT_SYSTEM_PROMPT
    assert "do not reproduce them as a Markdown table" in prompts.AGENT_SYSTEM_PROMPT


def test_agent_prompt_forbids_wildcard_and_duplicate_queries():
    prompt = prompts.AGENT_SYSTEM_PROMPT

    assert "Never use SELECT *, alias.*, or COUNT(*)" in prompt
    assert "name every selected column explicitly" in prompt
    assert "Submit each distinct SQL query only once" in prompt
    assert "never repeat the rejected SQL" in prompt


def test_agent_prompt_retrieves_only_relevant_gold_metadata():
    bundle = prompts.build_agent_prompt(
        question="monthly cash receipts by payment mode",
        tool_names=["query"],
    )
    content = bundle.messages[-1]["content"]
    assert "gold.payment_receipts" in content
    assert "receipt_total" in content
    assert "receipt_mode" in content
    assert "gold.semantic_msme_lead" not in content


def test_agent_prompt_keeps_catalog_hints_out_of_stable_prefix():
    receipts = prompts.build_agent_prompt(question="cash receipts")
    leads = prompts.build_agent_prompt(question="MSME lead security value")
    assert receipts.messages[0] == leads.messages[0]
    assert receipts.messages[-1] != leads.messages[-1]


def test_scheme_wise_metric_prompt_exposes_the_governed_scheme_dimension():
    context = prompts.build_agent_catalog_context("interest collected schemewise")

    assert context.metrics == ("interest_collected",)
    assert context.dimensions == ("scheme",)
    assert "- scheme | Scheme | categorical" in context.text
    assert "candidates retrieved for this question: scheme" in context.text


def test_no_time_cue_still_permits_a_month_breakdown():
    """Retrieval annotates; it never removes a dimension from the full schema."""
    context = prompts.build_agent_catalog_context("interest collected")
    assert "month" not in context.dimensions
    assert "must appear in `dimensions`" in context.text
    assert "- month |" in prompts.build_agent_gold_schema()


@pytest.mark.anyio
async def test_database_tools_are_not_defined_in_the_local_registry():
    from app.mcp import workbench_client
    from app.services.workbench import access

    offered = [
        item["function"]["name"] for item in await workbench_client.model_tool_definitions(
            access.build_policy(role="admin", external_sources_enabled=True),
        )
    ]
    assert not ({"query_metrics", "run_validated_query", "query"} & set(offered))
    assert set(offered) == {
        "search_curated_knowledge", "visualize_query_result", "finish_without_data",
        "submit_final_answer",
    }


def test_latest_tool_error_supplements_catalog_retrieval():
    plain = prompts.build_agent_catalog_context("interest collected")
    supplemented = prompts.build_agent_catalog_context(
        "interest collected", supplement="unknown dimension 'schemes'; did you mean scheme",
    )
    assert "scheme" not in plain.dimensions
    assert "scheme" in supplemented.dimensions
    assert "- scheme | Scheme | categorical" in supplemented.text
