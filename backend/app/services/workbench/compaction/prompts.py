"""Summarization prompts for workbench conversation checkpoints.

Deliberately *not* the coding-agent template. pi summarizes into
``Goal / Progress (Done, In Progress, Blocked) / Next Steps`` because its conversations
are work converging on a finished task. A workbench conversation is an analyst asking
questions about the loan book, macro conditions, competitors and regulation; nothing is
"blocked" and there is no task to finish. The sections below describe an *investigation*
instead, and add one pi has no need for — refusals — because forgetting that a role was
denied data leads the model to re-promise it on the next turn.
"""

from __future__ import annotations

SYSTEM_PROMPT = (
    "You are a context summarization assistant for a banking intelligence console. "
    "Read the conversation and produce a structured checkpoint another model will use "
    "to continue it.\n"
    "Do NOT continue the conversation. Do NOT answer any question that appears in it. "
    "Output only the checkpoint."
)

_FORMAT = """## Line of Enquiry
[What is the analyst investigating? One or two sentences. Multiple items if the conversation covered several.]

## Resolved Context
- [Bindings a follow-up question depends on: which institution, which period, which product or branch filter, which document is pinned]
- [Or "(none)" if nothing has been pinned down]

## Open Threads
- [Questions raised but not yet answered, and comparisons the analyst asked for that are incomplete]
- [Or "(none)"]

## Caveats & Refusals
- [Anything that was refused, unavailable, or came with a stated confidence limit]
- [Or "(none)"]

## Notes
- [Anything else needed to continue that does not fit above]
- [Or "(none)"]"""

_RULES = """
Rules:
- Do NOT restate numeric figures. They are carried separately and exactly; repeating them here risks corrupting them.
- Refer to figures by subject instead ("MSME credit outstanding was established for FY25").
- Preserve exact institution names, metric names, product names and period labels.
- Keep every section short. This is a checkpoint, not a report."""

INITIAL_PROMPT = f"""The messages above are a conversation to summarize. Create a structured checkpoint.

Use this EXACT format:

{_FORMAT}
{_RULES}"""

UPDATE_PROMPT = f"""The messages above are NEW turns to fold into the existing checkpoint given in <previous-checkpoint> tags.

RULES:
- PRESERVE everything from the previous checkpoint that is still true
- ADD what the new turns established
- MOVE items out of "Open Threads" once they have been answered
- REMOVE items that are no longer relevant
- Keep exact institution, metric, product and period names

Use this EXACT format:

{_FORMAT}
{_RULES}"""
