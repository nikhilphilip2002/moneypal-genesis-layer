"""Durable conversation history. In the test environment no database is configured, so these
exercise the in-memory fallback — the same code path a dev box runs — and pin the semantics:
the title comes from the first question, turns accumulate, and recency ordering is correct.
"""

from __future__ import annotations

import json

import pytest

from app.services.workbench import history


@pytest.fixture(autouse=True)
def _memory_only(monkeypatch):
    # Force the in-memory path so these are deterministic and independent of whatever
    # database happens to be reachable. The Postgres path mirrors the same semantics and is
    # covered by integration, not this unit suite.
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    history._MEMORY.clear()
    yield
    history._MEMORY.clear()


def test_first_turn_titles_the_conversation_from_the_question():
    history.record_turn("c1", "What was our disbursement last quarter?", ["db"])
    rec = history.get("c1")
    assert rec is not None
    assert rec.title.startswith("What was our disbursement")
    assert len(rec.turns) == 1
    assert rec.turns[0]["sources"] == ["db"]


def test_later_turns_accumulate_and_keep_the_title():
    history.record_turn("c1", "First question about the book", ["db"])
    history.record_turn("c1", "and by branch?", ["db"])
    rec = history.get("c1")
    assert rec.title.startswith("First question")
    assert len(rec.turns) == 2


def test_list_recent_orders_by_most_recently_updated():
    history.record_turn("a", "alpha", ["db"])
    history.record_turn("b", "bravo", ["macro"])
    history.record_turn("a", "alpha follow-up", ["db"])  # touches 'a' last
    recent = history.list_recent()
    assert [c.conversation_id for c in recent] == ["a", "b"]
    assert recent[0].turn_count == 2


def test_list_recent_respects_the_limit():
    for i in range(5):
        history.record_turn(f"c{i}", f"q{i}", ["db"])
    assert len(history.list_recent(limit=3)) == 3


def test_get_unknown_conversation_is_none():
    assert history.get("nope") is None


def test_complete_cards_are_saved_and_become_assistant_context():
    turn_id = history.begin_turn("c1", "alice", "What is PAR 30?")
    history.set_route("c1", "alice", turn_id, sources=["db"], intent="What is PAR 30?")
    history.add_card("c1", "alice", turn_id, {
        "source": "db",
        "card_type": "chart",
        "payload": {
            "title": "PAR 30",
            "chart_type": "kpi",
            "columns": [{"name": "par_30", "label": "PAR 30"}],
            "rows": [{"par_30": 4.2}],
            "summary": "PAR 30 is 4.2%.",
            "lineage": {"sql": "must not enter model context"},
        },
    })
    history.complete_turn("c1", "alice", turn_id)

    rec = history.get("c1", user="alice")
    assert rec is not None and rec.turns[0]["cards"][0]["payload"]["title"] == "PAR 30"
    messages = history.transcript("c1", user="alice")
    assert messages[-2] == {"role": "user", "content": "What is PAR 30?"}
    assert "PAR 30 is 4.2%" in messages[-1]["content"]
    assert "Chart context: type=kpi; fields=par_30" in messages[-1]["content"]
    assert "must not enter model context" not in messages[-1]["content"]


def test_conversations_and_context_are_isolated_by_user():
    history.record_turn("alice-chat", "Alice question", ["db"], user="alice")
    history.record_turn("bob-chat", "Bob question", ["db"], user="bob")

    assert history.get("bob-chat", user="alice") is None
    assert [item.conversation_id for item in history.list_recent(user="alice")] == ["alice-chat"]
    assert history.transcript("bob-chat", user="alice") == []


def test_new_conversation_starts_with_empty_context():
    history.record_turn("old", "Old question", ["db"], user="alice")
    assert history.transcript("new", user="alice") == []


def test_transcript_respects_the_token_budget():
    for index in range(12):
        turn_id = history.begin_turn("long", "alice", f"Question {index} " + "q" * 100)
        history.add_card("long", "alice", turn_id, {
            "source": "macro", "card_type": "brief",
            "payload": {"summary": f"Answer {index} " + "a" * 600},
        })
        history.complete_turn("long", "alice", turn_id)

    # ~1000 tokens: room for a couple of these turns, not twelve.
    messages = history.transcript("long", user="alice", token_budget=1_000)
    verbatim = [message for message in messages if message["role"] != "system"]
    assert sum(len(message["content"]) for message in verbatim) <= 4_200
    # The newest turn always survives, whatever the budget.
    assert "Question 11" in messages[-2]["content"]
    assert "Question 0" not in " ".join(message["content"] for message in verbatim)


