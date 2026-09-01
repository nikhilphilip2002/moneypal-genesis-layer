from __future__ import annotations

import pytest

from app.services.nlq.contracts import DrillStep, Period, QuerySpec
from app.services.workbench import suggestions
from tests.workbench.conftest import FakeLLM


def _step(step_id: str, label: str) -> DrillStep:
    return DrillStep(
        kind="deeper", id=step_id, label=label, question=f"question for {label}",
        dimension=step_id.split(":", 1)[-1],
        spec=QuerySpec(metrics=["loan_count"], period=Period(relative="all_time")),
    )


@pytest.mark.anyio
async def test_model_can_rank_and_relabel_only_governed_steps():
    original = [_step("deeper:branch", "By branch"), _step("deeper:product", "By product")]
    client = FakeLLM(
        '{"suggestions":['
        '{"id":"deeper:product","label":"Compare product contribution"},'
        '{"id":"deeper:branch","label":"Find leading branches"}]}'
    )

    result = await suggestions.personalize(
        question="How many loans were sanctioned?", summary="5,753 loans", steps=original,
        client=client,
    )

    assert [step.id for step in result] == ["deeper:product", "deeper:branch"]
    assert [step.label for step in result] == [
        "Compare product contribution", "Find leading branches",
    ]
    assert result[0].spec == original[1].spec


@pytest.mark.anyio
async def test_unknown_model_actions_are_discarded_without_losing_fallback():
    original = [_step("deeper:branch", "By branch"), _step("deeper:product", "By product")]
    client = FakeLLM('{"suggestions":[{"id":"delete:data","label":"Delete data"}]}')

    result = await suggestions.personalize(
        question="q", summary="s", steps=original, client=client,
    )

    assert result == original
