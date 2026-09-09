"""Score the deployed model's native tool selection over the evaluation corpora.

Two corpora live under ``tests/workbench/golden``:

* ``agent_questions.yaml``: 120 isolated prompts. Selection only; the chosen database tool
  is never executed.
* ``agent_conversations.yaml``: multi-turn conversations. Each model request states the
  exact transcript shape the model must receive and the structured call (or final text)
  it must return. Tool results are canned in the corpus, so the whole loop runs against
  the live model without a warehouse; scoring compares tool names and structured
  arguments only.

The conversation harness (`transcript_shape`, `CannedExecutor`, `run_conversation`) is the
same code the offline regression test drives with a scripted model, so a live report and
a green test describe the same contract. Run from ``backend`` with the deployment
environment loaded:

    python -m scripts.evaluate_native_agent --help
    python -m scripts.evaluate_native_agent --corpus questions --limit 12
    python -m scripts.evaluate_native_agent --corpus conversations --output docs/eval/ling.json
    python -m scripts.evaluate_native_agent --model /models/qwen.gguf --output docs/eval/qwen.json

The served model is confirmed through ``/v1/models`` before every run; a ``--model`` the
endpoint does not serve refuses to run, and a lock file keeps two evaluations from
sharing the single llama-server.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from app.services.nlq.catalog import get_catalog
from app.services.nlq.llm import LLMResult, NativeToolCall
from app.services.workbench import access, agent, agent_executor, history, models, prompts
from app.services.workbench.results import SourceResult


GOLDEN_DIR = Path(__file__).parents[1] / "tests" / "workbench" / "golden"
DEFAULT_GOLDEN = GOLDEN_DIR / "agent_questions.yaml"
DEFAULT_CONVERSATIONS = GOLDEN_DIR / "agent_conversations.yaml"
EVAL_USER = "eval"
EVAL_ROLE = "admin"

# Failure categories recorded per request and per conversation. Ordered from the
# model's own mistakes to environment failures so a report can be grouped by them.
CATEGORIES = (
    "transcript_shape",   # the model received a transcript other than the one asserted
    "wrong_tool",         # a call with a different function name
    "wrong_arguments",    # the right function, different structured arguments
    "no_call",            # text where a call was expected
    "unexpected_call",    # a call where final text was expected
    "extra_request",      # the model needed more requests than the conversation scripts
    "missing_request",    # the turn ended before every scripted request was made
    "outcome_mismatch",   # the visible outcome (answer/refusal/error) differs
    "budget_exhausted",
    "timeout",
    "policy_denied",
    "protocol_error",
    "execution_error",
)


# --- Isolated question corpus ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PromptCase:
    id: str
    view: str
    prompt: str
    tool: str
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]
    tables: tuple[str, ...]


def load_cases(path: Path) -> list[PromptCase]:
    families = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [
        PromptCase(
            id=f"{family['id']}:{index + 1}",
            view=family["view"],
            prompt=prompt,
            tool=family["tool"],
            metrics=tuple(family.get("metrics", ())),
            dimensions=tuple(family.get("dimensions", ())),
            tables=tuple(family.get("tables", ())),
        )
        for family in families
        for index, prompt in enumerate(family["prompts"])
    ]


def score_call(case: PromptCase, calls: list[Any]) -> tuple[bool, str]:
    if len(calls) != 1:
        return False, f"expected one {case.tool} call, got {[call.name for call in calls]}"
    call = calls[0]
    if call.name != case.tool:
        return False, f"expected {case.tool}, got {call.name}"
    if case.tool == "query_metrics":
        actual_metrics = set(call.arguments.get("metrics", ()))
        actual_dimensions = set(call.arguments.get("dimensions", ()))
        if actual_metrics != set(case.metrics):
            return False, f"metrics expected {case.metrics}, got {sorted(actual_metrics)}"
        if actual_dimensions != set(case.dimensions):
            return False, f"dimensions expected {case.dimensions}, got {sorted(actual_dimensions)}"
    if case.tool == "run_validated_query":
        actual_tables = set(call.arguments.get("tables", ()))
        if actual_tables != set(case.tables):
            return False, f"tables expected {case.tables}, got {sorted(actual_tables)}"
    return True, ""


def _exception_category(exc: BaseException) -> str:
    from app.services.nlq.llm import LLMProtocolError
    from app.services.workbench.agent_tools import AgentToolAccessDenied

    if isinstance(exc, agent.BudgetExhausted):
        return "budget_exhausted"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, AgentToolAccessDenied):
        return "policy_denied"
    if isinstance(exc, LLMProtocolError):
        return "protocol_error"
    return "execution_error"


async def evaluate_questions(cases: list[PromptCase], client: Any) -> dict[str, Any]:
    rows = []
    policy = access.build_policy(role=EVAL_ROLE, external_sources_enabled=True)
    for position, case in enumerate(cases, start=1):
        state = {
            "question": case.prompt,
            "history_messages": [],
            "source_policy": policy,
        }
        started = time.perf_counter()
        category = ""
        try:
            result = await agent.select_calls(state)
            passed, error = score_call(case, result.tool_calls)
            response_model = result.model
            calls = [
                {"name": call.name, "arguments": call.arguments}
                for call in result.tool_calls
            ]
            if not passed:
                category = "wrong_arguments" if any(
                    call.name == case.tool for call in result.tool_calls
                ) else "wrong_tool"
        except Exception as exc:  # noqa: BLE001 - eval records protocol failures
            passed, error, calls = False, f"{type(exc).__name__}: {exc}", []
            response_model = None
            category = _exception_category(exc)
        budget = state.get("_agent_budget")
        row = {
            "id": case.id,
            "view": case.view,
            "prompt": case.prompt,
            "passed": passed,
            "error": error,
            "failure_category": category,
            "calls": calls,
            "response_model": response_model,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "rounds_used": budget.rounds_used if budget is not None else 0,
        }
        rows.append(row)
        marker = "PASS" if passed else "FAIL"
        print(f"[{position}/{len(cases)}] {marker} {case.id}: {error or case.prompt}", flush=True)

    passed = sum(row["passed"] for row in rows)
    return {
        "total": len(rows),
        "passed": passed,
        "accuracy": passed / len(rows) if rows else 0.0,
        "rows": rows,
    }


# --- Conversation corpus: shared harness ------------------------------------------------


def load_conversations(path: Path) -> list[dict[str, Any]]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def response_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
    """The structured calls a scripted response carries (empty for final text)."""
    if "calls" in response:
        return list(response["calls"])
    if "tool" in response:
        return [{
            "id": response["id"], "tool": response["tool"],
            "arguments": response.get("arguments", {}),
            **({"preflight": response["preflight"]} if "preflight" in response else {}),
        }]
    return []


def execute_specs(step: dict[str, Any]) -> list[dict[str, Any] | None]:
    """Canned execution outcomes, one per call of the step's response, by position."""
    spec = step.get("execute")
    if spec is None:
        return []
    return list(spec) if isinstance(spec, list) else [spec]