def test_an_analysis_turn_survives_into_model_context():
    """An analysis carries its whole answer in the findings, not in a row grid. Without a
    branch of its own it flattened to "" — a compacted thread lost the briefing entirely, and
    the follow-up "why is that?" then had nothing to refer back to."""
    turn_id = history.begin_turn("c2", "alice", "How is the business doing?")
    history.set_route("c2", "alice", turn_id, sources=["db"], intent="briefing")
    history.add_card("c2", "alice", turn_id, {
        "source": "db",
        "card_type": "analysis",
        "payload": {
            "id": "portfolio_health",
            "title": "Portfolio health",
            "compose": "briefing",
            "headline": "2 of 4 indicators need attention: PAR 30, NPA ratio.",
            "findings": [
                {"step_id": "par30", "label": "PAR 30", "text": "PAR 30: 14.0%, above 10.0%."},
                {"step_id": "npa", "label": "NPA ratio", "text": "NPA ratio: 8.0%."},
            ],
            "narrative": "Arrears drove the move.",
            "charts": [],
            "warnings": [],
        },
    })
    history.complete_turn("c2", "alice", turn_id)

    context = history.transcript("c2", user="alice")[-1]["content"]
    assert "2 of 4 indicators need attention" in context
    assert "PAR 30: 14.0%" in context
    assert "NPA ratio: 8.0%" in context
    assert "Arrears drove the move." in context


def test_a_briefing_turn_survives_into_model_context():
    """A briefing is the answer to "what do I need to know?" and its whole content is the
    signals. Without a branch of its own it flattened to "", and a compacted thread lost the
    morning read entirely — so "why is that?" afterwards had nothing to refer back to."""
    turn_id = history.begin_turn("c3", "alice", "What do I need to know?")
    history.set_route("c3", "alice", turn_id, sources=["db"], intent="briefing")
    history.add_card("c3", "alice", turn_id, {
        "source": "db",
        "card_type": "briefing",
        "payload": {
            "persona": "risk",
            "label": "Credit and Risk",
            "headline": "2 things need attention: PAR 30, NPA ratio.",
            "signals": [
                {"id": "a", "text": "PAR 30 for Aluva is 14.0% — above the alert threshold of 10.0."},
                {"id": "b", "text": "NPA ratio is 8.0% — 3.2 standard deviations from its average."},
            ],
            "analyses": [{"title": "Portfolio health", "headline": "1 of 4 indicators need attention."}],
            "worklists": [],
            "warnings": [],
        },
    })
    history.complete_turn("c3", "alice", turn_id)

    context = history.transcript("c3", user="alice")[-1]["content"]
    assert "2 things need attention" in context
    assert "PAR 30 for Aluva is 14.0%" in context
    assert "Portfolio health" in context


def test_native_transcript_replays_only_complete_call_result_groups():
    turn_id = history.begin_turn("native", "alice", "Show PAR 30")
    assistant = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call_1", "type": "function",
            "function": {"name": "query_metrics", "arguments": '{"metrics":["par_30"]}'},
        }],
    }
    tool = {
        "role": "tool", "tool_call_id": "call_1",
        "content": '{"status":"ok","summary":"PAR 30 is 4.2%."}',
    }
    history.add_agent_exchange(
        "native", "alice", turn_id,
        assistant_message=assistant,
        calls=[{"id": "call_1", "name": "query_metrics", "arguments": {"metrics": ["par_30"]}}],
        tool_messages=[tool],
    )
    history.set_answer("native", "alice", turn_id, {"text": "PAR 30 is 4.2%."})
    history.complete_turn("native", "alice", turn_id)

    messages = history.build_native_transcript("native", user="alice")
    assert [message["role"] for message in messages] == [
        "user", "assistant", "tool", "assistant",
    ]
    assert messages[1]["tool_calls"][0]["id"] == "call_1"
    assert messages[2]["tool_call_id"] == "call_1"
    record = history.get("native", user="alice")
    assert record is not None
    events = record.turns[0]["events"]
    assert [event["type"] for event in events] == [
        "user_message",
        "llm_assistant_message",
        "tool_call",
        "tool_result",
        "final_answer",
    ]
    assert events[2]["payload"]["call"]["arguments"] == {"metrics": ["par_30"]}
    assert events[3]["payload"]["message"] == tool


