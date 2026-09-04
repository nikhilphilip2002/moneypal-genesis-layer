from app.services.nlq.llm import prompts as planner_prompts
from app.services.workbench import prompts


def test_router_prefix_is_stable_across_dynamic_questions():
    first = prompts.build_router_prompt(role="admin", question="question one")
    second = prompts.build_router_prompt(role="admin", question="question two")
    assert first.version == second.version
    assert first.prefix_hash == second.prefix_hash
    assert first.messages != second.messages


def test_composer_prefix_is_stable_across_evidence():
    first = prompts.build_composer_prompt(question="q", findings="first")
    second = prompts.build_composer_prompt(question="q", findings="second")
    assert first.prefix_hash == second.prefix_hash
    assert first.messages[0] == second.messages[0]


def test_planner_prefix_is_byte_stable():
    assert planner_prompts.stable_prefix() == planner_prompts.stable_prefix()
    assert planner_prompts.stable_prefix_hash() == planner_prompts.stable_prefix_hash()


def test_workbench_system_prompts_do_not_duplicate_json_schema_prose():
    router = prompts.build_router_prompt(role="admin", question="q").messages[0]["content"]
    composer = prompts.build_composer_prompt(question="q", findings="e").messages[0]["content"]
    for system_prompt in (router, composer):
        assert '"additionalProperties"' not in system_prompt
        assert '"properties"' not in system_prompt


def test_composer_has_no_router_catalog_sql_or_tool_implementation_context():
    system = prompts.COMPOSER_SYSTEM_PROMPT.lower()
    for forbidden in ("macro", "competitive", "regulatory", "route", "sql", "table", "qdrant", "tool"):
        assert forbidden not in system


def test_router_fallback_prompt_is_compact():
    bundle = prompts.build_router_prompt(role="admin", question="ambiguous request")
    # A conservative characters/4 estimate leaves room for the constrained schema under
    # the 900-token p95 fallback budget.
    assert len(bundle.messages[0]["content"]) / 4 < 400
