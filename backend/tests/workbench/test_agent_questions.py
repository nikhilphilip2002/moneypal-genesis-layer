from pathlib import Path

import yaml

from app.services.nlq.catalog import get_catalog
from app.services.nlq.compiler import compile_spec
from app.services.nlq.contracts import Period, QuerySpec
from app.services.workbench.prompts import agent_catalog_context, build_agent_catalog_context


GOLDEN = Path(__file__).parent / "golden" / "agent_questions.yaml"


def _families():
    return yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))


def test_agent_question_set_covers_every_gold_view_with_multiple_phrasings():
    catalog = get_catalog()
    families = _families()
    prompts = [prompt for family in families for prompt in family["prompts"]]

    assert len(families) == 36
    assert len(prompts) == 108
    assert len(set(prompts)) == len(prompts)
    assert {family["view"] for family in families} == catalog.allowed_tables()
    assert all(len(family["prompts"]) == 3 for family in families)


def test_agent_question_expectations_reference_only_governed_catalog_entries():
    catalog = get_catalog()
    for family in _families():
        assert family["tool"] in {"query_metrics", "run_validated_query"}
        assert set(family.get("metrics", ())) <= set(catalog.metrics)
        assert set(family.get("dimensions", ())) <= set(catalog.dimensions)
        assert set(family.get("tables", ())) <= catalog.allowed_tables()
        if family["tool"] == "query_metrics":
            assert family.get("metrics")
            assert "tables" not in family
        else:
            assert family.get("tables")
            assert "metrics" not in family


def test_retrieved_prompt_context_keeps_each_expected_view_visible():
    failures = []
    for family in _families():
        for prompt in family["prompts"]:
            context = agent_catalog_context(prompt)
            for entry_id in (
                family["view"],
                *family.get("tables", ()),
                *family.get("metrics", ()),
                *family.get("dimensions", ()),
            ):
                if entry_id not in context:
                    failures.append((family["id"], prompt, entry_id))
    assert not failures


def test_every_metric_expectation_compiles_through_the_governed_engine():
    catalog = get_catalog()
    for family in _families():
        if family["tool"] != "query_metrics":
            continue
        metrics = [catalog.metrics[metric_id] for metric_id in family["metrics"]]
        relative = (
            "today"
            if any(metric.point_in_time or metric.no_time_travel for metric in metrics)
            else "all_time"
        )
        spec = QuerySpec(
            metrics=family["metrics"],
            dimensions=family.get("dimensions", []),
            period=Period(relative=relative),
        )
        compile_spec(spec, catalog)


def test_each_question_builds_the_expected_tool_specific_catalog_surface():
    failures = []
    for family in _families():
        for prompt in family["prompts"]:
            context = build_agent_catalog_context(prompt)
            if family["tool"] == "query_metrics":
                if (
                    set(context.metrics) != set(family["metrics"])
                    or set(context.dimensions) != set(family.get("dimensions", ()))
                    or context.requires_validated_query
                ):
                    failures.append((family["id"], prompt, context))
            elif (
                not context.requires_validated_query
                or not context.tables
                or set(context.tables) != set(family["tables"])
            ):
                failures.append((family["id"], prompt, context))
    assert not failures