def transcript_shape(messages: list[dict[str, Any]]) -> list[str]:
    """Reduce a provider message list to the shape the corpus asserts.

    ``system``; ``question:<text>`` for the message carrying this turn's question;
    ``nudge:<kind>`` for an application nudge; ``user:<text>`` for a replayed question;
    ``call:<id>=<name>,...`` for an assistant message with tool calls;
    ``assistant:<text>`` for assistant prose; ``tool:<id>:<status>[:<code>][:truncated]``
    for a tool result. No content other than the question and prior answers is
    inspected, so the shape asserts roles, ids, and typed statuses, never wording.
    """
    nudges = {text: kind for kind, text in agent._NUDGES.items()}
    shape: list[str] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "system":
            shape.append("system")
        elif role == "user":
            text = content if isinstance(content, str) else ""
            if text in nudges:
                shape.append(f"nudge:{nudges[text]}")
            elif "\n\nUSER QUESTION\n" in text:
                shape.append("question:" + text.split("\n\nUSER QUESTION\n", 1)[1])
            else:
                shape.append(f"user:{text}")
        elif role == "assistant":
            calls = message.get("tool_calls") or []
            if calls:
                shape.append("call:" + ",".join(
                    f"{call.get('id')}={(call.get('function') or {}).get('name')}"
                    for call in calls if isinstance(call, dict)
                ))
            else:
                shape.append(f"assistant:{content or ''}")
        elif role == "tool":
            entry = f"tool:{message.get('tool_call_id')}"
            try:
                parsed = json.loads(content) if isinstance(content, str) else None
            except ValueError:
                parsed = None
            if isinstance(parsed, dict):
                entry += f":{parsed.get('status', 'unknown')}"
                if parsed.get("status") == "error" and parsed.get("code"):
                    entry += f":{parsed['code']}"
                truncated = parsed.get("truncated")
                if isinstance(truncated, dict) and truncated.get("reason") == "observation_limit":
                    entry += ":truncated"
            else:
                entry += ":opaque"
            shape.append(entry)
        else:
            shape.append(str(role))
    return shape