def test_legacy_card_is_retained_as_a_complete_tool_result_event():
    turn_id = history.begin_turn("legacy-event", "alice", "Show all customers")
    card = {
        "source": "db",
        "card_type": "chart",
        "payload": {
            "rows": [{"customer_id": str(index)} for index in range(30)],
            "lineage": {"sql": "SELECT customer_id FROM governed_view"},
        },
    }
    history.add_card("legacy-event", "alice", turn_id, card)
    history.complete_turn("legacy-event", "alice", turn_id)

    record = history.get("legacy-event", user="alice")
    event = record.turns[0]["events"][1]
    assert event["type"] == "tool_result"
    assert event["payload"]["card"] == card


def test_native_transcript_fails_instead_of_silently_dropping_a_complete_exchange():
    turn_id = history.begin_turn("native-overflow", "alice", "Show all rows")
    assistant = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "large_1", "type": "function",
            "function": {"name": "lookup_records", "arguments": "{}"},
        }],
    }
    history.add_agent_exchange(
        "native-overflow", "alice", turn_id,
        assistant_message=assistant,
        calls=[{"id": "large_1", "name": "lookup_records", "arguments": {}}],
        tool_messages=[{
            "role": "tool",
            "tool_call_id": "large_1",
            "content": "x" * 20_000,
        }],
    )
    history.complete_turn("native-overflow", "alice", turn_id)

    with pytest.raises(history.NativeTranscriptOverflow, match="context window"):
        history.build_native_transcript(
            "native-overflow", user="alice", token_budget=100,
        )


def test_named_agent_lookup_call_rows_and_lineage_replay_to_the_followup():
    turn_id = history.begin_turn(
        "vanitha-followup", "alice", "customers under vanitha",
    )
    arguments = {
        "selector": "agent_name",
        "value": "vanitha",
        "detail": "agent_customers",
        "requested_fields": ["borrower_name"],
    }
    assistant = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "lookup_vanitha",
            "type": "function",
            "function": {
                "name": "lookup_records",
                "arguments": json.dumps(arguments),
            },
        }],
    }
    rows = [
        {"customer_id": str(index), "borrower_name": f"Customer {index}"}
        for index in range(30)
    ]
    tool_payload = {
        "status": "ok",
        "source": "db",
        "card_type": "chart",
        "payload": {
            "columns": ["customer_id", "borrower_name"],
            "rows": rows,
        },
        "lineage": {
            "sql": (
                "SELECT customer_id, customer_name FROM gold.semantic_loan_account "
                "WHERE agent_name = :agent_name LIMIT 5000"
            ),
            "params": {"agent_name": "vanitha"},
        },
    }
    tool = {
        "role": "tool",
        "tool_call_id": "lookup_vanitha",
        "content": json.dumps(tool_payload),
    }
    history.add_agent_exchange(
        "vanitha-followup", "alice", turn_id,
        assistant_message=assistant,
        calls=[{
            "id": "lookup_vanitha",
            "name": "lookup_records",
            "arguments": arguments,
        }],
        tool_messages=[tool],
    )
    history.set_answer(
        "vanitha-followup", "alice", turn_id,
        {"text": "Showing 30 linked customers.", "status": "answered"},
    )
    history.complete_turn("vanitha-followup", "alice", turn_id)

    messages = history.build_native_transcript(
        "vanitha-followup", user="alice", token_budget=20_000,
    )

    assert messages[0] == {
        "role": "user", "content": "customers under vanitha",
    }
    replayed_arguments = json.loads(
        messages[1]["tool_calls"][0]["function"]["arguments"]
    )
    assert replayed_arguments == arguments
    replayed_result = json.loads(messages[2]["content"])
    assert replayed_result["payload"]["rows"] == rows
    assert replayed_result["lineage"]["params"] == {"agent_name": "vanitha"}


