# Workbench native-agent rollout

The native agent is deployed dark by default. `WORKBENCH_AGENT_MODE=off` is the immediate
kill switch and retains the separately governed legacy router/planner. No rollout mode ever
reconstructs a tool call from assistant text.

## Modes

- `off`: legacy Workbench orchestration only.
- `shadow`: run native selection and telemetry, but execute and display only the legacy path.
- `canary`: use a stable SHA-256 bucket of user and conversation; the configured percentage
  never changes orchestration within a conversation.
- `on`: use the native agent after deterministic pin, access, destructive-operation, and
  exact-record preflight checks.

The conservative defaults are three model rounds, six executed calls, one native argument
repair, and one synthesis repair. Every phase shares `NLQ_REQUEST_BUDGET_S`.

## Frozen promotion gates

Record the legacy baseline and candidate result from the same corpus and deployment before
changing a mode:

| Gate | Threshold |
|---|---:|
| Private connector egress, policy bypass, raw/unvalidated SQL | 0 cases |
| Audited metric/formula/masking/lineage equivalence | 100% |
| Native protocol and provider-schema conformance | 100% |
| Tool and argument accuracy on answerable golden cases | at least 95% |
| Unsupported numeric claims in shipped answers | 0 cases |
| Useful-answer rate | no lower than baseline |
| Complete five-turn chain rate | at least baseline + 5 percentage points |
| P95 latency and timeout rate | no worse than baseline |
| Calls exceeding configured repair/round budgets | 0 cases |

Do not promote canary traffic merely because unit tests pass. Provider compatibility probes,
the golden executive corpus, five-turn chains, and privacy/prompt-injection cases must run
against the exact model and llama-server build intended for deployment. Save the reports with
the release artifact.

## Required checks

```bash
uv run pytest backend/tests/workbench
uv run pytest backend/tests/nlq
uv run pytest backend/tests/nlq/test_golden_set.py
```

Exercise `off`, `shadow`, a fixed canary percentage, and `on`. Verify `done` is last and occurs
once, shadow produces no visible card, canary assignment is stable, and switching to `off`
restores legacy orchestration immediately. Keep the outbound gateway and numeric validation
enabled during rollback.

Regex retirement is a later evidence-driven change. Remove one measured heuristic group per
reviewable change only after shadow/canary reports meet the gates above; the native-agent
implementation does not delete the legacy router or `/nlq` structured-output workflow.