def tool_response(*calls: NativeToolCall) -> LLMResult:
    """A provider result carrying native tool calls, as the client would parse it."""
    return LLMResult(
        text="", model="scripted", provider="scripted", tool_calls=list(calls),
        assistant_message={
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": call.id, "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            } for call in calls],
        },
    )


def text_response(text: str) -> LLMResult:
    return LLMResult(
        text=text, model="scripted", provider="scripted",
        assistant_message={"role": "assistant", "content": text},
    )


def scripted_result(response: dict[str, Any]) -> LLMResult:
    calls = response_calls(response)
    if calls:
        return tool_response(*(
            NativeToolCall(id=call["id"], name=call["tool"], arguments=dict(call.get("arguments", {})))
            for call in calls
        ))
    return text_response(str(response.get("text", "")))


class RecordingClient:
    """Records every request and its result; subclasses supply the completion."""

    provider = "scripted"
    model = "scripted"
    supports_native_tools = True

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.results: list[LLMResult] = []
        self.latencies_ms: list[int] = []

    async def _complete(self, kwargs: dict[str, Any]) -> LLMResult:
        raise NotImplementedError

    async def complete(self, **kwargs: Any) -> LLMResult:
        self.requests.append(kwargs)
        started = time.perf_counter()
        try:
            result = await self._complete(kwargs)
        finally:
            self.latencies_ms.append(int((time.perf_counter() - started) * 1000))
        self.results.append(result)
        return result

    async def health(self) -> dict[str, Any]:
        return {"status": "ok", "provider": self.provider, "model": self.model}


class ScriptedClient(RecordingClient):
    """Returns the corpus response for the i-th request of a turn."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        super().__init__()
        self.responses = list(responses)

    async def _complete(self, kwargs: dict[str, Any]) -> LLMResult:
        index = len(self.requests) - 1
        if index >= len(self.responses):
            # The model asked for more rounds than the conversation scripts. Answer
            # with text so the loop ends and the report records an extra request.
            return text_response("")
        return scripted_result(self.responses[index])


class LiveClient(RecordingClient):
    """Delegates to the configured provider client and records what it saw."""

    def __init__(self, inner: Any) -> None:
        super().__init__()
        self.inner = inner
        self.provider = getattr(inner, "provider", "unknown")
        self.model = getattr(inner, "model", "unknown")

    async def _complete(self, kwargs: dict[str, Any]) -> LLMResult:
        return await self.inner.complete(**kwargs)

    async def health(self) -> dict[str, Any]:
        return await self.inner.health()


class CannedExecutionError(RuntimeError):
    """An execution failure the corpus scripts; ``code`` is what the model observes."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _generated_rows(spec: dict[str, Any]) -> list[dict[str, Any]]:
    count = int(spec.get("count", 0))
    return [
        {
            "branch": f"Branch {index % 20:02d}",
            "month": f"{2020 + index // 12 % 6}-{index % 12 + 1:02d}",
            "interest_collected": 1000 + index,
        }
        for index in range(count)
    ]


