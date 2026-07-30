# Moneypal Genesis Layer — Server Migration Runbook

Moving the whole stack — application, PostgreSQL warehouse, Qdrant vectors, file state and
secrets — from one host to another, without losing data and without a silent partial
cutover.

Written against the current deployment: compose project `moneypal-genesis-layer`, nginx
published on host `:4321`, PostgreSQL and Qdrant **shared with the `company-intelligence`
stack**.

---

## 0. The thing to decide before anything else

`moneypaldb` does not live in a Postgres container of its own. It is a database inside
`company-intelligence-postgres` (superuser role `agent`), and the vectors live in
`company-intelligence-qdrant`. Both are owned by a different compose project that has its
own data in the same services.

That means "migrate moneypal" is ambiguous, and the two readings need different work:

| Reading | What you do | When it's right |
|---|---|---|
| **A. Dedicated services on the target** (recommended) | Stand up a Postgres and a Qdrant that belong to *this* stack. Move only `moneypaldb` and the moneypal collections. | You want moneypal independently backed up, restarted and upgraded. This is the production answer. |
| **B. Lift the shared services too** | Migrate all of `company-intelligence-postgres` and `company-intelligence-qdrant`, both projects together. | Both stacks are moving to the same new host at the same time. |

The rest of this document assumes **A**, and notes where B differs. Under A the target
compose file gains `postgres` and `qdrant` services; today's does not have them, so that
is a real edit, made in §4.

Also decide this now: **the source stack keeps running until §9 signs off.** Nothing below
mutates the source except the final shutdown.

---

## 1. Inventory — everything that is state

If it is not on this list it is rebuildable from git, and should be rebuilt rather than
copied.

| # | State | Lives in | Size class | Rebuildable? |
|---|---|---|---|---|
| 1 | `moneypaldb` — schemas `bronze`, `silver` | `company-intelligence-postgres` | ~300k rows total, largest table 260k | No — this is the warehouse |
| 2 | `public.nlq_audit_log` | same database | grows with usage | No — it is the compliance record |
| 3 | `public.nlq_conversations` | same database | small, expires after 30 min idle | Yes, discardable |
| 4 | `public.briefs` (brief cache) | same database | small | Yes, regenerates |
| 5 | Role `nlq_readonly` + its grants | Postgres **cluster**, not the database | — | Yes, from `nlq_readonly_role.sql` |
| 6 | Qdrant collections `reg_*`, `macro_intel1`, `comp_*` | `company-intelligence-qdrant` | depends on corpus | Yes, by re-ingesting — slow |
| 7 | Qdrant collection `nlq_catalog_<hash>` | same | tiny (~120 points) | Yes, one command |
| 8 | `Regulations/` (source PDFs) | host bind mount, read-only | large | No, unless you hold the originals elsewhere |
| 9 | `backend/registry/` (institutions, regulations) | repo working tree | small | Partly — check `git status` |
| 10 | `backend/vector_store/genesis.db`, `regulatory_chunks.jsonl` | repo working tree | medium | Yes — local fallback index |
| 11 | `.env` | host, gitignored | — | **No.** Not in git by design |

Item 5 is the one people lose. `pg_dump` of a database does **not** carry roles — they are
cluster objects. A restore that looks perfectly clean will leave NLQ dead with
`ReadOnlyNotConfigured` or `role "nlq_readonly" does not exist`.

Item 9 and 10 are in the repo tree, so check whether the source host has uncommitted
changes there before you assume git covers them:

```bash
git -C /f/moneypal-genesis-layer status --short backend/registry backend/vector_store
```

---

## 2. Pre-flight on the target host

```bash
docker --version && docker compose version     # compose v2 syntax is used throughout
df -h /var/lib/docker                          # ≥ 20 GB free: images + pgdata + qdrant
free -g                                        # frontend build needs ~2 GB heap alone
```

Port map to confirm free. The moneypal backend and frontend publish **nothing** — only
nginx is reachable from outside, which is what keeps the API from being exposed directly:

| Port | Service | Note |
|---|---|---|
| 4321 | nginx | the only externally-facing port; match the source or update every bookmark |
| 5432 | postgres | new under plan A; bind to `127.0.0.1:5432` unless another host must reach it |
| 6333 | qdrant | same — no reason to expose it publicly |

