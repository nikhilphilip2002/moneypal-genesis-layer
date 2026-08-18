"""Token accounting: measured usage beats estimation, and the threshold behaves."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services.workbench.compaction import budget


def _turn(question: str, answer: str, prompt_tokens: int | None = None):
    turn = {"id": "t", "question": question, "synthesis": answer, "status": "complete"}
    if prompt_tokens is not None:
        turn["usage"] = {"prompt_tokens": prompt_tokens, "completion_tokens": 20}
    return turn


def _answer_of(turn):
    return turn.get("synthesis") or ""


class TestEstimation:
    def test_empty_text_is_free(self):
        assert budget.estimate_tokens("") == 0

    def test_estimate_is_conservative(self):
        # chars/4 rounds up: 10 chars must not be reported as 2 tokens.
        assert budget.estimate_tokens("a" * 10) == 3

    def test_estimates_everything_when_no_turn_was_measured(self):
        turns = [_turn("q" * 40, "a" * 40), _turn("q" * 40, "a" * 40)]

        assert budget.transcript_tokens(turns, _answer_of) == 40  # 4 * ceil(80/4) / 2


class TestMeasuredUsage:
    def test_prefers_the_last_measured_prompt(self):
        turns = [
            _turn("old", "old answer"),
            _turn("measured", "measured answer", prompt_tokens=5000),
        ]

        # The measured prompt subsumes everything before it. Its own answer was the
        # completion, not part of that prompt, so it is added back on top.
        answer = budget.estimate_tokens("measured answer")
        assert budget.transcript_tokens(turns, _answer_of) == 5000 + answer

    def test_adds_estimates_for_turns_after_the_measurement(self):
        turns = [
            _turn("measured", "measured answer", prompt_tokens=5000),
            _turn("q" * 40, "a" * 40),
        ]

        answer = budget.estimate_tokens("measured answer")
        assert budget.transcript_tokens(turns, _answer_of) == 5000 + answer + 20

    def test_the_measured_turns_own_answer_is_counted(self):
        """Otherwise every estimate is short by exactly one assistant message."""
        short = [_turn("q", "tiny", prompt_tokens=5000)]
        long = [_turn("q", "a" * 4000, prompt_tokens=5000)]

        assert budget.transcript_tokens(long, _answer_of) > budget.transcript_tokens(short, _answer_of)

    def test_ignores_zero_and_malformed_usage(self):
        turns = [_turn("q" * 40, "a" * 40)]
        turns[0]["usage"] = {"prompt_tokens": 0}

        assert budget.transcript_tokens(turns, _answer_of) == 20

        turns[0]["usage"] = "not a dict"
        assert budget.transcript_tokens(turns, _answer_of) == 20


class TestThreshold:
    @pytest.fixture(autouse=True)
    def _enable(self, monkeypatch):
        monkeypatch.setattr(settings, "workbench_compaction_enabled", True)
        monkeypatch.setattr(settings, "workbench_context_window", 32768)
        monkeypatch.setattr(settings, "workbench_reserve_tokens", 8192)

    def test_budget_reserves_headroom(self):
        assert budget.budget_tokens() == 32768 - 8192

    def test_short_conversation_does_not_compact(self):
        assert budget.should_compact([_turn("hi", "hello", prompt_tokens=100)], _answer_of) is False

    def test_over_budget_conversation_compacts(self):
        over = budget.budget_tokens() + 1
        assert budget.should_compact([_turn("q", "a", prompt_tokens=over)], _answer_of) is True

    def test_disabled_flag_wins(self, monkeypatch):
        monkeypatch.setattr(settings, "workbench_compaction_enabled", False)
        over = budget.budget_tokens() + 1

        assert budget.should_compact([_turn("q", "a", prompt_tokens=over)], _answer_of) is False

    def test_reserve_larger_than_window_yields_zero_not_negative(self, monkeypatch):
        monkeypatch.setattr(settings, "workbench_reserve_tokens", 99999)

        assert budget.budget_tokens() == 0
