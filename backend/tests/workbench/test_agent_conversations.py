"""Multi-turn regression conversations for the native agent (plan.md section 8, F.1).

Each conversation in ``golden/agent_conversations.yaml`` scripts the model: the fake
provider returns the corpus's structured call for every request, and the test asserts
what the application did with it — the exact transcript shape the model received on
every request, that the call reached the executor and the record unchanged, and the
visible outcome on the emit queue. History lives in memory, so turn two replays the
stored exchange of turn one exactly as production would. The same harness runs the
corpus against a live model in ``scripts.evaluate_native_agent``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.nlq.catalog import get_catalog
from app.services.workbench import access, agent, history
from app.services.workbench.agent_tools import (
    AgentToolArgumentsInvalid,
    AgentToolNotFound,
    validate_agent_arguments,
)
from scripts import evaluate_native_agent as harness


GOLDEN = Path(__file__).parent / "golden" / "agent_conversations.yaml"
CONVERSATIONS = harness.load_conversations(GOLDEN)
_PREFLIGHT_ERRORS = {
    "INVALID_TOOL_ARGUMENTS": AgentToolArgumentsInvalid,
    "TOOL_NOT_FOUND": AgentToolNotFound,
}


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 5)
    monkeypatch.setattr(agent.settings, "workbench_agent_max_tool_calls", 6)
    monkeypatch.setattr(agent.settings, "nlq_request_budget_s", 60.0)
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    history._MEMORY.clear()
    yield
    history._MEMORY.clear()


def _conversation(conversation_id: str) -> dict:
    return next(item for item in CONVERSATIONS if item["id"] == conversation_id)


def _expected_calls(step: dict) -> list[dict]:
    return harness.response_calls(step.get("response", {}))


def _executable_calls(step: dict) -> list[dict]:
    """The calls of a step that must pass preflight and reach the executor."""
    return [call for call in _expected_calls(step) if "preflight" not in call]


# --- Corpus integrity --------------------------------------------------------------------


def test_corpus_covers_every_required_scenario():
    ids = {item["id"] for item in CONVERSATIONS}
    assert ids >= {
        "interest_collected_scheme_wise", "interest_collected_branch_wise",
        "interest_collected_product_wise", "interest_collected_month_wise",
        "vanitha_customers_then_tenure_and_sanction",
        "change_then_remove_filter", "change_period_keep_constraints",
        "drill_from_aggregate_to_accounts", "misspelled_santioned",
        "forged_continuation_tool", "rounds_budget_exhausted",
        "calls_budget_exhausted_after_data", "deadline_exhausted",
        "multiple_invalid_calls_one_response", "invalid_sql_then_model_correction",
        "large_result_then_follow_up", "model_refusal_then_follow_up",
    }
    assert len(ids) == len(CONVERSATIONS)


def test_expected_calls_use_only_governed_catalog_ids():
    """Every scripted call either validates against the real catalog and policy or is
    marked with the exact typed preflight error the application must return."""
    catalog = get_catalog()
    policy = access.build_policy(role="admin", external_sources_enabled=True)
    failures = []
    for conversation in CONVERSATIONS:
        for turn in conversation["turns"]:
            for step in turn.get("requests", []):
                for call in _expected_calls(step):
                    expected_error = _PREFLIGHT_ERRORS.get(call.get("preflight", ""))
                    try:
                        validate_agent_arguments(
                            call["tool"], call.get("arguments", {}),
                            policy=policy, catalog=catalog,
                        )
                    except Exception as exc:  # noqa: BLE001 - classified below
                        if expected_error is None or not isinstance(exc, expected_error):
                            failures.append((conversation["id"], call["id"], repr(exc)))
                    else:
                        if expected_error is not None:
                            failures.append((conversation["id"], call["id"], "validated"))
    assert not failures


def test_every_scripted_step_has_one_execution_outcome_per_executable_call():
    failures = []
    for conversation in CONVERSATIONS:
        for turn in conversation["turns"]:
            for index, step in enumerate(turn.get("requests", [])):
                calls = _expected_calls(step)
                specs = harness.execute_specs(step)
                executable = [
                    call for call in calls
                    if "preflight" not in call and call["tool"] != "finish_without_data"
                ]
                if specs and len(specs) != len(calls):
                    failures.append((conversation["id"], index, "execute entries must match calls"))
                if executable and not specs and step is not turn["requests"][-1]:
                    failures.append((conversation["id"], index, "executable call without result"))
                for spec in specs:
                    if spec is not None and not ({"card", "raise"} & set(spec)):
                        failures.append((conversation["id"], index, "execute needs card or raise"))
    assert not failures


def test_transcript_shape_is_structural_and_reversible_for_every_role():
    shaped = harness.transcript_shape([
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "customers under vanitha"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "a", "type": "function", "function": {"name": "lookup_records", "arguments": "{}"}},
        ]},
        {"role": "tool", "tool_call_id": "a", "content": '{"status":"ok","payload":{}}'},
        {"role": "tool", "tool_call_id": "b", "content": '{"status":"error","code":"TOOL_NOT_FOUND"}'},
        {"role": "tool", "tool_call_id": "c", "content": '{"status":"ok","truncated":{"reason":"observation_limit"}}'},
        {"role": "assistant", "content": "Listed."},
        {"role": "user", "content": "CATALOG\n\nUSER QUESTION\ninclude tenure"},
        {"role": "user", "content": agent._NUDGES["auto"]},
    ])
    assert shaped == [
        "system", "user:customers under vanitha", "call:a=lookup_records",
        "tool:a:ok", "tool:b:error:TOOL_NOT_FOUND", "tool:c:ok:truncated",
        "assistant:Listed.", "question:include tenure", "nudge:auto",
    ]


# --- Driving the agent through every conversation ----------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    "conversation_id", [item["id"] for item in CONVERSATIONS],
)
async def test_conversation(conversation_id):
    conversation = _conversation(conversation_id)
    report = await harness.run_conversation(
        conversation, harness.scripted_client_for, compare_text=True,
    )
    assert len(report.turns) == len(conversation["turns"])
    for turn_spec, turn in zip(conversation["turns"], report.turns):
        steps = turn_spec.get("requests", [])
        # One model request per scripted step, no more and no fewer.
        assert [record["transcript"] for record in turn.requests] == [
            step["transcript"] for step in steps
        ], turn.detail
        assert [record["tool_choice"] for record in turn.requests] == [
            step["tool_choice"] for step in steps
        ]
        assert not any(record["failure_category"] for record in turn.requests), turn.detail
        # The structured call reached the executor exactly as the model wrote it, and
        # only calls that pass preflight ever reached it.
        expected_executed = [
            {"id": call["id"], "name": call["tool"], "arguments": call.get("arguments", {})}
            for step in steps for call in _executable_calls(step)
            if harness.execute_specs(step) or call["tool"] == "finish_without_data"
        ]
        assert turn.executed == expected_executed
        # The record holds every attempted call, failed ones included, in order; only
        # a response the call budget rejected outright (`persisted: false`) is absent.
        assert turn.persisted_calls == [
            {"id": call["id"], "name": call["tool"]}
            for step in steps if step.get("persisted", True)
            for call in _expected_calls(step)
        ]
        assert turn.outcome_mismatches == [], turn.actual_outcome
        assert turn.failure_category == "", turn.detail
    assert report.passed


def test_vanitha_follow_up_keeps_the_agent_constraint_and_identity_fields():
    conversation = _conversation("vanitha_customers_then_tenure_and_sanction")
    first = _expected_calls(conversation["turns"][0]["requests"][0])[0]
    second = _expected_calls(conversation["turns"][1]["requests"][0])[0]
    assert first["tool"] == second["tool"] == "lookup_records"
    for key in ("selector", "value", "detail"):
        assert second["arguments"][key] == first["arguments"][key]
    assert first["arguments"]["selector"] == "agent_name"
    assert first["arguments"]["value"] == "vanitha"
    retained = list(first["arguments"]["requested_fields"])
    assert second["arguments"]["requested_fields"] == [
        *retained, "number_of_emis", "sanction_amount",
    ]
    # The second request replays the first turn's exchange, ids matched to results.
    replay = conversation["turns"][1]["requests"][0]["transcript"]
    assert replay[:4] == [
        "system", "user:customers under vanitha",
        f"call:{first['id']}=lookup_records", f"tool:{first['id']}:ok",
    ]


def test_persisted_exchange_of_turn_one_is_replayed_verbatim_on_turn_two():
    """The transcript turn two receives is the stored exchange, not a re-rendering."""
    import asyncio

    conversation = _conversation("vanitha_customers_then_tenure_and_sanction")
    report = asyncio.run(harness.run_conversation(
        conversation, harness.scripted_client_for, compare_text=True,
    ))
    record = history.get("eval-vanitha_customers_then_tenure_and_sanction", user=harness.EVAL_USER)
    stored = history.native_replay_group(record.turns[0])
    second_request = report.turns[1].requests[0]
    assert harness.transcript_shape(stored) == second_request["transcript"][1:-1]


def test_budget_exhaustion_outcomes_are_typed_not_fabricated():
    import asyncio

    outcomes = {}
    for conversation_id in ("rounds_budget_exhausted", "deadline_exhausted"):
        report = asyncio.run(harness.run_conversation(
            _conversation(conversation_id), harness.scripted_client_for, compare_text=True,
        ))
        outcomes[conversation_id] = report.turns[0]
    rounds = outcomes["rounds_budget_exhausted"]
    assert rounds.actual_outcome["raises"] == "BudgetExhausted"
    assert [record["purpose"] for record in rounds.requests] == ["agent_select", "agent_select"]
    assert rounds.executed == []
    assert [call["name"] for call in rounds.persisted_calls] == ["query_metrics", "query_metrics"]
    deadline = outcomes["deadline_exhausted"]
    assert deadline.actual_outcome["raises"] == "TimeoutError"
    assert deadline.requests == []
    assert deadline.executed == []