def canned_card(spec: dict[str, Any]) -> SourceResult:
    payload: dict[str, Any] = {
        "title": spec.get("title", ""),
        "summary": spec.get("summary", ""),
        "columns": list(spec.get("columns", [])),
        "rows": list(spec.get("rows", [])),
    }
    if "generate_rows" in spec:
        payload["rows"] = _generated_rows(spec["generate_rows"])
    return SourceResult(
        source=spec.get("source", "db"),
        card_type=spec.get("card_type", "chart"),
        payload=payload,
        summary=str(spec.get("summary", "")),
        sensitive=True,
        lineage={"sql": spec.get("sql", "SELECT 1")},
    )


class CannedExecutor:
    """Executes calls with the corpus's canned outcomes; records what it received.

    A call is matched to its outcome by the request that produced it (the client's
    latest result) and its position in that response, so the live model's own call
    ids work as well as the scripted ones. ``finish_without_data`` always runs through
    the real executor so the terminal contract is the production one.
    """

    def __init__(self, client: RecordingClient, steps: list[dict[str, Any]]) -> None:
        self.client = client
        self.steps = list(steps)
        self.executed: list[dict[str, Any]] = []

    def _spec_for(self, call: NativeToolCall) -> dict[str, Any] | None:
        index = len(self.client.results) - 1
        if index < 0 or index >= len(self.steps):
            return None
        specs = execute_specs(self.steps[index])
        ids = [item.id for item in self.client.results[index].tool_calls]
        position = ids.index(call.id) if call.id in ids else -1
        if 0 <= position < len(specs):
            return specs[position]
        return None

    async def __call__(self, call: NativeToolCall, ctx: Any) -> agent_executor.ExecutedAgentCall:
        self.executed.append({"id": call.id, "name": call.name, "arguments": call.arguments})
        if call.name == "finish_without_data":
            return await agent_executor.execute_agent_call(call, ctx)
        spec = self._spec_for(call)
        if spec is None:
            raise CannedExecutionError(
                "SOURCE_UNAVAILABLE", "the conversation corpus scripts no result for this call",
            )
        if "raise" in spec:
            failure = spec["raise"]
            raise CannedExecutionError(str(failure["code"]), str(failure.get("message", "")))
        return agent_executor.ExecutedAgentCall(call=call, card=canned_card(spec["card"]))


_SETTING_NAMES = {
    "max_rounds": "workbench_agent_max_rounds",
    "max_calls": "workbench_agent_max_tool_calls",
    "budget_s": "nlq_request_budget_s",
    "argument_repairs": "workbench_agent_argument_repairs",
}


@contextlib.contextmanager
def patched_environment(
    client: RecordingClient, executor: CannedExecutor, overrides: dict[str, Any] | None = None,
):
    """Route model calls to ``client``, tool execution to ``executor``, history to memory."""
    saved_settings = {
        name: getattr(agent.settings, name)
        for name in (_SETTING_NAMES[key] for key in (overrides or {}))
    }
    saved = (models.for_step, agent.execute_agent_call, history._ensure_table)
    try:
        for key, value in (overrides or {}).items():
            setattr(agent.settings, _SETTING_NAMES[key], value)
        models.for_step = lambda *_args, **_kwargs: client  # type: ignore[assignment]
        agent.execute_agent_call = executor  # type: ignore[assignment]
        history._ensure_table = lambda: False  # type: ignore[assignment]
        yield
    finally:
        models.for_step, agent.execute_agent_call, history._ensure_table = saved  # type: ignore[assignment]
        for name, value in saved_settings.items():
            setattr(agent.settings, name, value)


def parse_frames(frames: list[str]) -> list[tuple[str, dict[str, Any]]]:
    parsed = []
    for frame in frames:
        event, data = "", {}
        for line in frame.splitlines():
            if line.startswith("event: "):
                event = line[len("event: "):].strip()
            elif line.startswith("data: "):
                try:
                    data = json.loads(line[len("data: "):])
                except ValueError:
                    data = {}
        parsed.append((event, data))
    return parsed


