# Workbench rollout and rollback runbook

## Pre-deployment

1. Run the Workbench, NLQ, security, frontend type-check, and production-build suites.
2. Confirm `uv.lock` contains no LangGraph or LangChain packages.
3. Verify new conversations omit or send `external_sources_enabled=false` by default.
4. Verify connector-off requests record zero macro/competitive/regulatory/web attempts.
5. Exercise direct PostgreSQL and PostgreSQL MCP in the target environment.

Build, start, and run the automated smoke verifier on the deployment machine:

```bash
docker compose build backend postgres-mcp frontend
docker compose up -d postgres-mcp backend frontend nginx
curl --fail --silent --show-error http://127.0.0.1:48106/api/health
python backend/scripts/verify_workbench_rollout.py \
  --base-url http://127.0.0.1:48106/api \
  --token mock-token-moneypal_admin \
  --include-web
```

Pass the FastAPI origin without `/api` when verifying a backend process directly. Pass the
nginx origin with `/api`, as above, because nginx strips that prefix before proxying.

Run it once with `POSTGRES_ACCESS_MODE=direct` and once with
`POSTGRES_ACCESS_MODE=mcp`, using the deployment's normal non-demo token when applicable.

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