Network reachability, only if you are keeping any dependency remote:

```bash
# From the target host, to wherever the LLM will run.
curl -sS --max-time 5 "$NLQ_LLM_BASE_URL/models" | head -c 200
```

---

## 3. Extract from the source

Do all of this while the source is still serving. Nothing here writes.

### 3.1 Quiesce writes

There is no ingestion cron in this stack — ingestion is operator-run — so "quiesce" means:
don't start an ingestion, and accept that `nlq_audit_log` rows written after the dump are
lost. If that matters, stop the backend first and take the dump from a still stack:

```bash
docker compose stop backend        # nginx keeps serving the frontend a 502; brief
```

### 3.2 PostgreSQL

Custom format (`-Fc`) — it compresses, and it lets you restore selectively:

```bash
docker exec company-intelligence-postgres \
  pg_dump -U agent -d moneypaldb -Fc --no-owner --no-acl \
  > moneypaldb_$(date +%F).dump
```

`--no-owner --no-acl` is deliberate: the target's ownership will be re-established by
restoring as the target's own role, and the ACLs are re-applied by §5.3 rather than
carried over. Carrying stale ACLs is how a `nlq_readonly` grant silently survives
pointing at a role that no longer means the same thing.

Capture the roles separately — this is item 5 above:

```bash
docker exec company-intelligence-postgres \
  pg_dumpall -U agent --roles-only > roles_$(date +%F).sql
```

Read that file before using it. Under plan A you want **only** the roles moneypal uses
(`moneypal`, `nlq_readonly`), not every role the company-intelligence stack invented. It
is usually cleaner to skip this file entirely and recreate the two roles from scratch in
§5.3 — the password hashes it contains are the only thing worth keeping, and you are
rotating those anyway (§7).

Record the row counts you will verify against in §9:

```bash
docker exec company-intelligence-postgres psql -U agent -d moneypaldb -c "
SELECT 'loan_account_master' t, count(*) FROM silver.loan_account_master
UNION ALL SELECT 'repayment_schedule', count(*) FROM silver.loan_repayment_schedule
UNION ALL SELECT 'asset_classification', count(*) FROM silver.asset_classification_details
UNION ALL SELECT 'audit_log', count(*) FROM public.nlq_audit_log;"
```

### 3.3 Qdrant

Snapshots are the supported path and they work over HTTP, no volume access needed.

```bash
QSRC=http://localhost:6333

# What is actually there — decide what belongs to moneypal.
curl -s $QSRC/collections | jq -r '.result.collections[].name'

for c in $(curl -s $QSRC/collections | jq -r '.result.collections[].name'); do
  echo "snapshotting $c"
  name=$(curl -s -XPOST "$QSRC/collections/$c/snapshots" | jq -r .result.name)
  curl -s "$QSRC/collections/$c/snapshots/$name" -o "qdrant_${c}.snapshot"
done
```

`nlq_catalog_*` is **not worth snapshotting** — regenerate it on the target with one
command in §6. Its name embeds the catalog content hash, so a stale copy from a different
catalog version is worse than no copy: retrieval silently ranks against definitions that
no longer exist.

> Your `company-intelligence-qdrant` currently reports **unhealthy**. Snapshot creation
> will fail or produce truncated files against an unhealthy instance. Check
> `docker logs company-intelligence-qdrant --tail 50` and get it green *before* you trust
> any snapshot taken from it. If it cannot be recovered, plan on re-ingesting the
> regulatory corpus on the target — slow, but correct.

Volume copy is the fallback if the HTTP API is unusable. It requires Qdrant **stopped** on
both ends; a hot copy of the storage directory produces a corrupt index:

```bash
docker stop company-intelligence-qdrant
docker run --rm -v company-intelligence_qdrant_storage:/from -v "$PWD":/to alpine \
  tar czf /to/qdrant_storage.tgz -C /from .
docker start company-intelligence-qdrant
```

### 3.4 Files and secrets

