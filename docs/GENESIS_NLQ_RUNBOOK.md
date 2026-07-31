# Genesis NLQ — Operations Runbook

Companion to `GENESIS_NLQ_BUILD_PLAN.md`. That document says what to build and why; this one
says how to run it.

---

## 1. What has to be true before it works

| # | Step | Who | Verify |
|---|---|---|---|
| 1 | `nlq_readonly` role exists | DBA, once, as superuser | `backend/scripts/sql/nlq_readonly_role.sql`, then `pytest backend/tests/nlq/test_readonly_role.py` — 16 tests must run, not skip |
| 2 | `NLQ_DB_USER` / `NLQ_DB_PASSWORD` in `.env` | Ops | `GET /nlq/health` → `db.status == "ok"` |
| 3 | Query indexes applied | DBA | `backend/scripts/sql/nlq_indexes.sql` (already applied 2026-07-29) |
| 4 | LLM endpoint reachable | Ops | `GET /nlq/health` → `llm.status == "ok"` |
| 5 | Catalog embedded into Qdrant | Ops, after any catalog edit | `python -m app.services.nlq.catalog.index` |

Steps 1, 2 and 4 gate different capabilities, and `/nlq/health` reports them separately:

```json
"capabilities": { "execute": true, "ask": false, "text_to_sql": false }
```

`execute: true` with `ask: false` is a **working product**, not an outage — saved questions,
drill-downs and dashboards all run without the model. That distinction is the whole reason
QuerySpec is a persisted contract rather than an internal detail.

---

## 2. Configuration

```
NLQ_LLM_PROVIDER=llamacpp|groq
NLQ_LLM_BASE_URL=http://<gpu-private-ip>:8080/v1
NLQ_LLM_MODEL=qwen3.6-32b-instruct-q4_K_M
NLQ_LLM_TIMEOUT_S=30
NLQ_LLM_MAX_RETRIES=1
NLQ_LLM_THINKING=false

NLQ_DB_USER=nlq_readonly
NLQ_DB_PASSWORD=<different from POSTGRES_PASSWORD>
NLQ_STATEMENT_TIMEOUT_MS=15000
NLQ_MAX_ROWS=5000
```

`llama-server` is hosted **outside** this compose stack. Reference invocation:

```
llama-server -m qwen3.6-32b-instruct-q4_K_M.gguf \
  -ngl 99 -c 8192 --parallel 4 --host 0.0.0.0 --port 8080
```

Pin the exact GGUF SHA-256 here when the node is provisioned, so a rebuild is reproducible:

```
model: qwen3.6-32b-instruct-q4_K_M.gguf
sha256: <fill in at provisioning>
```

`NLQ_LLM_THINKING` must stay `false` for any hybrid-reasoning model (the Qwen3 family, and
anything else llama-server answers with a `reasoning_content` field). The planner fills in a
form under a JSON grammar; deliberation buys nothing and costs everything, because the trace
consumes `max_tokens` before the first character of the plan is emitted and `content` comes
back empty.

**Network:** private VPC IP only, never internet-exposed — the endpoint is unauthenticated.
Security group allows 8080 from the app node alone. Customer data never leaves the app node:
the GPU node receives questions and catalog metadata, never loan or customer rows.

---

## 3. Routine operations

### After an ingestion run

```python
from app.services.nlq import cache
cache.bump_data_version()          # invalidates every cached result
```

Then re-run the introspection tests — they are what catch a renamed column before a user
does:

```
pytest backend/tests/nlq/test_catalog_introspection.py
```

### After editing the catalog

```
pytest backend/tests/nlq/test_catalog.py backend/tests/nlq/test_catalog_introspection.py
python -m app.services.nlq.catalog.index
python -m app.services.nlq.eval --pace 2
```

The catalog version is a content hash, so plan-cache entries from before the edit are
invalidated automatically. Qdrant vectors are **not** — that is what the index command is
for.

### Scoring the planner

```
python -m app.services.nlq.eval                 # full golden set
python -m app.services.nlq.eval --category refuse
python -m app.services.nlq.eval --json          # for CI
```

