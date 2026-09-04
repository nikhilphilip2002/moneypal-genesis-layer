"""Context-aware labels and ordering for governed chart follow-ups.

The model may choose and phrase an action, but it cannot create one. Every returned id must
refer to a DrillStep already built and compiler-checked by the NLQ drill graph; the original
QuerySpec is copied back onto the suggestion after generation.
"""

from __future__ import annotations

import json

from app.services.nlq.contracts import DrillStep

_SYSTEM = (
    "Choose the most useful next questions for a bank analyst from the supplied allowed "
    "actions. Rank them using the user's question and the result summary. Rewrite each "
    "chip label as a concise, specific action (maximum 6 words). Do not answer the question, "
    "invent an action, add a number, or mention an id. Return JSON only."
)


async def personalize(
    *, question: str, summary: str, steps: list[DrillStep], client, limit: int = 4,
) -> list[DrillStep]:
    """Return model-ranked safe steps, or the original steps on any unusable output."""
    if len(steps) < 2:
        return steps
    by_id = {step.id: step for step in steps}
    schema = {
        "title": "ContextualNextSteps",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "suggestions": {
                "type": "array",
                "minItems": 1,
                "maxItems": min(limit, len(steps)),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string", "enum": list(by_id)},
                        "label": {"type": "string", "minLength": 2, "maxLength": 48},
                    },
                    "required": ["id", "label"],
                },
            },
        },
        "required": ["suggestions"],
    }
    allowed = [
        {"id": step.id, "label": step.label, "question": step.question}
        for step in steps
    ]
    result = await client.complete(
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": (
                f"User question: {question}\nResult summary: {summary}\n"
                f"Allowed actions: {json.dumps(allowed, ensure_ascii=False)}"
            )},
        ],
        json_schema=schema,
        call_purpose="suggestions",
        prompt_version="workbench-suggestions-v1",
    )
    payload = result.json()
    proposed = payload.get("suggestions", []) if isinstance(payload, dict) else []
    selected: list[DrillStep] = []
    seen: set[str] = set()
    for item in proposed:
        if not isinstance(item, dict):
            continue
        step_id = str(item.get("id", ""))
        label = " ".join(str(item.get("label", "")).split()).strip(" .")
        if step_id not in by_id or step_id in seen or not (2 <= len(label) <= 48):
            continue
        seen.add(step_id)
        selected.append(by_id[step_id].model_copy(update={"label": label}))
    return selected or steps


__all__ = ["personalize"]