```bash
tar czf regulations_$(date +%F).tgz Regulations/
tar czf appstate_$(date +%F).tgz backend/registry backend/vector_store
cp .env env_source_backup                       # transfer out of band, see §7
```

Transfer everything with checksums, not a bare `scp`:

```bash
sha256sum *.dump *.tgz *.snapshot > MANIFEST.sha256
rsync -avP --checksum *.dump *.tgz *.snapshot MANIFEST.sha256 user@target:/srv/migration/
ssh user@target 'cd /srv/migration && sha256sum -c MANIFEST.sha256'
```

Never put `.env` in that rsync alongside the rest — see §7.

---

## 4. Prepare the target

```bash
git clone <repo> /srv/moneypal-genesis-layer
cd /srv/moneypal-genesis-layer
git checkout nlp
grep sqlglot backend/Dockerfile     # must print — the NLQ import fails without it
```

Under plan A, add the two services the stack no longer borrows. Append to
`docker-compose.yml`:

```yaml
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: moneypal
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: moneypaldb
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"          # loopback only
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U moneypal -d moneypaldb"]
      interval: 10s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:latest
    restart: unless-stopped
    volumes:
      - qdrant_storage:/qdrant/storage
    ports:
      - "127.0.0.1:6333:6333"

volumes:
  pgdata:
  qdrant_storage:
```

and add `depends_on: {postgres: {condition: service_healthy}}` to `backend`.

Two notes on this block. `POSTGRES_USER: moneypal` makes the app role the cluster
superuser, which is *not* ideal but matches how the app already connects; the security
boundary that matters is `nlq_readonly`, which is a separate non-superuser role either
way. And pinning `qdrant:latest` is a reproducibility hole — pin the digest you actually
tested once you know it works.

Bring up only the data services first:

```bash
docker compose up -d postgres qdrant
docker compose ps          # postgres must reach (healthy) before you restore
```

---

## 5. Restore

### 5.1 PostgreSQL

```bash
docker cp /srv/migration/moneypaldb_*.dump moneypal-genesis-layer-postgres-1:/tmp/db.dump

docker compose exec postgres \
  pg_restore -U moneypal -d moneypaldb --no-owner --no-acl \
             --exit-on-error --verbose /tmp/db.dump
```

`--exit-on-error` matters. Without it `pg_restore` reports a long list of errors, exits 0,
and leaves you with a database that is missing objects you will not notice until a query
fails in production.

If it errors on extensions or pre-existing objects, restore into a genuinely empty
database rather than forcing past them:

```bash
docker compose exec postgres dropdb -U moneypal moneypaldb
docker compose exec postgres createdb -U moneypal moneypaldb
# then re-run pg_restore
```

### 5.2 Indexes and statistics

The dump carries indexes, but not planner statistics — a freshly restored database will
seq-scan everything until analysed:

```bash
docker compose exec -T postgres psql -U moneypal -d moneypaldb \
  < backend/scripts/sql/nlq_indexes.sql
```

Idempotent (`IF NOT EXISTS` throughout) and ends in `ANALYZE`, so it is safe whether or
not the dump already brought the indexes.

### 5.3 The read-only role — the step that gets forgotten

Generate a password and keep it; you need it twice.

```bash
openssl rand -base64 24 | tr -d '/+='
```

Check the owner first, because line 29 of the script names a role explicitly and only
covers tables created by that role:

```bash
docker compose exec postgres psql -U moneypal -d moneypaldb \
  -c "SELECT tableowner, count(*) FROM pg_tables WHERE schemaname='silver' GROUP BY 1;"
```

If that returns anything other than `moneypal`, edit
`backend/scripts/sql/nlq_readonly_role.sql:29` to match before running. Get this wrong and
everything works today, while every table your next ingestion creates is invisible to NLQ.

```bash
docker compose exec -T postgres psql -U moneypal -d moneypaldb \
  -v pw="<the-generated-password>" -v ON_ERROR_STOP=1 \
  < backend/scripts/sql/nlq_readonly_role.sql
```

Pass the password **raw** — the script writes `:'pw'`, so psql adds the quotes.

### 5.4 Qdrant

