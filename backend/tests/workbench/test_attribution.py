import pytest
from pydantic import ValidationError

from app.services.workbench.agent_contracts import FinalSynthesis
from app.services.workbench.attribution import reconcile_query_attribution


def _record(
    query_id, *, status="success", has_data=True, visual=None, purpose="answer",
    tool_name="query", source_query_id=None,
):
    if visual is None:
        visual = tool_name == "visualize_query_result"
    return {
        "query_id": query_id, "attempt_id": f"{query_id}:a1",
        "tool_call_id": f"call-{query_id}", "tool_name": tool_name,
        "status": status, "purpose": purpose, "row_count": 1 if has_data else 0,
        "has_data": has_data, "visual_available": visual, "duration_ms": 1,
        "source_query_id": source_query_id,
    }


def _synthesis(*, active=(), visual=()):
    return FinalSynthesis(
        narrative_insights="Answer", active_query_ids=list(active),
        visual_query_ids=list(visual),
    )


def test_final_synthesis_rejects_active_excluded_overlap():
    with pytest.raises(ValidationError, match="both active and excluded"):
        FinalSynthesis.model_validate({
            "narrative_insights": "Contradictory answer",
            "active_query_ids": ["t:q1"],
            "visual_query_ids": [],
            "excluded_queries": [{
                "query_id": "t:q1", "reason_code": "unused_by_synthesis",
                "reason": "Not actually used.",
            }],
        })


def test_reconciliation_deduplicates_and_rejects_invented_ids():
    result = reconcile_query_attribution(
        [_record("t:q1"), _record(
            "t:v1", tool_name="visualize_query_result", source_query_id="t:q1",
        )],
        _synthesis(active=["t:q1", "made-up", "t:q1"], visual=["t:v1", "made-up"]),
    )

    assert result.active_query_ids == ["t:q1"]
    assert result.visual_query_ids == ["t:v1"]
    assert result.invalid_query_ids == ["made-up"]


def test_reconciliation_filters_error_empty_and_timeout_results():
    registry = [
        _record("t:q1", status="error", has_data=False, visual=False),
        _record("t:q2", status="empty", has_data=False, visual=False),
        _record("t:q3", status="timeout", has_data=False, visual=False),
        _record("t:q4"),
        _record(
            "t:v1", tool_name="visualize_query_result", source_query_id="t:q4",
        ),
    ]
    result = reconcile_query_attribution(
        registry,
        _synthesis(active=["t:q1", "t:q2", "t:q3", "t:q4"], visual=["t:q1", "t:v1"]),
    )

    assert result.active_query_ids == ["t:q4"]
    assert result.visual_query_ids == ["t:v1"]
    assert {item.query_id: item.reason_code for item in result.excluded_queries} == {
        "t:q1": "execution_error", "t:q2": "empty_result", "t:q3": "timeout",
    }


def test_reconciliation_never_infers_missing_query_references():
    result = reconcile_query_attribution([_record("t:q1")], _synthesis())
    assert result.active_query_ids == []
    assert result.visual_query_ids == []
    assert result.fallback_used is False


def test_visuals_are_active_visualizable_intersection():
    result = reconcile_query_attribution(
        [_record("t:q2"), _record("t:q1"), _record(
            "t:v1", tool_name="visualize_query_result", source_query_id="t:q2",
        )],
        _synthesis(active=["t:q1", "t:q2"], visual=["t:q1", "t:v1"]),
    )
    assert result.active_query_ids == ["t:q1", "t:q2"]
    assert result.visual_query_ids == ["t:v1"]


def test_discovery_query_gets_deterministic_audit_reason():
    result = reconcile_query_attribution(
        [_record("t:q1", purpose="discovery"), _record("t:q2")],
        _synthesis(active=["t:q2"], visual=["t:q2"]),
    )
    assert result.excluded_queries[0].reason_code == "discovery_only"


def test_model_rationale_only_supplements_semantic_unused_reason():
    synthesis = FinalSynthesis.model_validate({
        "schema_version": 1, "narrative_insights": "Used q2.",
        "active_query_ids": ["t:q2"], "visual_query_ids": ["t:q2"],
        "excluded_queries": [{
            "query_id": "t:q1", "reason_code": "unused_by_synthesis",
            "reason": "Outliers made this result irrelevant to the requested trend.",
        }],
    })
    result = reconcile_query_attribution(
        [_record("t:q1"), _record("t:q2")], synthesis,
    )
    assert result.excluded_queries[0].reason == (
        "Outliers made this result irrelevant to the requested trend."
    )


def test_model_can_classify_successful_unused_query_purpose_but_not_execution_status():
    registry = [_record("t:q1"), _record("t:q2")]
    synthesis = FinalSynthesis.model_validate({
        "schema_version": 1, "narrative_insights": "Used q2.",
        "active_query_ids": ["t:q2"], "visual_query_ids": ["t:q2"],
        "excluded_queries": [{
            "query_id": "t:q1", "reason_code": "discovery_only",
            "reason": "Used only to inspect available periods.",
        }],
    })

    result = reconcile_query_attribution(registry, synthesis)

    assert registry[0]["purpose"] == "discovery"
    assert result.excluded_queries[0].reason_code == "discovery_only"
    assert result.excluded_queries[0].reason == "Used only to inspect available periods."


def test_successful_unused_query_can_be_declared_superseded():
    synthesis = FinalSynthesis.model_validate({
        "schema_version": 1, "narrative_insights": "Used the corrected result.",
        "active_query_ids": ["t:q2"], "visual_query_ids": ["t:q2"],
        "excluded_queries": [{
            "query_id": "t:q1", "reason_code": "superseded",
            "reason": "Replaced by the corrected period filter.",
        }],
    })
    result = reconcile_query_attribution(
        [_record("t:q1"), _record("t:q2")], synthesis,
    )
    assert result.excluded_queries[0].reason_code == "superseded"
    assert result.excluded_queries[0].reason == "Replaced by the corrected period filter."


def test_successful_derived_visual_is_not_promoted_without_explicit_reference():
    result = reconcile_query_attribution(
        [
            _record("t:q1"),
            _record(
                "t:v1", tool_name="visualize_query_result", source_query_id="t:q1",
            ),
        ],
        _synthesis(active=["t:q1"], visual=[]),
    )

    assert result.active_query_ids == ["t:q1"]
    assert result.visual_query_ids == []
    assert [item.query_id for item in result.excluded_queries] == ["t:v1"]
    assert result.fallback_used is False


def test_historical_source_reference_is_not_rewritten_to_a_visual():
    result = reconcile_query_attribution(
        [_record(
            "current:v1", tool_name="visualize_query_result",
            source_query_id="previous:q1",
        )],
        _synthesis(active=["previous:q1"], visual=["previous:q1"]),
    )

    assert result.active_query_ids == []
    assert result.visual_query_ids == []
    assert result.invalid_query_ids == ["previous:q1"]
    assert result.fallback_used is False
