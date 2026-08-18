"""Checkpointing end to end: transcript layering, v2 compatibility, and the safety rails.

In-memory storage only, like the rest of the history suite, and a stubbed summarizer so
nothing here needs a model.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services.workbench import compaction, history


@pytest.fixture(autouse=True)
def _memory_only(monkeypatch):
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    history._MEMORY.clear()
    yield
    history._MEMORY.clear()


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "workbench_compaction_enabled", True)
    monkeypatch.setattr(settings, "workbench_keep_recent_turns", 2)


def _add_turn(cid, user, question, answer, *, sources=("db",), usage=None):
    turn_id = history.begin_turn(cid, user, question)
    history.set_route(cid, user, turn_id, sources=list(sources), intent="data")
    history.add_card(cid, user, turn_id, {
        "source": sources[0], "card_type": "chart",
        "payload": {"title": "Result", "columns": [{"name": "value"}], "rows": [], "summary": answer},
    })
    history.set_synthesis(cid, user, turn_id, answer)
    if usage is not None:
        history.set_usage(cid, user, turn_id, prompt_tokens=usage, completion_tokens=10)
    history.complete_turn(cid, user, turn_id)
    return turn_id


class TestTranscriptLayering:
    def test_recent_turns_are_verbatim(self):
        _add_turn("c1", "u", "What is PAR-30?", "PAR-30 stood at 4.2% in FY25.")

        messages = history.transcript("c1", user="u")

        assert {"role": "user", "content": "What is PAR-30?"} in messages
        assert any(m["role"] == "assistant" and "4.2%" in m["content"] for m in messages)

    def test_session_state_block_is_always_present(self):
        _add_turn("c1", "u", "PAR for FY25?", "PAR-30 stood at 4.2% in FY25.")

        messages = history.transcript("c1", user="u")

        state_blocks = [m for m in messages if "<established-figures>" in m["content"]]
        assert len(state_blocks) == 1
        assert state_blocks[0]["role"] == "system"

    def test_running_turn_is_excluded(self):
        history.begin_turn("c1", "u", "in flight")

        assert history.transcript("c1", user="u") == []

    def test_budget_drops_oldest_turns_but_keeps_the_newest(self, monkeypatch):
        for index in range(10):
            _add_turn("c1", "u", f"question number {index}", f"answer number {index} " * 40)
        # A budget far too small for ten turns.
        messages = history.transcript("c1", user="u", token_budget=120)

        users = [m["content"] for m in messages if m["role"] == "user"]
        assert users, "the most recent turn must always survive"
        assert users[-1] == "question number 9"
        assert "question number 0" not in users

    def test_figures_from_dropped_turns_survive_in_the_state_block(self):
        _add_turn("c1", "u", "PAR in FY25?", "PAR-30 stood at 4.2% in FY25.")
        for index in range(8):
            _add_turn("c1", "u", f"filler {index}", f"nothing numeric here {index} " * 30)

        messages = history.transcript("c1", user="u", token_budget=150)

        users = [m["content"] for m in messages if m["role"] == "user"]
        assert "PAR in FY25?" not in users, "the old turn should have aged out"
        # ...but its figure is still available to the model.
        assert any("4.2%" in m["content"] for m in messages if m["role"] == "system")


class TestContextOverflow:
    """The compressed layers must never crowd out the conversation they summarize."""

    def test_state_block_is_capped_to_a_share_of_the_budget(self):
        # Many turns, each contributing figures, so the state block wants to be large.
        for index in range(40):
            _add_turn("c1", "u", f"metric {index} for FY25?", f"Metric {index} reached {index}.5% in FY25.")

        built = history.build_transcript("c1", user="u", token_budget=400)

        state_blocks = [m for m in built.messages if "<established-figures>" in m["content"]]
        assert state_blocks
        from app.services.workbench.compaction import budget

        assert budget.estimate_tokens(state_blocks[0]["content"]) <= 400 * budget.COMPRESSED_SHARE

    def test_a_long_checkpoint_summary_is_clipped(self):
        _add_turn("c1", "u", "question", "answer")
        history.set_compaction("c1", "u", {
            "summary": "verbose checkpoint. " * 5000,
            "first_kept_turn_id": "",
        })

        built = history.build_transcript("c1", user="u", token_budget=400)

        checkpoint = next(m for m in built.messages if "Conversation checkpoint" in m["content"])
        assert "truncated to fit the context window" in checkpoint["content"]

    def test_oversized_newest_turn_is_clipped_and_flagged(self):
        _add_turn("c1", "u", "a question", "an enormous answer " * 4000)

        built = history.build_transcript("c1", user="u", token_budget=200)

        assert built.overflow is True
        assistant = [m for m in built.messages if m["role"] == "assistant"]
        assert assistant, "the current exchange must survive even when it does not fit"
        assert "truncated to fit the context window" in assistant[0]["content"]

    def test_normal_conversation_does_not_report_overflow(self):
        _add_turn("c1", "u", "a question", "a short answer")

        assert history.build_transcript("c1", user="u").overflow is False

    def test_transcript_stays_within_budget_once_clipped(self):
        _add_turn("c1", "u", "a question", "an enormous answer " * 4000)

        built = history.build_transcript("c1", user="u", token_budget=300)

        from app.services.workbench.compaction import budget

        total = sum(budget.estimate_tokens(m["content"]) for m in built.messages)
        # Clipping is approximate (labels and role overhead are not counted), so allow
        # headroom — the point is that an unbounded turn is now bounded.
        assert total <= 300 * 1.5

    @pytest.mark.parametrize(
        "message",
        [
            "llamacpp rejected the request: the request exceeds the available context size",
            "context length exceeded: 33000 > 32768",
            "Requested tokens exceed maximum context length",
            "n_ctx is too small for this prompt",
        ],
    )
    def test_provider_context_errors_are_recognised(self, message):
        from app.services.workbench.graph import _is_context_overflow

        assert _is_context_overflow(RuntimeError(message)) is True

    def test_ordinary_errors_are_not_mistaken_for_overflow(self):
        from app.services.workbench.graph import _is_context_overflow

        assert _is_context_overflow(RuntimeError("connection refused")) is False
        assert _is_context_overflow(RuntimeError("model did not return JSON")) is False

    def test_refusals_do_not_grow_without_bound(self):
        from app.services.workbench.compaction import state as session_state

        for index in range(30):
            turn_id = history.begin_turn("c1", "u", f"show me PII {index}")
            history.set_route("c1", "u", turn_id, sources=["db"], intent="data")
            history.set_refusal("c1", "u", turn_id, {"message": f"Denied for your role ({index})."})
            history.complete_turn("c1", "u", turn_id)

        record = history.get("c1", user="u")
        state = session_state.from_turns(record.turns, history.assistant_text)

        assert len(state.refusals) == session_state.MAX_REFUSALS
        # The most recent denials are the ones kept.
        assert "29" in state.refusals[-1]


class TestCheckpoint:
    @pytest.mark.anyio
    async def test_writes_and_replaces_older_turns(self, enabled, monkeypatch):
        async def fake_summary(turns, *, assistant_text_of, previous_summary=""):
            return "## Line of Enquiry\nPortfolio quality."

        monkeypatch.setattr(compaction.summarize, "write_checkpoint", fake_summary)
        for index in range(5):
            _add_turn("c1", "u", f"question {index}", f"answer {index}")

        assert await compaction.compact_now("c1", "u") is True

        record = history.get("c1", user="u")
        assert record.compaction["summary"].startswith("## Line of Enquiry")
        assert record.record_version == history.RECORD_VERSION

        messages = history.transcript("c1", user="u")
        assert any("Conversation checkpoint" in m["content"] for m in messages)
        users = [m["content"] for m in messages if m["role"] == "user"]
        assert users == ["question 3", "question 4"], "only the kept window replays"

    @pytest.mark.anyio
    async def test_is_a_noop_when_nothing_new_aged_out(self, enabled, monkeypatch):
        calls = []

        async def fake_summary(turns, *, assistant_text_of, previous_summary=""):
            calls.append(len(turns))
            return "## Line of Enquiry\nX."

        monkeypatch.setattr(compaction.summarize, "write_checkpoint", fake_summary)
        for index in range(5):
            _add_turn("c1", "u", f"question {index}", f"answer {index}")

        assert await compaction.compact_now("c1", "u") is True
        assert await compaction.compact_now("c1", "u") is False
        assert len(calls) == 1

    @pytest.mark.anyio
    async def test_second_checkpoint_only_summarizes_new_turns(self, enabled, monkeypatch):
        seen = []

        async def fake_summary(turns, *, assistant_text_of, previous_summary=""):
            seen.append([t["question"] for t in turns])
            return "## Line of Enquiry\nX."

        monkeypatch.setattr(compaction.summarize, "write_checkpoint", fake_summary)
        for index in range(5):
            _add_turn("c1", "u", f"question {index}", f"answer {index}")
        await compaction.compact_now("c1", "u")
        for index in range(5, 8):
            _add_turn("c1", "u", f"question {index}", f"answer {index}")
        await compaction.compact_now("c1", "u")

        assert seen[0] == ["question 0", "question 1", "question 2"]
        # Incremental: the previously summarized turns are not re-read.
        assert seen[1] == ["question 3", "question 4", "question 5"]

    @pytest.mark.anyio
    async def test_a_tiny_conversation_is_not_summarized_however_many_turns(
        self, enabled, monkeypatch
    ):
        """Turn count alone must not trigger a checkpoint.

        Twenty short turns are still a few hundred tokens; paying for a summarization
        call after every one of them buys nothing.
        """
        called = False

        async def fake_summary(*args, **kwargs):
            nonlocal called
            called = True
            return "## Line of Enquiry\nX."

        monkeypatch.setattr(compaction.summarize, "write_checkpoint", fake_summary)
        for index in range(20):
            _add_turn("c1", "u", f"q{index}", f"a{index}", usage=50)

        assert await compaction.maybe_compact("c1", "u") is False
        assert called is False

    @pytest.mark.anyio
    async def test_conversation_over_budget_is_summarized(self, enabled, monkeypatch):
        async def fake_summary(*args, **kwargs):
            return "## Line of Enquiry\nX."

        monkeypatch.setattr(compaction.summarize, "write_checkpoint", fake_summary)
        monkeypatch.setattr(settings, "workbench_context_window", 1000)
        monkeypatch.setattr(settings, "workbench_reserve_tokens", 500)
        for index in range(10):
            _add_turn("c1", "u", f"q{index}", f"a{index}")
        # Last turn reports a prompt far beyond the 500-token budget.
        _add_turn("c1", "u", "final", "answer", usage=5000)

        assert await compaction.maybe_compact("c1", "u") is True

    @pytest.mark.anyio
    async def test_short_conversation_is_never_checkpointed(self, enabled):
        _add_turn("c1", "u", "only question", "only answer")

        assert await compaction.compact_now("c1", "u") is False

    @pytest.mark.anyio
    async def test_summarizer_failure_leaves_the_record_usable(self, enabled, monkeypatch):
        async def boom(turns, *, assistant_text_of, previous_summary=""):
            raise compaction.summarize.SummarizationError("model unavailable")

        monkeypatch.setattr(compaction.summarize, "write_checkpoint", boom)
        for index in range(5):
            _add_turn("c1", "u", f"question {index}", f"answer {index}")

        # maybe_compact swallows; the transcript still works from turns alone.
        assert await compaction.maybe_compact("c1", "u") is False
        record = history.get("c1", user="u")
        assert record.compaction is None
        assert history.transcript("c1", user="u")

    @pytest.mark.anyio
    async def test_disabled_flag_skips_entirely(self, monkeypatch):
        monkeypatch.setattr(settings, "workbench_compaction_enabled", False)
        called = False

        async def fake_summary(*args, **kwargs):
            nonlocal called
            called = True
            return "x"

        monkeypatch.setattr(compaction.summarize, "write_checkpoint", fake_summary)
        for index in range(5):
            _add_turn("c1", "u", f"question {index}", f"answer {index}")

        assert await compaction.maybe_compact("c1", "u") is False
        assert called is False

    @pytest.mark.anyio
    async def test_dropping_the_checkpoint_restores_full_replay(self, enabled, monkeypatch):
        async def fake_summary(turns, *, assistant_text_of, previous_summary=""):
            return "## Line of Enquiry\nX."

        monkeypatch.setattr(compaction.summarize, "write_checkpoint", fake_summary)
        for index in range(5):
            _add_turn("c1", "u", f"question {index}", f"answer {index}")
        await compaction.compact_now("c1", "u")

        history.set_compaction("c1", "u", None)

        users = [m["content"] for m in history.transcript("c1", user="u") if m["role"] == "user"]
        assert users == [f"question {i}" for i in range(5)]


class TestRecordVersioning:
    def test_v2_record_without_compaction_still_loads(self):
        _add_turn("c1", "u", "question", "answer")
        record = history.get("c1", user="u")
        record.record_version = 2
        record.compaction = None
        history._MEMORY[("u", "c1")] = record

        assert history.transcript("c1", user="u")

    def test_unknown_first_kept_pointer_falls_back_to_full_replay(self):
        _add_turn("c1", "u", "question one", "answer one")
        _add_turn("c1", "u", "question two", "answer two")
        history.set_compaction("c1", "u", {
            "summary": "## Line of Enquiry\nX.",
            "first_kept_turn_id": "a-turn-that-no-longer-exists",
        })

        users = [m["content"] for m in history.transcript("c1", user="u") if m["role"] == "user"]
        assert users == ["question one", "question two"]


class TestSafety:
    @pytest.mark.anyio
    async def test_summarization_is_routed_as_sensitive(self, monkeypatch):
        """A checkpoint can describe loan-book results, so it must stay local."""
        seen: dict = {}

        class FakeClient:
            async def complete(self, **kwargs):
                class Result:
                    text = "## Line of Enquiry\nX."
                    prompt_tokens = 10
                    completion_tokens = 5

                return Result()

        def fake_for_step(step, *, sensitive):
            seen["step"] = step
            seen["sensitive"] = sensitive
            return FakeClient()

        monkeypatch.setattr(compaction.summarize.models, "for_step", fake_for_step)
        turns = [{"id": "t1", "question": "q", "synthesis": "a", "status": "complete"}]

        await compaction.summarize.write_checkpoint(
            turns, assistant_text_of=lambda t: t["synthesis"]
        )

        assert seen["sensitive"] is True

    @pytest.mark.anyio
    async def test_tool_call_response_is_rejected(self, monkeypatch):
        class FakeClient:
            async def complete(self, **kwargs):
                class Result:
                    text = '{"tool_calls": [{"name": "read"}]}'
                    prompt_tokens = 10
                    completion_tokens = 5

                return Result()

        monkeypatch.setattr(
            compaction.summarize.models, "for_step", lambda step, *, sensitive: FakeClient()
        )
        turns = [{"id": "t1", "question": "q", "synthesis": "a", "status": "complete"}]

        with pytest.raises(compaction.summarize.SummarizationError):
            await compaction.summarize.write_checkpoint(
                turns, assistant_text_of=lambda t: t["synthesis"]
            )

    @pytest.mark.anyio
    async def test_empty_response_is_rejected(self, monkeypatch):
        class FakeClient:
            async def complete(self, **kwargs):
                class Result:
                    text = "   "
                    prompt_tokens = 10
                    completion_tokens = 5

                return Result()

        monkeypatch.setattr(
            compaction.summarize.models, "for_step", lambda step, *, sensitive: FakeClient()
        )
        turns = [{"id": "t1", "question": "q", "synthesis": "a", "status": "complete"}]

        with pytest.raises(compaction.summarize.SummarizationError):
            await compaction.summarize.write_checkpoint(
                turns, assistant_text_of=lambda t: t["synthesis"]
            )