```bash
QDST=http://localhost:6333
for f in /srv/migration/qdrant_*.snapshot; do
  c=$(basename "$f" .snapshot); c=${c#qdrant_}
  curl -sS -XPOST "$QDST/collections/$c/snapshots/upload?priority=snapshot" \
       -H 'Content-Type:multipart/form-data' -F "snapshot=@$f"
  echo " <- $c"
done
curl -s $QDST/collections | jq -r '.result.collections[].name'
```

### 5.5 Files

```bash
tar xzf /srv/migration/regulations_*.tgz -C /srv/moneypal-genesis-layer/
tar xzf /srv/migration/appstate_*.tgz    -C /srv/moneypal-genesis-layer/
```

---

## 6. Configuration

Write `.env` on the target **by hand** from `.env.example` — do not copy the source file
across unchanged. Three values are host-specific and copying them is the most common way
a migration ends up quietly reading from the old server:

```bash
POSTGRES_HOST=postgres          # the compose service name, under plan A
POSTGRES_PORT=5432
POSTGRES_DB=moneypaldb
POSTGRES_USER=moneypal
POSTGRES_PASSWORD=<new>

QDRANT_URL=http://qdrant:6333   # service name, not 192.168.1.183
QDRANT_HOST=qdrant
QDRANT_PORT=6333

NLQ_DB_USER=nlq_readonly
NLQ_DB_PASSWORD=<the §5.3 password>
NLQ_LLM_PROVIDER=groq
NLQ_LLM_BASE_URL=http://<llm-host-lan-ip>:8080/v1
GROQ_API_KEY=<rotated>
```

`NLQ_LLM_BASE_URL` resolves **inside** the backend container. `localhost` there is the
backend itself, not your llama-server — it must be a LAN IP or a service name.

`NLQ_DB_PASSWORD` must differ from `POSTGRES_PASSWORD`. This is enforced in spirit by
`db.py`, which raises `ReadOnlyNotConfigured` rather than falling back to the app role: a
prompt-injected query that reached the warehouse as the owning role could write to it.

Then build and start:

```bash
docker compose build backend frontend
docker compose up -d
docker compose logs -f backend | head -50
```

Regenerate the catalog vectors — deliberately not migrated, per §3.3:

```bash
docker compose exec backend python -m app.services.nlq.catalog.index
```

If Qdrant is unreachable this fails and NLQ falls back to lexical retrieval. That is a
degradation, not an outage; `RetrievalResult.mode` reports which is in use.

---

## 7. Secrets

Rotate on migration rather than copying. A migration is the one moment where rotation is
free — nothing is running yet on the target to break.

| Secret | Action |
|---|---|
| `POSTGRES_PASSWORD` | New. Set at first `postgres` boot via the compose env. |
| `NLQ_DB_PASSWORD` | New, generated in §5.3. Must differ from the above. |
| `GROQ_API_KEY` | Rotate in the Groq console; the old key stays valid on the old host until you revoke it, which is what lets you roll back. |
| `NLQ_LLM_API_KEY` | Empty for llama.cpp; set only if a gateway sits in front. |

Move `.env` over an interactive channel, not the bulk `rsync`. Then, on the source host,
after §9 signs off:

```bash
shred -u env_source_backup
```

Current deployment note: `NLQ_DB_PASSWORD` is `nlp` — three characters, on the credential
that stands between a prompt-injected query and the warehouse. Migration is the moment to
replace it.

---

## 8. Cutover

1. Stop the source stack: `docker compose stop` (do not `down -v`, that destroys volumes).
2. Repoint DNS / the reverse proxy / bookmarks at the target's `:4321`.
3. Run §9 in full.
4. Only after §9 passes: revoke the old Groq key, and keep the source host's volumes
   untouched for at least **7 days**.

---

## 9. Verification — the sign-off gate

Do not skip to the last one. Each catches a different class of failure, and a stack that
serves a page can still be reading a half-restored warehouse.

**Row counts match §3.2 exactly.** Re-run that same query on the target; every number
must be identical. A pg_restore that silently dropped a table shows up here and nowhere
else.

**The read-only boundary holds.** This is a security control, not a smoke test:

