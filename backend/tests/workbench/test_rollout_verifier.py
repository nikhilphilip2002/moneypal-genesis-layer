"""The deployment verifier must not confuse fallback behavior with LLM readiness."""

import pytest

from scripts.verify_workbench_rollout import assert_required_llm


def test_accepts_ready_llamacpp_with_matching_served_model():
    assert_required_llm({
        "capabilities": {"ask": True},
        "llm": {
            "status": "ok",
            "provider": "llamacpp",
            "model": "qwen-9b",
            "served_models": ["qwen-9b"],
            "model_match": True,
        },
    })


@pytest.mark.parametrize(
    "health",
    [
        {
            "capabilities": {"ask": False},
            "llm": {"status": "down", "provider": "llamacpp", "model": "qwen-9b"},
        },
        {
            "capabilities": {"ask": True},
            "llm": {
                "status": "ok", "provider": "llamacpp", "model": "qwen-9b",
                "model_match": None,
            },
        },
        {
            "capabilities": {"ask": True},
            "llm": {
                "status": "degraded", "provider": "llamacpp", "model": "qwen-9b",
                "served_models": ["qwen-35b"], "model_match": False,
            },
        },
    ],
)
def test_rejects_unavailable_unproven_or_mismatched_llamacpp(health):
    with pytest.raises(AssertionError, match="LLM is not ready"):
        assert_required_llm(health)


def test_accepts_ready_non_llamacpp_provider_without_model_identity_extension():
    assert_required_llm({
        "capabilities": {"ask": True},
        "llm": {"status": "ok", "provider": "groq", "model": "hosted-model"},
    })
