# Workbench rollout and rollback runbook

## Pre-deployment

1. Run the Workbench, NLQ, security, frontend type-check, and production-build suites.
2. Confirm `uv.lock` contains no LangGraph or LangChain packages.
3. Verify new conversations omit or send `external_sources_enabled=false` by default.
4. Verify connector-off requests record zero macro/competitive/regulatory/web attempts.
5. Exercise PostgreSQL MCP discovery and read-only query execution in the target environment.

Build, start, and run the automated smoke verifier on the deployment machine:

```bash
docker compose build backend frontend
docker compose up -d postgres-mcp backend frontend nginx
curl --fail --silent --show-error http://127.0.0.1:48106/api/health
python backend/scripts/verify_workbench_rollout.py \
  --base-url http://127.0.0.1:48106/api \
  --token mock-token-moneypal_admin \
  --include-web \
  --require-llm
```

Pass the FastAPI origin without `/api` when verifying a backend process directly. Pass the
nginx origin with `/api`, as above, because nginx strips that prefix before proxying.
`--require-llm` prevents a false-green rollout while the configured model endpoint is down or
still loading. Runtime readiness checks use status only and do not inspect model names.

The root health payload is non-blocking and reports cached startup state. Before traffic, verify
`workbench.postgres_mcp.status=ok`, `workbench.postgres_mcp.tools=["query"]`, and
`workbench.gold_schema.status=ok`. Run these checks on the deployment machine; they do not require
or imply that a developer workstation can reach the remote containers or database.

The LLM is intentionally hosted outside this Compose stack. Before deploying the app, start
`llama-server` on the private GPU host using the command in `GENESIS_NLQ_RUNBOOK.md` and confirm
its `/health` endpoint from the backend host. Restart the backend after changing `.env`.

Verify that startup discovers the authorized PostgreSQL MCP tools and that Workbench requests
cannot select or fall back to a direct PostgreSQL adapter.

The API, PostgreSQL MCP server, and macro pipeline reuse `moneypal-backend:local`. The
Dockerfile installs CPU-only PyTorch before `genesis-core`, and `.dockerignore` excludes the
local `.venv`; together these prevent the multi-GB CUDA/context pressure that can terminate
BuildKit with `rpc error: ... EOF` on smaller hosts.

## Canary

Deploy to internal users first. Monitor persisted turn telemetry for model calls by purpose,
uncached/cached/cache-write tokens, first-event/first-card/final/total latency, route reason,
fallback frequency, source attempts, partial answers, refusals, connector denials, and errors.
Compare route/citation/numeric outcomes with the saved baseline. Do not expand if safety or
numeric reconciliation regresses.

## Rollback

The data/API change is additive: old clients omit consent and safely receive internal-only
behavior; version 1–3 histories load with consent off. Roll back the application image and
frontend together. No relational migration reversal is needed. If an external connector is
the problem, set `WORKBENCH_EXTERNAL_CONNECTORS_ENABLED=false` immediately; this kill switch
is independent of the per-conversation toggle and model-provider settings.

The retired LangGraph runtime is not a rollback target. Rollback uses the prior application
image; do not restore removed graph packages into the new image.
