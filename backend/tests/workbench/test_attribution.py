import pytest
from pydantic import ValidationError

from app.services.workbench.agent_contracts import FinalSynthesis
from app.services.workbench.attribution import reconcile_query_attribution


def _record(query_id, *, status="success", has_data=True, purpose="answer"):
    return {
        "query_id": query_id, "attempt_id": f"{query_id}:a1",
        "tool_call_id": f"call-{query_id}", "tool_name": "query",
        "status": status, "purpose": purpose, "row_count": 1 if has_data else 0,
        "has_data": has_data, "visual_available": False, "duration_ms": 1,
        "source_query_id": None,
    }


def test_final_synthesis_is_three_fields_and_allows_empty_insights():
    synthesis = FinalSynthesis.model_validate({
        "insights": "", "query_id": 1, "view": "table",
    })
    assert synthesis.insights == ""
    with pytest.raises(ValidationError):
        FinalSynthesis.model_validate({
            "insights": "Answer", "query_id": 1, "view": "table",
            "schema_version": 1,
        })


def test_reconciliation_selects_one_local_query_and_derives_exclusions():
    registry = [_record("turn:q1", purpose="discovery"), _record("turn:q2")]
    result = reconcile_query_attribution(
        registry, FinalSynthesis(insights="Answer", query_id=2, view="bar"),
    )

    assert result.active_query_ids == ["turn:q2"]
    assert result.visual_query_ids == ["turn:q2"]
    assert result.invalid_query_ids == []
    assert result.excluded_queries[0].query_id == "turn:q1"
    assert result.excluded_queries[0].reason_code == "discovery_only"


def test_reconciliation_rejects_unknown_or_unsuccessful_selection():
    registry = [_record("turn:q1", status="error", has_data=False)]
    failed = reconcile_query_attribution(
        registry, FinalSynthesis(insights="", query_id=1, view="table"),
    )
    missing = reconcile_query_attribution(
        registry, FinalSynthesis(insights="", query_id=2, view="table"),
    )

    assert failed.active_query_ids == []
    assert failed.invalid_query_ids == ["q1"]
    assert missing.invalid_query_ids == ["q2"]