def visible_outcome(frames: list[str], error: BaseException | None) -> dict[str, Any]:
    """The user-visible end of a turn, in comparable structured form."""
    parsed = parse_frames(frames)
    outcome: dict[str, Any] = {
        "error_cards": [
            str(data.get("code", ""))
            for event, data in parsed
            if event == "source_card" and data.get("card_type") == "error"
        ],
    }
    if error is not None:
        outcome["raises"] = type(error).__name__
        return outcome
    final = next(((event, data) for event, data in reversed(parsed) if event in {"answer", "refusal", "error"}), None)
    if final is None:
        outcome["event"] = None
        return outcome
    event, data = final
    outcome["event"] = event
    outcome["status"] = data.get("status")
    outcome["text"] = data.get("text", data.get("message", ""))
    if "origin" in data:
        outcome["origin"] = data["origin"]
    if data.get("reason") is not None:
        outcome["reason"] = data["reason"]
    outcome["unavailable_types"] = [
        str(item.get("type", "")) for item in data.get("unavailable_sources", []) or []
    ]
    outcome["limitation_sources"] = [
        str(item.get("source", "")) for item in data.get("limitations", []) or []
    ]
    return outcome


def compare_outcome(
    expected: dict[str, Any], actual: dict[str, Any], *, compare_text: bool,
) -> list[str]:
    """Keys named by the corpus that the visible outcome does not satisfy."""
    mismatches = []
    for key, value in expected.items():
        if key == "text" and not compare_text:
            continue
        if actual.get(key) != value:
            mismatches.append(f"{key}: expected {value!r}, got {actual.get(key)!r}")
    return mismatches


def _call_dict(call: NativeToolCall) -> dict[str, Any]:
    return {"id": call.id, "name": call.name, "arguments": call.arguments}


def compare_request(
    step: dict[str, Any], request: dict[str, Any], result: LLMResult,
) -> tuple[str, str]:
    """Classify one model request against its scripted expectation."""
    expected_shape = list(step.get("transcript", []))
    actual_shape = transcript_shape(request.get("messages", []))
    if actual_shape != expected_shape:
        return "transcript_shape", f"expected {expected_shape}, got {actual_shape}"
    if step.get("tool_choice") and request.get("tool_choice") != step["tool_choice"]:
        return "transcript_shape", (
            f"tool_choice expected {step['tool_choice']!r}, got {request.get('tool_choice')!r}"
        )
    expected_calls = response_calls(step.get("response", {}))
    actual_calls = list(result.tool_calls)
    if expected_calls and not actual_calls:
        return "no_call", "the model answered with text where a call was expected"
    if not expected_calls and actual_calls:
        return "unexpected_call", f"the model called {[call.name for call in actual_calls]}"
    if len(expected_calls) != len(actual_calls):
        return "wrong_tool", (
            f"expected {len(expected_calls)} call(s), got {[call.name for call in actual_calls]}"
        )
    for expected, actual in zip(expected_calls, actual_calls):
        if actual.name != expected["tool"]:
            return "wrong_tool", f"expected {expected['tool']}, got {actual.name}"
        if actual.arguments != expected.get("arguments", {}):
            return "wrong_arguments", (
                f"{actual.name}: expected {expected.get('arguments', {})!r}, got {actual.arguments!r}"
            )
    return "", ""


@dataclass
class TurnReport:
    question: str
    turn_id: str
    requests: list[dict[str, Any]] = field(default_factory=list)
    executed: list[dict[str, Any]] = field(default_factory=list)
    persisted_calls: list[dict[str, Any]] = field(default_factory=list)
    expected_outcome: dict[str, Any] = field(default_factory=dict)
    actual_outcome: dict[str, Any] = field(default_factory=dict)
    outcome_mismatches: list[str] = field(default_factory=list)
    error: str = ""
    latency_ms: int = 0
    failure_category: str = ""
    detail: str = ""

    @property
    def passed(self) -> bool:
        return not self.failure_category

    def as_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "passed": self.passed}


@dataclass
class ConversationReport:
    id: str
    turns: list[TurnReport] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(turn.passed for turn in self.turns)

    @property
    def failure_category(self) -> str:
        return next((turn.failure_category for turn in self.turns if not turn.passed), "")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "passed": self.passed,
            "failure_category": self.failure_category,
            "turns": [turn.as_dict() for turn in self.turns],
        }