def test_public_search_arguments_are_redacted_in_durable_native_history():
    turn_id = history.begin_turn("web-native", "alice", "Search the web")
    assistant = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "web_1", "type": "function",
            "function": {
                "name": "search_public_web",
                "arguments": '{"search_query":"customer ID secret-42"}',
            },
        }],
    }
    history.add_agent_exchange(
        "web-native", "alice", turn_id,
        assistant_message=assistant,
        calls=[{
            "id": "web_1", "name": "search_public_web",
            "arguments": {"search_query": "customer ID secret-42"},
        }],
        tool_messages=[{
            "role": "tool", "tool_call_id": "web_1",
            "content": '{"status":"error","code":"PII_POLICY_VIOLATION"}',
        }],
    )
    record = history.get("web-native", user="alice")
    encoded = str(record.turns[0]["agent_exchanges"])
    assert "secret-42" not in encoded
    assert "redacted after policy evaluation" in encoded


def test_lookup_values_feed_session_private_entity_screening():
    turn_id = history.begin_turn("lookup-native", "alice", "Find Asha Rao")
    history.add_agent_exchange(
        "lookup-native", "alice", turn_id,
        assistant_message={
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": "lookup_1", "type": "function",
                "function": {"name": "lookup_records", "arguments": "{}"},
            }],
        },
        calls=[{
            "id": "lookup_1", "name": "lookup_records",
            "arguments": {"selector": "borrower_name", "value": "Asha Rao"},
        }],
        tool_messages=[{
            "role": "tool", "tool_call_id": "lookup_1",
            "content": '{"status":"ok"}',
        }],
    )
    history.complete_turn("lookup-native", "alice", turn_id)

    assert history.private_entities("lookup-native", user="alice") == ("Asha Rao",)
    assert history.private_entities("lookup-native", user="bob") == ()


def test_native_exchange_rejects_unmatched_tool_results():
    turn_id = history.begin_turn("native", "alice", "Show PAR 30")
    with pytest.raises(ValueError, match="every persisted native call"):
        history.add_agent_exchange(
            "native", "alice", turn_id,
            assistant_message={"role": "assistant", "content": None, "tool_calls": []},
            calls=[{"id": "call_1", "name": "query_metrics", "arguments": {}}],
            tool_messages=[],
        )


def test_stored_native_results_replay_bounded_but_are_kept_complete(monkeypatch):
    """History keeps every row; the transcript the model sees is shaped like a live one."""
    from app.services.workbench import agent_executor

    monkeypatch.setattr(
        agent_executor.settings, "workbench_agent_observation_max_chars", 6_000,
        raising=False,
    )
    turn_id = history.begin_turn("bounded-replay", "alice", "customers under vanitha")
    rows = [
        {"customer_id": str(index), "borrower_name": f"Customer {index}"}
        for index in range(2000)
    ]
    assistant = {
        "role": "assistant", "content": None,
        "tool_calls": [{
            "id": "lookup_big", "type": "function",
            "function": {"name": "lookup_records", "arguments": "{}"},
        }],
    }
    history.add_agent_exchange(
        "bounded-replay", "alice", turn_id,
        assistant_message=assistant,
        calls=[{"id": "lookup_big", "name": "lookup_records", "arguments": {}}],
        tool_messages=[{
            "role": "tool", "tool_call_id": "lookup_big",
            "content": json.dumps({
                "status": "ok", "source": "db", "card_type": "chart",
                "payload": {"columns": ["customer_id", "borrower_name"], "rows": rows},
                "summary": "2000 customers.",
            }),
        }],
    )
    history.complete_turn("bounded-replay", "alice", turn_id)

    stored = history.get("bounded-replay", user="alice").turns[-1]
    result_event = next(e for e in stored["events"] if e["type"] == "tool_result")
    stored_rows = json.loads(result_event["payload"]["message"]["content"])
    assert len(stored_rows["payload"]["rows"]) == 2000

    messages = history.build_native_transcript(
        "bounded-replay", user="alice", token_budget=50_000,
    )
    replayed = json.loads(messages[2]["content"])
    assert len(messages[2]["content"]) <= 6_000
    assert 0 < len(replayed["payload"]["rows"]) < 2000
    assert replayed["truncated"]["rows_total"] == 2000
    assert replayed["summary"] == "2000 customers."


