from app.services.nlq.llm import prompts as planner_prompts
from app.services.workbench import prompts


def test_composer_prefix_is_stable_across_evidence():
    first = prompts.build_composer_prompt(question="q", findings="first")
    second = prompts.build_composer_prompt(question="q", findings="second")
    assert first.prefix_hash == second.prefix_hash
    assert first.messages[0] == second.messages[0]


def test_planner_prefix_is_byte_stable():
    assert planner_prompts.stable_prefix() == planner_prompts.stable_prefix()
    assert planner_prompts.stable_prefix_hash() == planner_prompts.stable_prefix_hash()


def test_workbench_system_prompts_do_not_duplicate_json_schema_prose():
    agent = prompts.build_agent_prompt(question="q").messages[0]["content"]
    composer = prompts.build_composer_prompt(question="q", findings="e").messages[0]["content"]
    for system_prompt in (agent, composer):
        assert '"additionalProperties"' not in system_prompt
        assert '"properties"' not in system_prompt


def test_composer_has_no_router_catalog_sql_or_tool_implementation_context():
    system = prompts.COMPOSER_SYSTEM_PROMPT.lower()
    for forbidden in ("macro", "competitive", "regulatory", "route", "sql", "qdrant", "tool"):
        assert forbidden not in system


def test_answer_prompts_do_not_duplicate_structured_result_rows():
    for system in (prompts.COMPOSER_SYSTEM_PROMPT, prompts.AGENT_SYSTEM_PROMPT):
        assert "Structured result rows are rendered separately" in system
        assert "do not reproduce them as a Markdown table" in system


def test_agent_prompt_retrieves_only_relevant_gold_metadata():
    bundle = prompts.build_agent_prompt(
        question="monthly cash receipts by payment mode",
        tool_names=["query_metrics", "run_validated_query"],
    )
    content = bundle.messages[-1]["content"]
    assert "gold.semantic_receipt_adjustment_event" in content
    assert "receipt_total" in content
    assert "receipt_mode" in content
    assert "gold.semantic_msme_lead" not in content


def test_agent_prompt_keeps_catalog_hints_out_of_stable_prefix():
    receipts = prompts.build_agent_prompt(question="cash receipts")
    leads = prompts.build_agent_prompt(question="MSME lead security value")
    assert receipts.prefix_hash == leads.prefix_hash
    assert receipts.messages[0] == leads.messages[0]
    assert receipts.messages[-1] != leads.messages[-1]


def test_scheme_wise_metric_prompt_exposes_the_governed_scheme_dimension():
    context = prompts.build_agent_catalog_context("interest collected schemewise")

    assert context.metrics == ("interest_collected",)
    assert context.dimensions == ("scheme",)
    assert "- scheme | Scheme | categorical" in context.text
    assert "candidates retrieved for this question: scheme" in context.text


def test_no_time_cue_still_permits_a_month_breakdown():
    """B4: retrieval annotates; it never removes a dimension from the schema."""
    from app.services.workbench import access
    from app.services.workbench.agent_tools import native_tool_definitions

    context = prompts.build_agent_catalog_context("interest collected")
    assert "month" not in context.dimensions
    assert "must appear in `dimensions`" in context.text
    definitions = native_tool_definitions(
        access.build_policy(role="admin", external_sources_enabled=True),
    )
    dimensions = next(
        item for item in definitions if item["function"]["name"] == "query_metrics"
    )["function"]["parameters"]["properties"]["dimensions"]
    assert "month" in dimensions["items"]["enum"]
    assert "maxItems" not in dimensions


def test_row_question_still_offers_both_governed_query_tools():
    from app.services.workbench import access
    from app.services.workbench.agent_tools import native_tool_definitions

    offered = [
        item["function"]["name"] for item in native_tool_definitions(
            access.build_policy(role="admin", external_sources_enabled=True),
        )
    ]
    assert "query_metrics" in offered and "run_validated_query" in offered


def test_latest_tool_error_supplements_catalog_retrieval():
    plain = prompts.build_agent_catalog_context("interest collected")
    supplemented = prompts.build_agent_catalog_context(
        "interest collected", supplement="unknown dimension 'schemes'; did you mean scheme",
    )
    assert "scheme" not in plain.dimensions
    assert "scheme" in supplemented.dimensions
    assert "- scheme | Scheme | categorical" in supplemented.text
