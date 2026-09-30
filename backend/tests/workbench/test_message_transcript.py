import json
from contextlib import contextmanager
from copy import deepcopy

import pytest

from app.services.nlq.llm.messages import ChatMessage
from app.services import db_schema
from app.services.workbench import history


@pytest.fixture(autouse=True)
def memory(monkeypatch):
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    history._MEMORY.clear()
    yield
    history._MEMORY.clear()


def test_messages_survive_database_reload_without_rewriting_or_aliasing(
    monkeypatch,
):
    turn = history.begin_turn("c", "u", "question")
    messages: list[ChatMessage] = [
        {"role": "user", "content": "context\n\nquestion  "},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "search_public_web",
                        "arguments": '{ "search_query": "original query" }',
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "result\n "},
        {"role": "assistant", "content": "answer\n\n"},
    ]
    expected = deepcopy(messages)
    history.append_messages("c", "u", turn, messages)
    messages[1]["tool_calls"][0]["function"]["arguments"] = "{}"
    record = history.get("c", user="u")
    assert record is not None
    payload = json.loads(json.dumps(history._record_payload(record)))

    class Cursor:
        def execute(self, *args):
            pass

        def fetchone(self):
            return (
                record.title,
                payload,
                record.updated_at,
                "u",
                history.RECORD_VERSION,
            )

    class Connection:
        def rollback(self):
            pass

    @contextmanager
    def cursor():
        yield Connection(), Cursor()

    monkeypatch.setattr(history, "_ensure_table", lambda: True)
    monkeypatch.setattr(db_schema, "db_cursor", cursor)
    history._MEMORY.clear()
    loaded = history.load_messages("c", user="u")
    assert loaded == expected
    loaded[1]["tool_calls"].clear()
    assert history.load_messages("c", user="u") == expected


def test_version_nine_migration_preserves_original_events_and_model_answer():
    record = history.ConversationRecord(
        "old",
        "question",
        history._now(),
        owner_username="u",
        record_version=9,
        turns=[
            {
                "id": "t",
                "question": "question",
                "status": "complete",
                "answer": {"text": "displayed answer"},
                "events": [
                    {
                        "type": "llm_assistant_message",
                        "payload": {
                            "message": {
                                "role": "assistant",
                                "content": "original answer ",
                            }
                        },
                    }
                ],
            }
        ],
        compaction={"summary": "old checkpoint"},
    )
    original_events = deepcopy(record.turns[0]["events"])
    history._MEMORY[("u", "old")] = record
    assert history.load_messages("old", user="u") == [
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "original answer "},
    ]
    assert record.turns[0]["events"] == original_events
    assert record.migration is not None
    assert record.migration["previous_compaction"] == {
        "summary": "old checkpoint"
    }
    assert record.compaction is None
    assert record.record_version == history.RECORD_VERSION


def test_pending_calls_block_invalid_results_and_are_closed_on_restart():
    turn = history.begin_turn("c", "u", "question")
    assistant: ChatMessage = {
        "role": "assistant",
        "content": "Looking up a customer.",
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {
                    "name": "query",
                    "arguments": json.dumps(
                        {
                            "sql": "SELECT * FROM gold.loan_accounts WHERE borrower_name = 'Asha Rao'"
                        }
                    ),
                },
            }
        ],
    }
    history.append_messages("c", "u", turn, [assistant])
    assert history.private_entities("c", user="u") == ("Asha Rao",)
    assert history.private_entities("c", user="other") == ()
    before = history.load_messages("c", user="u")
    with pytest.raises(ValueError, match="pending"):
        history.append_messages(
            "c", "u", turn, [{"role": "user", "content": "continue"}]
        )
    with pytest.raises(ValueError, match="match"):
        history.append_messages(
            "c",
            "u",
            turn,
            [{"role": "tool", "tool_call_id": "wrong", "content": "x"}],
        )
    assert history.load_messages("c", user="u") == before
    next_turn = history.begin_turn("c", "u", "followup")
    record = history.start_turn_messages(
        "c",
        "u",
        next_turn,
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "followup"},
    )
    assert record.messages[1] == assistant
    assert record.messages[2]["tool_call_id"] == "c1"
    content = record.messages[2]["content"]
    assert isinstance(content, str)
    assert json.loads(content)["code"] == "INTERRUPTED"
    assert history.pending_tool_calls(record.messages) == []
    assert record.turns[0]["status"] == "partial"


@pytest.mark.parametrize("changed_part", [0, 1])
def test_followup_refreshes_system_prompt_and_preserves_history_and_checkpoint(changed_part):
    from app.services.workbench import prompts
    from app.services.workbench.compaction.request import active_messages

    first = history.begin_turn("c", "u", "first")
    system = prompts.build_agent_system_prompt()
    history.start_turn_messages(
        "c", "u", first, system, {"role": "user", "content": "first"},
    )
    history.append_messages("c", "u", first, [{"role": "assistant", "content": "answer "}])
    history.complete_turn("c", "u", first)
    checkpoint = {"cut": 1, "summary": "previous question", "preserved_question": None}
    history.set_checkpoint("c", "u", checkpoint)
    previous = history.load_messages("c", user="u")
    updated = deepcopy(system)
    parts = updated["content"]
    assert isinstance(parts, list)
    parts[changed_part]["text"] += "\nUpdated configuration"

    second = history.begin_turn("c", "u", "second")
    record = history.start_turn_messages(
        "c", "u", second, updated, {"role": "user", "content": "second"},
    )
    assert record.messages[0] == updated
    assert record.messages[1:-1] == previous[1:]
    assert record.turns[-1]["previous_system_message"] == system
    assert record.compaction == checkpoint
    assert active_messages(record.messages, record.compaction)[0] == updated
    assert record.turns[0]["message_start"] == 1
    assert record.turns[0]["message_end"] == 3

    third = history.begin_turn("c", "u", "third")
    record = history.start_turn_messages(
        "c", "u", third, updated, {"role": "user", "content": "third"},
    )
    assert "previous_system_message" not in record.turns[-1]
    assert record.turns[1]["previous_system_message"] == system
