from app.services.nlq.llm.telemetry import (
    CallRecord,
    budget_violations,
    call_counts,
    collect_calls,
    prefix_hash,
    serialize_messages,
    summarize_calls,
)


def _record(**changes):
    values = {
        "purpose": "route",
        "call_kind": "planned",
        "provider": "llamacpp",
        "model": "test",
        "prompt_version": "router-v1",
        "catalog_version": "",
        "prefix_hash": "abc",
        "prompt_tokens": 100,
        "cached_prompt_tokens": 80,
        "cache_write_prompt_tokens": 0,
        "uncached_prompt_tokens": 20,
        "completion_tokens": 10,
        "duration_ms": 250,
        "attempts": 1,
        "retries": 0,
        "finish_reason": "stop",
    }
    values.update(changes)
    return CallRecord(**values)


def test_message_serialization_and_hash_are_byte_stable():
    messages = [{"role": "system", "content": "fixed"}]
    assert serialize_messages(messages) == serialize_messages(list(messages))
    assert prefix_hash(messages) == prefix_hash(list(messages))
    assert prefix_hash(messages) != prefix_hash([{"role": "system", "content": "changed"}])


def test_turn_summary_separates_context_size_from_additive_cost():
    records = [
        _record(),
        _record(
            purpose="final_compose", prompt_tokens=60, cached_prompt_tokens=10,
            uncached_prompt_tokens=50, completion_tokens=20, duration_ms=400,
            attempts=2, retries=1,
        ),
    ]
    summary = summarize_calls(records)
    assert summary["model_call_count"] == 2
    assert summary["prompt_tokens"] == 100
    assert summary["total_prompt_tokens"] == 160
    assert summary["cached_prompt_tokens"] == 90
    assert summary["uncached_prompt_tokens"] == 70
    assert summary["completion_tokens"] == 30
    assert summary["model_duration_ms"] == 650
    assert summary["retry_count"] == 1
    assert [call["purpose"] for call in summary["calls"]] == ["route", "final_compose"]


def test_collectors_are_scoped():
    with collect_calls() as outer:
        assert outer == []
    with collect_calls() as second:
        assert second == []
    assert outer is not second


def test_call_budget_helpers_report_only_excess_calls():
    records = [_record(), _record(), _record(purpose="final_compose")]
    assert call_counts(records) == {"route": 2, "final_compose": 1}
    assert budget_violations(records, {"route": 1, "final_compose": 1}) == {
        "route": (2, 1),
    }