def _persisted_calls(conversation_id: str, turn_id: str) -> list[dict[str, Any]]:
    record = history.get(conversation_id, user=EVAL_USER)
    if record is None:
        return []
    turn = next((item for item in record.turns if item.get("id") == turn_id), None)
    if turn is None:
        return []
    return [
        {"id": call.get("id"), "name": call.get("name")}
        for event in history.turn_events(turn)
        if event.get("type") == "tool_call"
        for call in [event.get("payload", {}).get("call", {})]
    ]


def _drain(queue: asyncio.Queue) -> list[str]:
    frames = []
    while not queue.empty():
        frames.append(queue.get_nowait())
    return frames


ClientFactory = Callable[[dict[str, Any]], RecordingClient]


async def run_turn(
    conversation_id: str, turn: dict[str, Any], client: RecordingClient,
    overrides: dict[str, Any] | None, *, compare_text: bool,
) -> TurnReport:
    """Drive `agent.run` for one turn of a conversation whose history is in memory."""
    question = str(turn["question"])
    steps = list(turn.get("requests", []))
    turn_id = history.begin_turn(conversation_id, EVAL_USER, question)
    report = TurnReport(question=question, turn_id=turn_id)
    executor = CannedExecutor(client, steps)
    error: BaseException | None = None
    started = time.perf_counter()
    with patched_environment(client, executor, overrides):
        # The same order as graph.run_workbench: the turn exists before the transcript
        # is built, so the running turn is never replayed to itself.
        agent_history = history.build_native_transcript(conversation_id, user=EVAL_USER)
        state: dict[str, Any] = {
            "question": question, "conversation_id": conversation_id,
            "user": EVAL_USER, "role": EVAL_ROLE, "turn_id": turn_id,
            "history_messages": [], "agent_history_messages": agent_history,
            "emit": asyncio.Queue(),
            "source_policy": access.build_policy(role=EVAL_ROLE, external_sources_enabled=True),
            "timing": {
                "started_at": time.perf_counter(), "source_attempts": [],
                "source_completions": [],
            },
        }
        try:
            await agent.run(state)
        except Exception as exc:  # noqa: BLE001 - the outcome records the exception
            error = exc
            report.error = f"{type(exc).__name__}: {exc}"
    report.latency_ms = int((time.perf_counter() - started) * 1000)
    history.complete_turn(conversation_id, EVAL_USER, turn_id, partial=error is not None)
    frames = _drain(state["emit"])
    report.executed = list(executor.executed)
    report.persisted_calls = _persisted_calls(conversation_id, turn_id)

    for index, (request, result) in enumerate(zip(client.requests, client.results)):
        step = steps[index] if index < len(steps) else None
        record: dict[str, Any] = {
            "index": index,
            "purpose": request.get("call_purpose"),
            "tool_choice": request.get("tool_choice"),
            "transcript": transcript_shape(request.get("messages", [])),
            "expected_transcript": list(step.get("transcript", [])) if step else None,
            "calls": [_call_dict(call) for call in result.tool_calls],
            "text": result.text,
            "expected": step.get("response") if step else None,
            "latency_ms": client.latencies_ms[index] if index < len(client.latencies_ms) else None,
            "failure_category": "",
            "detail": "",
        }
        if step is None:
            record["failure_category"], record["detail"] = "extra_request", "no scripted request"
        else:
            record["failure_category"], record["detail"] = compare_request(step, request, result)
        report.requests.append(record)
        if record["failure_category"] and not report.failure_category:
            report.failure_category, report.detail = record["failure_category"], record["detail"]
    if len(client.requests) < len(steps) and not report.failure_category:
        report.failure_category = "missing_request"
        report.detail = f"{len(client.requests)} of {len(steps)} scripted requests were made"

    report.expected_outcome = dict(turn.get("outcome", {}))
    report.actual_outcome = visible_outcome(frames, error)
    report.outcome_mismatches = compare_outcome(
        report.expected_outcome, report.actual_outcome, compare_text=compare_text,
    )
    if report.outcome_mismatches and not report.failure_category:
        report.failure_category = "outcome_mismatch"
        report.detail = "; ".join(report.outcome_mismatches)
    if error is not None and "raises" not in report.expected_outcome and not report.failure_category:
        report.failure_category = _exception_category(error)
        report.detail = report.error
    return report