# --- Phase C: one history representation ------------------------------------------------


def _assistant_calling(call_id: str, name: str, arguments: str = "{}") -> dict:
    return {
        "role": "assistant", "content": None,
        "tool_calls": [{
            "id": call_id, "type": "function",
            "function": {"name": name, "arguments": arguments},
        }],
    }


def _tool(call_id: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def _types(turn: dict) -> list[str]:
    return [event["type"] for event in turn["events"]]


def test_native_cards_fill_the_history_rail_without_a_second_tool_result_event():
    """The native `tool_result` event already carries the result; the rendered card is
    kept on the turn for the History rail in the same write, with no event of its own."""
    turn_id = history.begin_turn("one-write", "alice", "Show PAR 30")
    card = {"source": "db", "card_type": "chart", "payload": {"rows": [{"par_30": 4.2}]},
            "call_id": "call_1"}
    history.add_agent_exchange(
        "one-write", "alice", turn_id,
        assistant_message=_assistant_calling("call_1", "query_metrics"),
        calls=[{"id": "call_1", "name": "query_metrics", "arguments": {}}],
        tool_messages=[_tool("call_1", '{"status":"ok","summary":"PAR 30 is 4.2%."}')],
        cards=[card],
    )

    turn = history.get("one-write", user="alice").turns[0]
    assert turn["cards"] == [card]
    assert _types(turn).count("tool_result") == 1
    assert turn["events"][3]["payload"]["execution_path"] == "native"


def test_selection_stage_and_nudges_are_stored_but_nudges_are_not_replayed():
    """The event stream is the exact transcript the model saw; what is resent is a
    replay policy, and stored nudges are not resent."""
    turn_id = history.begin_turn("exact", "alice", "Show PAR 30")
    history.add_agent_exchange(
        "exact", "alice", turn_id,
        assistant_message=_assistant_calling("c1", "query_metrics"),
        calls=[{"id": "c1", "name": "query_metrics", "arguments": {}}],
        tool_messages=[_tool("c1", "error: unknown metric")],
        stage="route",
    )
    history.add_system_message(
        "exact", "alice", turn_id, content="Inspect the results above.", kind="nudge",
        stage="continue", round_number=1,
    )
    history.add_agent_exchange(
        "exact", "alice", turn_id,
        assistant_message=_assistant_calling("c2", "query_metrics"),
        calls=[{"id": "c2", "name": "query_metrics", "arguments": {}}],
        tool_messages=[_tool("c2", "PAR 30 is 4.2%.")],
        stage="continue",
    )
    history.set_answer("exact", "alice", turn_id, {"text": "PAR 30 is 4.2%."})
    history.complete_turn("exact", "alice", turn_id)

    turn = history.get("exact", user="alice").turns[0]
    assert _types(turn) == [
        "user_message",
        "llm_assistant_message", "tool_call", "tool_result",
        "system_message",
        "llm_assistant_message", "tool_call", "tool_result",
        "final_answer",
    ]
    assert turn["events"][1]["payload"]["stage"] == "route"
    assert turn["events"][5]["payload"]["stage"] == "continue"
    nudge = turn["events"][4]["payload"]
    assert nudge["kind"] == "nudge" and nudge["synthetic"] is True and nudge["round"] == 1
    assert nudge["message"] == {"role": "user", "content": "Inspect the results above."}

    replay = history.build_native_transcript("exact", user="alice")
    assert [m["role"] for m in replay] == [
        "user", "assistant", "tool", "assistant", "tool", "assistant",
    ]
    assert all(m.get("content") != "Inspect the results above." for m in replay)


def test_nested_text_to_sql_trace_becomes_ordered_child_events_of_the_tool_call():
    turn_id = history.begin_turn("sql-trace", "alice", "Average ticket by branch")
    trace = [
        {"round": 1, "sql": "SELECT 1", "error": "unknown column"},
        {"round": 2, "sql": "SELECT branch, AVG(amount) FROM v", "error": None},
    ]
    content = json.dumps({
        "status": "ok", "summary": "Two branches.",
        "lineage": {"sql": trace[-1]["sql"], "text_to_sql": {"trace": trace}},
    })
    history.add_agent_exchange(
        "sql-trace", "alice", turn_id,
        assistant_message=_assistant_calling("q1", "run_validated_query"),
        calls=[{"id": "q1", "name": "run_validated_query", "arguments": {"question": "avg"}}],
        tool_messages=[_tool("q1", content)],
    )
    history.complete_turn("sql-trace", "alice", turn_id)

    turn = history.get("sql-trace", user="alice").turns[0]
    assert _types(turn) == [
        "user_message", "llm_assistant_message", "tool_call",
        "text_to_sql_attempt", "text_to_sql_attempt", "tool_result",
    ]
    parent = turn["events"][2]
    children = turn["events"][3:5]
    assert [c["payload"]["index"] for c in children] == [0, 1]
    assert all(c["payload"]["parent_sequence"] == parent["sequence"] for c in children)
    assert all(c["payload"]["parent_call_id"] == "q1" for c in children)
    assert [c["payload"]["attempt"] for c in children] == trace
    # The lineage copy inside the result is kept this phase; children are not replayed.
    assert json.loads(turn["events"][5]["payload"]["message"]["content"])["lineage"]["text_to_sql"]
    replay = history.build_native_transcript("sql-trace", user="alice")
    assert [m["role"] for m in replay] == ["user", "assistant", "tool"]


def test_synthesis_candidate_and_final_answer_are_one_event_each():
    turn_id = history.begin_turn("candidate", "alice", "PAR?")
    history.set_synthesis(
        "candidate", "alice", turn_id, "PAR 30 is about 4%.",
        message={"role": "assistant", "content": "PAR 30 is about 4%."},
    )
    history.set_answer("candidate", "alice", turn_id, {"text": "PAR 30 is 4.2%."})
    history.complete_turn("candidate", "alice", turn_id)

    turn = history.get("candidate", user="alice").turns[0]
    assert _types(turn) == ["user_message", "llm_assistant_message", "final_answer"]
    candidate = turn["events"][1]["payload"]
    assert candidate["candidate"] is True and candidate["stage"] == "synthesize"
    assert candidate["message"]["content"] == "PAR 30 is about 4%."
    assert turn["events"][2]["payload"]["answer"]["text"] == "PAR 30 is 4.2%."
    # The compatibility field mirrors the final text; the events keep both.
    assert turn["synthesis"] == "PAR 30 is 4.2%."
    replay = history.build_native_transcript("candidate", user="alice")
    assert [m["content"] for m in replay if m["role"] == "assistant"] == ["PAR 30 is 4.2%."]


def test_legacy_exchange_copy_is_written_only_behind_the_flag(monkeypatch):
    monkeypatch.setattr(history.settings, "workbench_history_write_legacy_exchanges", False)
    turn_id = history.begin_turn("no-legacy", "alice", "PAR?")
    history.add_agent_exchange(
        "no-legacy", "alice", turn_id,
        assistant_message=_assistant_calling("c1", "query_metrics"),
        calls=[{"id": "c1", "name": "query_metrics", "arguments": {}}],
        tool_messages=[_tool("c1", "PAR 30 is 4.2%.")],
    )
    history.complete_turn("no-legacy", "alice", turn_id)

    turn = history.get("no-legacy", user="alice").turns[0]
    assert turn["agent_exchanges"] == []
    assert "tool_call" in _types(turn)
    assert [m["role"] for m in history.build_native_transcript("no-legacy", user="alice")] == [
        "user", "assistant", "tool",
    ]
    assert history.private_entities("no-legacy", user="alice") == ()

    monkeypatch.setattr(history.settings, "workbench_history_write_legacy_exchanges", True)
    turn_id = history.begin_turn("no-legacy", "alice", "Again?")
    history.add_agent_exchange(
        "no-legacy", "alice", turn_id,
        assistant_message=_assistant_calling("c2", "query_metrics"),
        calls=[{"id": "c2", "name": "query_metrics", "arguments": {}}],
        tool_messages=[_tool("c2", "Still 4.2%.")],
    )
    assert len(history.get("no-legacy", user="alice").turns[1]["agent_exchanges"]) == 1


def _compat_replay(turns: list[dict]) -> list[dict]:
    """The replay the pre-v7 compatibility reader produced from the sideways fields:
    question, each exchange's assistant and raw tool messages, then the answer text."""
    messages: list[dict] = []
    for turn in turns:
        group = [{"role": "user", "content": turn["question"]}]
        for exchange in turn.get("agent_exchanges") or []:
            group.append(dict(exchange["assistant"]))
            group.extend(dict(item) for item in exchange["tools"])
        answer = history.assistant_text(turn)
        if answer:
            group.append({"role": "assistant", "content": answer})
        messages.extend(group)
    return messages


def _version_5_record() -> history.ConversationRecord:
    tool_content = "PAR 30 is 4.2% across 12 branches."
    turns = [
        {
            "id": "t1", "question": "Show PAR 30", "route": {"sources": ["db"], "intent": "data"},
            "sources": ["db"], "status": "complete",
            "agent_exchanges": [{
                "assistant": _assistant_calling("c1", "query_metrics", '{"metrics":["par_30"]}'),
                "calls": [{"id": "c1", "name": "query_metrics", "arguments": {"metrics": ["par_30"]}}],
                "tools": [_tool("c1", tool_content)],
            }],
            "cards": [{"source": "db", "card_type": "chart", "payload": {"summary": tool_content}}],
            "synthesis": "PAR 30 is about 4 percent.",
            "answer": {"text": "PAR 30 is 4.2%."},
            "refusal": None, "error": None,
            "created_at": "2025-01-01T00:00:00+00:00", "completed_at": "2025-01-01T00:00:05+00:00",
        },
        {
            "id": "t2", "question": "And by branch?", "route": {"sources": ["db"], "intent": "data"},
            "sources": ["db"], "status": "partial",
            "agent_exchanges": [], "cards": [], "synthesis": None, "answer": None,
            "refusal": None, "error": "The workbench hit an error.",
            "created_at": "2025-01-01T00:01:00+00:00", "completed_at": "2025-01-01T00:01:02+00:00",
        },
    ]
    return history.ConversationRecord(
        conversation_id="v5", owner_username="alice", title="Show PAR 30",
        updated_at=history._now(), turns=turns, record_version=5,
    )


def test_version_5_record_migrates_and_replays_like_the_compatibility_reader():
    record = _version_5_record()
    expected = _compat_replay(record.turns)
    history._MEMORY[("alice", "v5")] = record

    loaded = history.get("v5", user="alice")
    assert [e["type"] for e in loaded.turns[0]["events"]] == [
        "user_message", "route_decision",
        "llm_assistant_message", "tool_call", "tool_result",
        "tool_result",               # the rendered card
        "llm_assistant_message",     # the synthesis candidate, which differed
        "final_answer",
    ]
    assert [e["type"] for e in loaded.turns[1]["events"]] == [
        "user_message", "route_decision", "execution_error",
    ]
    assert all(e["derived"] is True for turn in loaded.turns for e in turn["events"])
    assert loaded.turns[0]["events"][0]["timestamp"] == "2025-01-01T00:00:00+00:00"
    assert loaded.turns[1]["events"][2]["payload"]["message"] == "The workbench hit an error."

    assert history.build_native_transcript("v5", user="alice") == expected
    assert history.private_entities("v5", user="alice") == ()
    assert history.native_tool_calls(loaded.turns[0])[0]["name"] == "query_metrics"

    # The version is a schema signal: it says 7 only once every turn carries events,
    # which the next write establishes.
    history.complete_turn("v5", "alice", "t2")
    assert history.get("v5", user="alice").record_version == history.RECORD_VERSION
    assert history.build_native_transcript("v5", user="alice") == expected


def test_migrate_payload_is_idempotent_and_leaves_v7_turns_alone():
    raw = history._record_payload(_version_5_record())
    raw["version"] = 5

    migrated, changed = history.migrate_payload(json.loads(json.dumps(raw)))
    assert changed == 2 and migrated["version"] == history.RECORD_VERSION
    assert all(history.turn_has_events(turn) for turn in migrated["turns"])
    # Sideways fields are kept for the rollback window; nothing is deleted.
    assert migrated["turns"][0]["agent_exchanges"] == raw["turns"][0]["agent_exchanges"]

    again, changed_again = history.migrate_payload(json.loads(json.dumps(migrated)))
    assert changed_again == 0
    assert again["turns"] == migrated["turns"]


def test_save_refuses_a_record_version_it_does_not_understand():
    record = history.ConversationRecord(
        conversation_id="future", owner_username="alice", title="?",
        updated_at=history._now(), record_version=history.RECORD_VERSION + 1,
    )
    with pytest.raises(history.UnknownRecordVersion, match="record version"):
        history._save(record)
    assert ("alice", "future") not in history._MEMORY


def test_overflow_names_whether_compaction_could_help():
    big = _assistant_calling("big", "lookup_records")
    turn_id = history.begin_turn("reason", "alice", "Everything")
    history.add_agent_exchange(
        "reason", "alice", turn_id, assistant_message=big,
        calls=[{"id": "big", "name": "lookup_records", "arguments": {}}],
        tool_messages=[_tool("big", "x" * 2_000)],
    )
    history.complete_turn("reason", "alice", turn_id)
    with pytest.raises(history.NativeTranscriptOverflow, match="single_turn_exceeds_budget") as one:
        history.build_native_transcript("reason", user="alice", token_budget=100)
    assert one.value.reason == "single_turn_exceeds_budget"

    turn_id = history.begin_turn("reason", "alice", "Again")
    history.set_answer("reason", "alice", turn_id, {"text": "short"})
    history.complete_turn("reason", "alice", turn_id)
    with pytest.raises(history.NativeTranscriptOverflow) as two:
        history.build_native_transcript("reason", user="alice", token_budget=100)
    assert two.value.reason == "conversation_exceeds_budget"


class _FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.updates: list[tuple] = []
        self._selected: list[tuple] = []

    def execute(self, sql, params=None):
        if sql.startswith("UPDATE"):
            self.updates.append(tuple(params))
        else:
            self._selected = [
                (cid, version, payload) for cid, version, payload in self.rows
                if version != params[0] and (len(params) == 1 or cid == params[1])
            ]

    def fetchall(self):
        return list(self._selected)


class _FakeConn:
    def __init__(self):
        self.committed = 0
        self.rolled_back = 0

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


def test_migration_script_reports_on_dry_run_and_writes_only_with_apply(monkeypatch):
    import contextlib
    import importlib.util
    import sys
    from pathlib import Path

    from app.services import db_schema

    path = Path(__file__).resolve().parents[2] / "scripts" / "migrate_history_events.py"
    spec = importlib.util.spec_from_file_location("migrate_history_events", path)
    script = importlib.util.module_from_spec(spec)
    # Registered before execution so the script's dataclass can resolve its
    # postponed annotations through sys.modules, as a normal import would.
    monkeypatch.setitem(sys.modules, spec.name, script)
    spec.loader.exec_module(script)

    raw = history._record_payload(_version_5_record())
    raw["version"] = 5
    current = {"version": 7, "title": "x", "turns": [{"id": "z", "question": "q", "events": [
        {"sequence": 0, "type": "user_message", "payload": {"role": "user", "content": "q"}},
    ]}]}
    rows = [("v5", 5, json.dumps(raw)), ("v6-events", 6, current), ("future", 99, {"turns": []})]
    cursor = _FakeCursor(rows)
    conn = _FakeConn()

    @contextlib.contextmanager
    def fake_db_cursor():
        yield conn, cursor

    monkeypatch.setattr(db_schema, "db_cursor", fake_db_cursor)

    report = script.migrate(apply=False)
    assert (report.scanned, report.migrated, report.turns_changed) == (3, 1, 2)
    assert report.skipped_current == 1
    assert report.refused_unknown_version == ["future (v99)"]
    assert cursor.updates == [] and conn.committed == 0 and conn.rolled_back == 1
    assert "would migrate 1 conversation(s), 2 turn(s)" in report.render(applied=False)

    report = script.migrate(apply=True)
    assert conn.committed == 1
    assert [(u[0], u[2], u[3]) for u in cursor.updates] == [
        (history.RECORD_VERSION, "v5", 5), (history.RECORD_VERSION, "v6-events", 6),
    ]
    written = json.loads(cursor.updates[0][1])
    assert written["version"] == history.RECORD_VERSION
    assert [e["type"] for e in written["turns"][0]["events"]][:3] == [
        "user_message", "route_decision", "llm_assistant_message",
    ]
    assert written["turns"][0]["agent_exchanges"] == raw["turns"][0]["agent_exchanges"]
