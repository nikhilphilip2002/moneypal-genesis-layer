"""Model routing policy for the workbench.

Completely local by default. Every step of the orchestrator asks this module which client
to use; `local_only` forces the llama.cpp provider everywhere, which is the whole point of
the privacy posture — loan-book data never leaves the machine.

Groq is not deleted, only fenced. It is reachable only when a deployment opts in
(`WORKBENCH_GROQ_OPT_IN`) *and* the step is one whose inputs are public — macro,
competitive and regulatory synthesis over already-published documents. A DB step, whose
prompt carries figures from the warehouse, can never be sent to Groq from here; the policy
refuses rather than trusting the caller to remember.

The existing `get_llm_client` (grammar-guaranteed JSON on llama.cpp) is kept as the actual
LLM implementation — this module only picks which one, never how it talks.
"""

from __future__ import annotations

from typing import Literal

from app.core.config import settings
from app.services.nlq.llm import get_llm_client
from app.services.nlq.llm.client import OpenAICompatibleClient

# The steps the orchestrator runs. "route" and "db_plan" must stay local because their
# prompts can contain warehouse-derived context; "synthesize" over public sources may burst
# to Groq when opted in.
Step = Literal["route", "rewrite", "db_plan", "synthesize"]

_PUBLIC_SYNTHESIS_STEPS: frozenset[str] = frozenset({"synthesize"})


def for_step(step: Step, *, sensitive: bool = True) -> OpenAICompatibleClient:
    """Return the LLM client for an orchestrator step.

    `sensitive` marks whether the prompt for this call carries private (loan-book) data.
    A sensitive call is always local. A non-sensitive synthesis call may use Groq, but only
    when the deployment has both left local-only off and opted Groq in.
    """
    if _may_use_groq(step, sensitive):
        return get_llm_client("groq")
    # llama.cpp is the local provider in this codebase; ask for it by name so this holds
    # even when NLQ_LLM_PROVIDER is set to groq for the legacy /nlq path.
    return get_llm_client("llamacpp")


def _may_use_groq(step: Step, sensitive: bool) -> bool:
    if settings.workbench_local_only:
        return False
    if not settings.workbench_groq_opt_in:
        return False
    if sensitive:
        return False
    return step in _PUBLIC_SYNTHESIS_STEPS


def active_mode() -> str:
    """Human-readable mode for the UI badge and the guidebot."""
    if settings.workbench_local_only:
        return "local"
    if settings.workbench_groq_opt_in:
        return "hybrid"
    return "local"