async def run_conversation(
    conversation: dict[str, Any], client_for_turn: ClientFactory, *, compare_text: bool,
) -> ConversationReport:
    """Run every turn in order with in-memory history so later turns replay earlier ones."""
    history._MEMORY.clear()
    conversation_id = f"eval-{conversation['id']}"
    overrides = dict(conversation.get("settings", {}) or {})
    report = ConversationReport(id=str(conversation["id"]))
    for turn in conversation.get("turns", []):
        client = client_for_turn(turn)
        report.turns.append(await run_turn(
            conversation_id, turn, client, overrides, compare_text=compare_text,
        ))
    return report


def scripted_client_for(turn: dict[str, Any]) -> ScriptedClient:
    return ScriptedClient([step.get("response", {}) for step in turn.get("requests", [])])


async def evaluate_conversations(
    conversations: list[dict[str, Any]], client: Any,
) -> dict[str, Any]:
    rows = []
    for position, conversation in enumerate(conversations, start=1):
        report = await run_conversation(
            conversation, lambda _turn: LiveClient(client), compare_text=False,
        )
        rows.append(report.as_dict())
        marker = "PASS" if report.passed else "FAIL"
        detail = next((turn.detail for turn in report.turns if not turn.passed), "")
        print(
            f"[{position}/{len(conversations)}] {marker} {report.id}"
            f"{': ' + report.failure_category + ' ' + detail if detail else ''}",
            flush=True,
        )
    passed = sum(row["passed"] for row in rows)
    return {
        "total": len(rows),
        "passed": passed,
        "accuracy": passed / len(rows) if rows else 0.0,
        "rows": rows,
    }


# --- Run metadata and guards -------------------------------------------------------------


def commit_hash() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(Path(__file__).parents[2]), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - a report without a hash is still a report
        return "unknown"


class ServedModelMismatch(RuntimeError):
    pass


async def confirm_served_model(
    client: Any, requested: str | None, *, allow_unverified: bool = False,
) -> dict[str, Any]:
    """Read ``/v1/models`` through the client's health probe; refuse a mismatch.

    Returns the health payload with ``served_model`` set to the id this run will
    record. The evaluator never switches server models, so the id must already be
    served; with no ``--model`` the configured id must be served as well.
    """
    health = await client.health()
    served = [str(item) for item in health.get("served_models") or []]
    configured = str(getattr(client, "model", ""))
    target = requested or configured
    if not served:
        if not allow_unverified:
            raise ServedModelMismatch(
                "the endpoint did not report served models through /v1/models "
                f"(health: {health.get('status')} {health.get('detail', '')}); "
                "pass --allow-unverified-model to record the model as unverified"
            )
        health["served_model"] = target
        health["model_verified"] = False
        return health
    if target not in served:
        raise ServedModelMismatch(
            f"model {target!r} is not served; /v1/models reports {', '.join(served)}. "
            "Serve that model first or drop --model; the evaluator never switches models."
        )
    health["served_model"] = target
    health["model_verified"] = True
    return health


@contextlib.contextmanager
def single_run_lock(path: Path):
    """One evaluation at a time against the single llama-server."""
    try:
        handle = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        owner = path.read_text(encoding="utf-8", errors="replace").strip() or "unknown"
        raise SystemExit(
            f"another evaluation holds {path} (started by {owner}); wait for it to finish "
            "or remove the stale lock"
        ) from None
    with os.fdopen(handle, "w", encoding="utf-8") as lock:
        lock.write(f"pid={os.getpid()} started={datetime.now(timezone.utc).isoformat()}")
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