```bash
docker compose exec -e PGPASSWORD='<pw>' postgres \
  psql -U nlq_readonly -d moneypaldb \
  -c "SELECT count(*) FROM silver.loan_account_master;" \
  -c "SELECT count(*) FROM bronze.genlnacnts;" \
  -c "BEGIN READ WRITE; CREATE TABLE silver.x (i int);"
```

Expect `13510`, then **permission denied for schema bronze**, then **permission denied for
schema silver**. Note the `BEGIN READ WRITE` — without it the third statement is blocked
by the session default, which any session can `SET` away, so it proves nothing.

**Capabilities are what you expect:**

```bash
curl -s localhost:4321/api/nlq/health | jq '.capabilities, .catalog.status, .db.status'
```

`execute: true, ask: false` means the database landed and the LLM did not. That is a
working product — saved questions, drill-downs and dashboards all run without the model —
but it is not a complete migration.

**A known number comes back right.** This is the one that proves the warehouse, the
catalog, the compiler and the executor all survived together:

```bash
curl -s -XPOST localhost:4321/api/nlq/execute -H 'Content-Type: application/json' \
  -d '{"query_spec":{"metrics":["par_30"],"period":{"start":"2026-01-01","end":"2026-07-01"}}}' \
  | jq '.rows[0].par_30'
```

Expect **0.090**. If it returns `null`, the `asset_classification_details` table restored
incompletely — that table is an event log, not a snapshot, and a partial restore reads as
"no data" rather than as an error.

Two more to confirm against §3.2's numbers: `loan_count` for all time should be `13510`,
and total disbursement should be **₹217.08 Cr**.

**Audit logging is writing.** The table self-creates on first use via the app role, which
needs CREATE on `public`. If it silently fell back to memory you lose the compliance
record on every restart, with only a warning in the logs:

```bash
docker compose exec postgres psql -U moneypal -d moneypaldb \
  -c "SELECT count(*), max(ts) FROM public.nlq_audit_log;"
```

**The UI renders a chart.** Open `http://<target>:4321/ask` and ask
*"disbursement by product this financial year"*. A chart with three products, a lineage
panel showing SQL, and a summary line. This is the only check that covers nginx, the SSE
stream and the frontend build together.

---

## 10. Rollback

Cheap, because §8 never destroyed anything:

1. `docker compose start` on the source host.
2. Point DNS back.
3. Leave the target up for diagnosis.

The only irreversible step in this document is revoking the old Groq key, which is why it
is last in §8. The window closes when the source host's volumes are deleted — do not do
that for at least a week, and take a final `pg_dump` before you do.

---

## 11. Post-migration

- **Back up.** The source host was the backup until now. Nightly, off-host:
  `pg_dump -Fc moneypaldb` plus a Qdrant snapshot, retained 30 days. A restore you have
  never tested is not a backup — restore into a throwaway container once.
- **Pin `qdrant:latest`** to the digest you verified.
- **Re-run the test suite** against the migrated database:
  `docker compose exec backend pytest tests/nlq -q` — expect 505 passing, including the
  16 `test_readonly_role.py` tests that skip when the role is absent. If those 16 skip,
  §5.3 did not take.
- **Re-run the golden-set eval** once the LLM endpoint is final:
  `docker compose exec backend python -m app.services.nlq.eval`. The gate before persona
  users is ≥ 85% on the QuerySpec path.

### Carried-over open items

Migration does not close these, and they are worth restating because a new server often
gets read as a fresh start:

- **Authentication is mocked.** `auth.py:13` issues `mock-token-<username>` with no
  verification. Every PII masking decision rests on that login, so masking is a UI
  convention rather than a control. **Blocker for production data on any host.**
- **Six metrics await client sign-off:** `par_30`, `par_60`, `par_90`, `npa_ratio`,
  `avg_interest_rate`, `gl_balance`. The PAR denominator question — classified subset
  (₹198.5 Cr) versus whole book (₹275.2 Cr) — will move a board-pack number.
- **Golden-set accuracy has never been measured on a production model.** The free-tier
  provider ran out of quota mid-run.

See `GENESIS_NLQ_RUNBOOK.md` for day-two operations and `GENESIS_NLQ_BUILD_PLAN.md` §12a
for build status.