Scoring is on execution match, not string match. The gate before persona users is **≥ 85%
on the QuerySpec path**.

> On a rate-limited free-tier provider a full 54-case run exceeds the daily token budget
> (~3.9k tokens per call, doubled by the repair attempt). Use `--pace`, a paid tier, or the
> self-hosted endpoint. A run that reports 0% accuracy with `LLMUnavailable: 429` in every
> failure detail is a quota result, not a quality result — read the failure details before
> concluding anything about the model.

---

## 4. Monitoring

Expose on the existing platform dashboard, from `/nlq/health` and `nlq_audit_log`:

| Signal | Query | Alert when |
|---|---|---|
| LLM availability | `/nlq/health` → `llm.status` | not `ok` for 5 min |
| Error rate | `outcome = 'execution_error'` share | > 2% over 15 min |
| p95 latency | `percentile_cont(0.95) … duration_ms` | > 8000 ms |
| Refusal rate | `route = 'refuse'` share | > 25% — usually a catalog gap, not user behaviour |
| Validator rejections | `outcome = 'validator_rejected'` | any spike — the model is trying something new |
| PII access | `touches_pii = true` | reviewed weekly, always |

```sql
-- Answer quality over the last day, by route.
SELECT route, outcome, count(*), round(avg(duration_ms)) AS avg_ms
FROM public.nlq_audit_log
WHERE ts > now() - interval '1 day'
GROUP BY 1, 2 ORDER BY 3 DESC;

-- The catalog backlog: every thumbs-down is a golden-set case waiting to be written.
SELECT turn_id, question, route, feedback_comment
FROM public.nlq_audit_log
WHERE feedback = 'down' ORDER BY ts DESC;
```

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `db.status = "unconfigured"` | `NLQ_DB_PASSWORD` unset | Create the role, set the variable. NLQ deliberately refuses to fall back to the app role |
| Every question refuses | Catalog failed to load | `/nlq/health` → `catalog.status`; check the YAML |
| Every question refuses, catalog and DB healthy | The planner is failing and demoting to text-to-SQL, which then declines. The `plan` SSE frame shows `route: "sql", attempts: 2, repaired: true` | Read the `NLQ plan rejected on attempt N` log line — it carries the exact reason. A thinking model with `NLQ_LLM_THINKING=true` spends the whole token budget on `reasoning_content` and returns empty `content` |
| `ask: false`, `execute: true` | LLM unreachable | Expected degradation. The ask bar says so; dashboards keep working |
| PAR looks impossibly low | Denominator is the classified subset (₹198.5 Cr), not the whole book (₹275.2 Cr) | Working as documented — see the coverage warning on every PAR answer, and §7 below |
| Disbursement reads zero before Oct 2025 | The event log starts 2025-10-15 | Working as documented; the answer says so |
| A trend has missing months | Classification history starts 2026-05-22 | Working as documented — gaps are shown rather than filled with zero |
| Slow query | Missing index or a fan-out bug | Largest table is 260k rows; if a query is slow it is not scale |

---

## 6. Rollout gates

1. Catalog + compiler + `/nlq/execute` behind a feature flag — **done**, no LLM required.
2. `/nlq/ask` with the LLM, internal users only.
3. Golden-set accuracy ≥ 85% on the QuerySpec path before persona users.
4. General availability.

---

## 7. Open items before go-live

These are known, deliberate, and not defects:

- **Mock authentication.** `auth.py:13` issues `mock-token-<username>` with no verification.
  Every PII masking decision is only as strong as that login, so the masking is a UI
  convention until auth is real. **Blocker for production data.**
- **Metric definitions pending client sign-off:** `par_30`, `par_60`, `par_90`, `npa_ratio`,
  `avg_interest_rate`, `gl_balance`. Each renders with a badge until confirmed. The PAR
  denominator question — classified subset versus whole book — is the one that will change a
  number on a board pack.
- **Golden-set accuracy not yet measured on the production model.** Re-run the eval against
  the final GGUF before GA; the gate is 85%.
- **Retrieval runs lexical-only until the catalog is embedded.** Functional, slightly worse
  ranking; `RetrievalResult.mode` reports which is in use.