async def evaluate(
    cases: list[PromptCase], conversations: list[dict[str, Any]], *,
    model_override: str | None = None, allow_unverified: bool = False,
) -> dict[str, Any]:
    client = models.for_step("agent", sensitive=True)
    configured_model = client.model
    health = await confirm_served_model(
        client, model_override, allow_unverified=allow_unverified,
    )
    if model_override:
        client.model = model_override
    catalog = get_catalog()
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": commit_hash(),
        "served_model": health["served_model"],
        "model_verified": health["model_verified"],
        "served_models": health.get("served_models", []),
        "requested_model": model_override or configured_model,
        "provider": getattr(client, "provider", "unknown"),
        "prompt_version": prompts.AGENT_PROMPT_VERSION,
        "catalog_version": catalog.version,
        "agent_settings": {
            "max_rounds": agent.settings.workbench_agent_max_rounds,
            "max_tool_calls": agent.settings.workbench_agent_max_tool_calls,
            "argument_repairs": agent.settings.workbench_agent_argument_repairs,
            "observation_max_chars": agent.settings.workbench_agent_observation_max_chars,
            "request_budget_s": agent.settings.nlq_request_budget_s,
        },
        "questions": None,
        "conversations": None,
    }
    try:
        if cases:
            report["questions"] = await evaluate_questions(cases, client)
        if conversations:
            report["conversations"] = await evaluate_conversations(conversations, client)
    finally:
        client.model = configured_model
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--corpus", choices=("questions", "conversations", "all"), default="all",
        help="Which corpus to run (default: all).",
    )
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--conversations", type=Path, default=DEFAULT_CONVERSATIONS)
    parser.add_argument("--view", help="questions: keep only this Gold view")
    parser.add_argument("--family", help="questions: keep only this family id")
    parser.add_argument("--one-per-view", action="store_true")
    parser.add_argument("--limit", type=int, help="cap the number of cases in each corpus")
    parser.add_argument("--conversation", action="append", help="conversation id to run (repeatable)")
    parser.add_argument("--output", type=Path, help="write the JSON report here")
    parser.add_argument(
        "--model",
        help=(
            "OpenAI-compatible model id to send for this evaluation. The endpoint must "
            "already serve it (checked through /v1/models); this never loads or switches "
            "server models."
        ),
    )
    parser.add_argument(
        "--allow-unverified-model", action="store_true",
        help="run even when /v1/models is unavailable; the report marks the model unverified",
    )
    parser.add_argument(
        "--lock", type=Path,
        default=Path(tempfile.gettempdir()) / "moneypal-native-agent-eval.lock",
        help="lock file that keeps two evaluations from sharing the llama-server",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases: list[PromptCase] = []
    conversations: list[dict[str, Any]] = []
    if args.corpus in {"questions", "all"}:
        cases = load_cases(args.golden)
        if args.view:
            cases = [case for case in cases if case.view == args.view]
        if args.family:
            cases = [case for case in cases if case.id.split(":", 1)[0] == args.family]
        if args.one_per_view:
            first_by_view: dict[str, PromptCase] = {}
            for case in cases:
                first_by_view.setdefault(case.view, case)
            cases = list(first_by_view.values())
        if args.limit is not None:
            cases = cases[: max(args.limit, 0)]
    if args.corpus in {"conversations", "all"}:
        conversations = load_conversations(args.conversations)
        if args.conversation:
            wanted = set(args.conversation)
            conversations = [item for item in conversations if item["id"] in wanted]
        if args.limit is not None:
            conversations = conversations[: max(args.limit, 0)]

    with single_run_lock(args.lock):
        try:
            report = asyncio.run(evaluate(
                cases, conversations, model_override=args.model,
                allow_unverified=args.allow_unverified_model,
            ))
        except ServedModelMismatch as exc:
            print(f"refusing to run: {exc}", file=sys.stderr, flush=True)
            return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    lines = [f"model: {report['served_model']} (verified={report['model_verified']})"]
    all_passed = True
    for name in ("questions", "conversations"):
        section = report.get(name)
        if section is None:
            continue
        lines.append(f"{name}: {section['passed']}/{section['total']} = {section['accuracy']:.1%}")
        all_passed = all_passed and section["passed"] == section["total"]
    print("\n".join(lines), flush=True)
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
