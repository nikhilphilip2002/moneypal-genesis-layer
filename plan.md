# Workbench Source-Access and Single-Agent Simplification Plan

## Document status

- Status: repository implementation complete; deployment measurement/canary validation pending
- Local verification: Workbench 225 passed/1 skipped, scoped NLQ 852 passed/90 skipped,
  TypeScript clean, production frontend build passed
- Remaining authority boundary: live PostgreSQL/Qdrant/web/model/cache validation and
  rollback/canary execution must run on the deployment machine
- Scope: data-source consent, backend orchestration, model-call reduction, prompt-cache stability, and conversation state
- Compatibility target: evolve the Workbench request additively while preserving SSE events,
  cards, existing history, and the governed NLQ safety boundary
- Primary outcome: reduce redundant model calls without weakening database, PII, role, source, or citation controls
- Related data-layer plan: docs/semantic-views-low-token-plan.md

## 1. Executive decision

Replace the current LangGraph route → dispatch → synthesize wrapper with an ordinary async
orchestrator. Use one canonical Workbench conversation transcript and a small set of governed
data tools. Prefer deterministic source selection for explicit and high-confidence cases.
Keep the existing constrained NLQ planner, compiler, validator, read-only execution, and audit
path as the database tool's internal safety implementation.

Do not begin with a native autonomous tool-calling loop. The current LLM client supports
completions and constrained JSON, but not tool-call request/response messages. The first
implementation gets most of the cost benefit with less risk by using application-controlled
tool execution and one final composition call only when retrieved evidence needs prose.

Do not use one universal model prompt. Router fallback, DB planning, and answer composition
have different jobs and receive separate minimal, versioned prompts. The composer never
receives routing instructions, complete tool descriptions, DB schema mechanics, or rules
already enforced by structured output and application code.

The target is one conversational-agent experience, not necessarily one model invocation for
every request. DB planning may remain a separate constrained call because it produces
validated structured intent rather than user-facing prose.

The data-source policy is independent of routing and model-provider policy. PostgreSQL is
available by default. A single explicit, conversation-scoped toggle additionally permits all
role-authorized Qdrant sources and web search. The backend enforces this boundary before
routing, dispatch, direct tool execution, or external network access.

## 2. Why this change

The graph itself is not the main cost. Model calls also occur inside source handlers and the
NLQ pipeline:

    user question
      → LLM source router
      → one or more source handlers
           → NLQ planner and possibly SQL generator
           → or per-source RAG synthesis
      → optional LLM next-question personalization
      → optional multi-source LLM synthesis
      → optional background LLM compaction

The same request can therefore be interpreted several times under different system prompts.
Those prompts fragment local KV and hosted-provider caches. The three-node graph also
duplicates control flow already expressible with asyncio.gather, an event queue, and ordinary
functions.

Two state stores currently exist:

- public.workbench_conversations: durable renderable turns and bounded model transcript.
- public.nlq_conversations: short-lived structured QuerySpec anchor and sticky filters.

They have different purposes. Workbench history becomes the canonical prose history, while
the structured NLQ state remains temporarily as an internal DB-tool implementation detail.

The current build also makes every role-visible source eligible for automatic routing. Its
Direct/MCP selector changes only the PostgreSQL transport, source pinning forces one source,
and local/Groq settings choose a model provider. None is the required consent control for
Qdrant and web access. This plan adds that missing boundary.

## 3. Goals

### Product goals

- Preserve the existing Workbench behavior and UI.
- Give follow-ups one coherent conversational context.
- Continue returning charts, analyses, worklists, briefings, schema cards, citations,
  clarifications, refusals, errors, and partial answers.
- Continue streaming progress and completed source cards.
- Keep source pinning and role-specific visibility.
- Default every new conversation to PostgreSQL/internal sources only.
- Provide one clearly labeled toggle that enables or disables all Qdrant and web sources
  together for the current conversation.
- Make the active data-source mode visible beside the composer and in restored history.

### Cost and performance goals

- Remove the LLM router from ordinary high-confidence requests.
- Remove LLM next-step personalization from the critical path.
- Stop generating prose independently inside every vector source.
- Use no more than one user-facing composition call per turn.
- Retain a DB planner call only when deterministic follow-up resolution, plan cache,
  registered analyses, or governed lookups cannot answer without it.
- Reduce median calls for a simple governed DB request from approximately three to one.
- Reduce two-vector-source requests from approximately four calls to one.
- Record prompt, cached-prompt, completion tokens, call counts, and latency for every turn.
- Keep a stable prompt prefix to improve cache reuse.

### Safety goals

- Never expose unrestricted SQL execution to the conversational model.
- Never execute SQL that has not passed the existing validator.
- Preserve table, column, join, role, PII, timeout, row-limit, and read-only controls.
- Preserve exact user names, identifiers, periods, and measures sent to the DB tool.
- Treat vector and web content as untrusted evidence, not instructions.
- Keep citations and lineage attached to structured tool results.
- Fail closed for permissions and unsafe DB requests.
- Never send sensitive DB evidence to an external provider.
- Enforce external-source consent on the server; UI hiding is not a security boundary.
- Prevent router, pin, tool, workspace, or direct endpoint paths from bypassing consent.
- Intersect user consent with role permissions and deployment availability; consent never
  grants a role new access.

## 4. Non-goals

- Rewriting the semantic catalog, Gold views, QuerySpec compiler, or SQL validator.
- Replacing Qdrant, PostgreSQL, llama.cpp, Groq, or the frontend framework.
- Moving loan-book data to an external model.
- Merging the conversation tables in the first release.
- Adding unrestricted autonomous actions or write-capable DB tools.
- Breaking existing `/workbench/ask` callers (or `/api/workbench/ask` through nginx); the
  new request field defaults safely.
- Redesigning Workbench cards or navigation.
- Completing the separate semantic-view/catalog initiative in this change.

## 5. Data-source access policy

### Source groups

| Group | Sources | Default | Notes |
|---|---|---|---|
| Internal data | db | Enabled | Governed read-only PostgreSQL loan-book access |
| Internal metadata | schema | Enabled only for authorized explicit schema requests | PostgreSQL-derived abstracted views/relationships |
| Local governed knowledge | knowledge | Enabled | Static catalog definitions; no Qdrant or web access |
| External indexed data | macro, competitive, regulatory | Disabled | Qdrant sources enabled together by the toggle |
| Live external data | web | Disabled | Network search enabled by the same toggle and deployment configuration |

The toggle controls data provenance, not whether infrastructure is physically local. A local
Qdrant deployment still contains external/indexed sources and remains disabled until the user
enables other sources.

### Effective allowed-source set

For every request:

    effective sources
      = sources allowed by the conversation toggle
      ∩ sources allowed by the user's role
      ∩ sources available in the deployment

With the toggle off, automatic routing may use db and local governed knowledge; schema is
available only for an explicit authorized schema request. It may not use macro, competitive,
regulatory, or web. With the toggle on, those external sources become candidates while db
remains available.

### Toggle semantics

- Request field: external_sources_enabled: boolean, optional and false when absent.
- Scope: current conversation, not a global account setting.
- New conversation: false.
- Existing pre-change conversation: false until explicitly enabled.
- Reopened conversation: restore the last explicitly persisted value and display it.
- Turning the toggle off: immediately remove external sources from subsequent requests and
  clear an external pinned source.
- In-flight request: use an immutable snapshot of the value at submission time.
- External pin while disabled: reject with a typed access response; never silently enable it.
- External-only question while disabled: do not call the router, Qdrant, or web. Explain that
  other sources are disabled and invite the user to enable the toggle.
- Mixed internal/external question while disabled: answer the supported DB portion and mark
  external evidence unavailable because it is disabled.

### Backend enforcement points

Enforce the effective set at all of these boundaries:

1. request validation and policy construction;
2. source list returned to routing;
3. deterministic and model-router output validation;
4. dispatch immediately before a handler runs;
5. source pin validation;
6. POST /workbench/tool/{id};
7. Workbench workspace actions that retrieve Qdrant or web evidence;
8. web client immediately before any external network call.

The same policy object should flow through the request rather than being recomputed
differently in each module. Denials must be audited without storing sensitive question text
in general application logs.

### Independent controls

- external_sources_enabled controls Qdrant/web data access.
- data_access controls direct versus MCP PostgreSQL transport.
- pinned_source narrows routing to one already-allowed source.
- WORKBENCH_LOCAL_ONLY and WORKBENCH_GROQ_OPT_IN control inference provider policy.
- Role policy controls which sources the authenticated user may use.

These controls must not imply or mutate one another.

## 6. Baseline to measure

| Request family | Current approximate calls | Main calls |
|---|---:|---|
| Pinned source | 0–2 | source synthesis or DB planning; optional personalization |
| Simple governed DB metric | about 3 | router, planner, personalization |
| Structural DB follow-up | about 1–2 | router and optional personalization |
| Long-tail DB SQL | about 3–5 | router, planner, SQL generation/repair, personalization |
| One vector source | about 2 | router and source synthesis |
| Two vector sources | about 4 | router, two source syntheses, final synthesis |
| DB plus vector | about 4–6 | router, DB planning, source synthesis, final synthesis, optional personalization |

Exact counts must come from telemetry. Retries, cached plans, deterministic lookups,
clarifications, and empty retrieval alter the count.

Capture:

- model calls per turn and by purpose;
- planned calls versus retry/repair calls;
- prompt, cached-prompt, and completion tokens;
- cache-hit and cached-token ratios;
- time to first event, first card, final answer, and total latency;
- source-selection correctness;
- attempted and completed Qdrant/web calls by toggle state;
- external consent denials and attempted pin/tool bypasses;
- answer correctness, completeness, and refusal correctness;
- SQL validation and repair rates;
- retrieval latency and empty-result rate.

## 7. Target architecture

    canonical Workbench conversation + external-source consent
                 │
    user → auth/role → consent gate → transcript + follow-up resolution
                 │
                 v
       deterministic selection from effective allowed sources
          │        │        │        │
          v        v        v        v
       DB tool   vector   schema   public web
          │       search    tool      tool
          +--------+--------+---------+
                 │
       deterministic render when sufficient
                 │
       otherwise one composition call
                 │
       cards + answer + citations + lineage

### Orchestrator responsibilities

The plain async orchestrator must:

1. load the bounded transcript once;
2. begin and persist the turn;
3. snapshot external-source consent and compute the role/deployment/consent intersection;
4. enforce the effective source set on pins, routing, dispatch, tools, and web calls;
5. resolve safe structural follow-ups;
6. select tools deterministically where confidence is high;
7. run independent allowed tools concurrently;
8. stream source lifecycle events;
9. isolate individual source failures;
10. render deterministically when one result already answers the question;
11. call one composer when evidence requires prose or comparison;
12. persist consent, the definitive answer, and usage;
13. trigger bounded compaction after the turn only when required.

### Source-selection policy

Selection is layered:

1. Build the effective set from conversation consent, role, and deployment availability.
2. Reject every source outside that set before model routing.
3. An allowed explicit pin selects a source without a model.
4. Deterministic grammar recognizes schema, record lookup, DB value, explicit web,
   freshness, regulatory, macro, competitor, and stable-definition requests.
5. Exact and lexical catalog evidence confirms DB coverage.
6. External-only questions short-circuit to a consent-required response while disabled.
7. The existing constrained router handles only genuinely ambiguous allowed requests.
8. All model selections are post-validated against the effective source set.
9. Refusal occurs only after policy and catalog checks find no permitted supporting source.

The model router is a temporary ambiguity fallback, not a mandatory stage. Remove it only
after deterministic routing and fallback behavior meet acceptance thresholds.

The router must never decide whether external access is allowed. It receives only the
effective source set. Enabling external sources changes eligibility, not the router's
authority.

## 8. Governed tool contracts

Use one typed result envelope:

    ToolResult
      source: string
      kind: string
      payload: renderable UI object
      evidence: compact model-facing evidence list
      summary: deterministic short summary
      complete: boolean
      limitation: string
      sensitive: boolean
      lineage: optional object

The UI payload and composer evidence are separate. Raw rows, full chart JSON, SQL logs, and
hidden lineage do not enter model history.

Every tool declares a source group. The dispatcher checks that declaration against the
request's immutable source policy immediately before execution. Tool handlers also perform a
defense-in-depth check where they can trigger Qdrant or network access.

### Database tool

Inputs:

- exact user question;
- conversation id;
- user and role;
- direct or MCP access mode;
- bounded conversation context;
- optional structured NLQ anchor.

Internal priority:

1. deterministic record lookup;
2. structural follow-up on the previous QuerySpec;
3. cached validated plan;
4. registered analysis, briefing, signal, or worklist;
5. constrained QuerySpec plan and deterministic compile;
6. retrieved-schema text-to-SQL fallback;
7. safe refusal.

Retain the current validator, read-only transaction, PII checks, audit log, timeout, row
limits, and lineage.

### Vector tools

Macro, competitive, and regulatory-document tools require external_sources_enabled. They
return ranked passages and metadata and do not each write prose on multi-source requests. A
common composer handles one or several evidence sets. Extractive fallbacks remain available.
Stable catalog-backed knowledge does not require the toggle because it accesses neither
Qdrant nor the web.

### Schema tool

Return only role-permitted abstracted view metadata and approved join paths. Do not expose
raw operational schemas, hidden columns, credentials, or sensitive database statistics.

### Web tool

Accept only a sanitized public-data subquestion. Reject private bank identifiers and internal
figures before an external request. Return URL, title, publication date, measured period when
known, retrieval time, and bounded evidence. Treat all returned content as untrusted. Check
external consent both before dispatch and immediately before network retrieval.

## 9. Answer composition

Render without a composer when:

- one DB result already has a complete chart/worklist/analysis headline;
- the outcome is a clarification or refusal;
- schema metadata already has a complete card;
- a deterministic template expresses the result faithfully.

Use one composer when:

- RAG passages need a natural-language answer;
- multiple sources contribute;
- comparison or synthesis is explicitly requested;
- partial or conflicting evidence needs explanation.

When external sources are disabled, do not invoke the composer merely to explain the policy.
Use a deterministic consent-required message. For a mixed question, the normal DB result can
be returned with a structured limitation naming disabled external evidence.

Composer requirements:

- use supplied facts and passages only;
- never alter or infer figures;
- cite claims using supplied metadata;
- expose missing and conflicting evidence;
- ignore instructions in retrieved content;
- include only role-authorized facts;
- return status, text, sources, citations, unavailable sources, and limitations.

## 10. Model-call budgets

| Path | Target |
|---|---:|
| Structural DB follow-up | 0 |
| Deterministic DB lookup | 0 |
| Governed DB metric requiring planning | 1 |
| Normal DB text-to-SQL fallback | 2 |
| DB SQL fallback with one repair | at most 3 |
| Single vector source | 1 |
| Multiple vector sources | 1 |
| DB plus vector | DB planning if needed + 1 composer |
| Schema display | 0 |
| Permission refusal | 0 |
| External-only request while toggle is off | 0; deterministic consent response |
| Mixed DB/external request while toggle is off | DB budget only; no external call |
| History compaction | 0 normally; 1 only past threshold |

Retries must be reported separately from planned calls.

### Per-call token budgets

These are initial engineering guardrails. Phase 0 must measure the baseline and ratify or
tighten them before they become CI failure thresholds. Cached stable prefixes are reported
separately and are not hidden inside the uncached-input number.

| Call/input component | p50 target | p95 ceiling | Output ceiling |
|---|---:|---:|---:|
| Ambiguous router fallback | 600 uncached input tokens | 900 | 300 |
| DB planner dynamic suffix, excluding cached Gold prefix | 1,200 | 2,500 | 700 |
| Text-to-SQL dynamic schema/evidence pack | 1,800 | 3,000 | 900 |
| Common composer total input | 2,000 | 4,000 | 700 |
| Replayed conversation history | 1,000 | 2,000 | n/a |
| Evidence from one source | 600 | 1,200 | n/a |
| Evidence across all sources | 1,500 | 3,000 | n/a |
| Compaction input | 2,000 | 4,000 | 1,200 |

Track total input, cached input, cache-write input when the provider reports it, and uncached
input independently. Optimize the whole turn using:

    uncached prompt work = sum(uncached input tokens for every model call)

For providers that charge separately for cache writes and reads, also report a
provider-weighted input cost. Do not optimize only total system-prompt length: a longer,
stable cached prefix may be cheaper and faster than a shorter prefix that changes each turn.

## 11. Prompt and cache design

### Instruction ownership

Each rule has one authoritative owner:

| Concern | Owner | Must not be repeated in |
|---|---|---|
| Role, consent, source eligibility | Application policy | Composer prompt |
| SQL tables, columns, joins, PII, read-only execution | DB tool/compiler/validator | Router and composer |
| Source retrieval mechanics | Tool implementation/contract | Composer prompt |
| Source-specific limitations and provenance | ToolResult evidence envelope | Global system prompt |
| Grounding and untrusted-evidence behavior | Composer system prompt | Every evidence item |
| Citation and answer behavior | Composer system prompt | Router prompt |
| Output fields and types | Structured-output schema | Duplicated prose instructions |
| Current user/consent/evidence state | Dynamic request suffix | Stable prefix |

Do not describe a JSON schema again in prose when constrained structured output already
enforces it. Prose may explain semantic invariants that a schema cannot express, such as
“never alter a supplied figure.”

### Purpose-specific prompts

#### Router fallback

The router receives only:

1. a short fixed routing contract;
2. compact descriptions of sources in the effective allowed set;
3. the constrained route schema;
4. only the conversation facts needed to resolve the source;
5. the current normalized question.

It does not receive evidence, SQL schema, chart payloads, composer instructions, or sources
the request is not allowed to use.

#### DB planner

The DB planner keeps its own stable governed Gold prefix, compact conversation/query anchor,
and current question. It does not receive external-source descriptions or composer rules.
Its structured schema owns the plan format.

#### Composer

The composer system prompt contains only:

1. grounding and untrusted-evidence invariants;
2. citation requirements;
3. concise answer and partial-evidence behavior;
4. semantic requirements not expressible in the structured-output schema.

The composer receives selected ToolResult evidence, limitations, relevant recent history,
and the question as a dynamic suffix. It does not receive the complete source registry, tool
implementation descriptions, routing examples, DB catalog, SQL instructions, or prose that
duplicates its output schema.

### Cacheable-prefix rules

- Put stable instructions and shared reference material first; append dynamic user/history/
  evidence state afterward.
- No timestamps, random ids, availability state, consent value, or evidence in the stable
  prefix.
- Serialize every stable prefix deterministically and record its byte hash and version.
- Keep provider/model affinity within a conversation when policy permits.
- Record prompt version, tool-contract version, catalog version, provider, and model.
- Record total, cached, cache-write, and uncached input tokens where available.
- Preserve append-only recent messages where possible; record when compaction or truncation
  changes the reusable prefix.
- Keep router source descriptions byte-for-byte stable and in deterministic order, while the
  effective source schema/state remains in the dynamic portion.
- Avoid normal-path per-source system prompts.
- Verify exact prefix reuse; logical history equality alone is not a cache hit.
- Preserve the warmed Gold prefix for NLQ until the compact semantic-pack project replaces it.
- Test cache behavior under concurrent llama.cpp slots.

### Provider-specific cache controls

- llama.cpp: retain and measure cache_prompt and n_cache_reuse behavior; tune slots and reuse
  only from production-like load tests.
- OpenAI Responses API, when selected and supported: use a stable prompt_cache_key, place an
  explicit cache breakpoint immediately after reusable instructions when beneficial, and
  measure cached_tokens, cache_write_tokens, latency, and weighted cost.
- Other providers: use only documented controls and preserve the same provider-neutral prompt
  ordering.
- Never add OpenAI-only fields to llama.cpp or Groq requests.

Minimum cacheable length and breakpoint behavior vary by provider/model. Do not pad prompts
with irrelevant instructions merely to qualify for caching; measure the deployed model.

## 12. Conversation state

public.workbench_conversations is the canonical user-visible store. Model history contains:

- bounded checkpoint summary;
- mechanically extracted exact session facts and source bindings;
- newest complete turns;
- final assistant answers, not duplicate source-card prose;
- no raw SQL, full chart payloads, large row sets, or hidden lineage.

“Single history” means one ordered conversational list of user questions and definitive
assistant answers. It does not mean one raw list containing router prompts, planner JSON,
tool traces, retrieved documents, and UI cards. Those remain typed per-turn state and are
projected into a bounded prompt only when relevant. This keeps conversational continuity
without paying repeatedly for internal execution detail.

Each turn also records external_sources_enabled and the effective source ids used for that
request. The conversation record stores the latest explicit toggle state so reopening a
conversation restores it visibly. New and pre-change conversations default to false. This is
policy/audit state and is not summarized away during compaction.

Keep public.nlq_conversations temporarily for structured analytics state only. A later
migration can place active QuerySpec, entities, and sticky filters in the Workbench record.
Do not combine that migration with the orchestration rollout.

## 13. API and frontend compatibility

Keep:

- POST /api/v1/workbench/ask
- existing question, conversation_id, pinned_source, and data_access fields;
- add optional external_sources_enabled with a server-side default of false;
- text/event-stream response;
- conversation, stage, route, source_start, source_card, answer, refusal, error, and done
  events and their current shapes;
- readable version-1 through version-3 history records; write the new policy state in a new
  record version without requiring a relational-table migration.

The frontend must add one toggle labeled in data-source terms, for example “Use external
sources.” It controls macro, competitive, regulatory, and web together. It must not be named
“local/cloud,” because Qdrant may be local while its data provenance is external. The current
Direct/MCP PostgreSQL selector remains independent. The source-pin menu disables external
pins while the toggle is off and clears one when the user turns access off.

GET /workbench/sources should return source group and availability metadata so the UI does not
hardcode classifications. POST /workbench/tool/{id} and any relevant workspace request must
carry or resolve the same conversation-scoped policy. Backend checks remain authoritative.

## 14. Repository change map

| File/area | Change | Risk |
|---|---|---|
| backend/app/services/workbench/graph.py | Replace StateGraph with plain async orchestration; preserve run_workbench | Medium |
| backend/app/services/workbench/router.py | Deterministic-first selection, confidence, reason, optional model fallback | Medium |
| backend/app/services/workbench/sources.py | Classify internal, external-indexed, and web groups; compute effective sources | Medium |
| backend/app/services/workbench/nodes.py | Split retrieval/execution from per-source prose; typed results | Medium-high |
| backend/app/services/workbench/tools.py | Attach source groups and enforce consent for direct tool execution | Medium |
| backend/app/services/workbench/models.py | Simplify model purposes; retain sensitive/local enforcement | Low |
| backend/app/services/workbench/history.py | Persist consent/effective sources and aggregate usage compatibly | Medium |
| backend/app/services/workbench/compaction/* | Adapt only if result envelope changes require it | Low-medium |
| backend/app/services/workbench/suggestions.py | Remove default critical-path model call | Low |
| backend/app/api/routes/workbench.py | Add safe-default request field, policy construction, source metadata, and tool enforcement | Medium |
| backend/app/services/nlq/ask.py | Telemetry/tool-boundary metadata; preserve behavior | Low-medium |
| backend/app/services/nlq/llm/client.py | Call-purpose telemetry; no native tools initially | Low |
| pyproject.toml, uv.lock, backend/Dockerfile | Remove unused graph dependencies | Low |
| backend/tests/workbench/* | Framework-neutral orchestration, routing, contract, budget tests | Medium |
| frontend/app/workbench/page.tsx | Own conversation-scoped toggle state and send it with requests | Medium |
| frontend/components/workbench/Composer.tsx | Add the grouped external-source toggle and disabled pin states | Medium |
| frontend/lib/api.ts | Add request/response types and payload field | Low |

No relational DB migration is required. The JSON history record version changes additively;
older records load with external_sources_enabled=false.

## 15. Implementation phases

### Phase 0 — Baseline and safeguards

- Add call-purpose and per-turn usage telemetry.
- Define separate router, DB planner, and minimal composer prompt builders.
- Serialize each stable prefix deterministically; record its version and byte hash.
- Add prefix-stability tests before changing the call graph.
- Record total, cached, cache-write, and uncached tokens per call where supported.
- Baseline p50/p95 token use against the provisional per-call budgets.
- Build a representative fixture for all sources and mixed paths.
- Measure current calls, tokens, cache behavior, latency, correctness, and failures.
- Add model-call-budget test helpers.
- Add flags for the new orchestrator, deterministic routing, common composer, and optional
  suggestion personalization.
- Add a deployment master switch for external connectors, independent of the user toggle.
- Baseline external_sources_enabled=false and true, including attempted bypasses.
- Run existing backend, NLQ, Workbench, and frontend checks.

Exit:

- Baseline is recorded.
- Every target path has a measured call count.
- Every model purpose has a measured p50/p95 uncached-token baseline and prefix hash.
- Repeated identical prefixes demonstrate cache reuse where the provider supports it.
- Legacy/new selection is tested.
- Current suites pass or existing failures are documented.

### Phase 1 — Add data-source consent and remove optional critical-path calls

- Add source-group classification and one shared SourceAccessPolicy object.
- Add external_sources_enabled to ask requests with a false default.
- Persist the submitted value and effective source set on each turn.
- Restore the latest explicit value on reopen; default old records off.
- Add the composer toggle and API types.
- Keep Direct/MCP and local/Groq controls independent.
- Filter candidates before routing and validate again before dispatch.
- Reject an external pin while disabled and clear it when the UI toggle turns off.
- Gate direct Workbench tools and relevant workspace actions on the backend.
- Check consent immediately before Qdrant and web operations as defense in depth.
- Return deterministic consent-required and mixed-question limitation responses.
- Disable LLM next-step personalization by default.
- Return existing compiler-checked suggestions.
- Bypass model routing for allowed pins, deterministic lookups, and structural DB follow-ups.
- Preserve exact DB question text.

Exit:

- DB drill UX works.
- Toggle-off requests cannot reach Qdrant or web through routing, pins, tools, or workspaces.
- Toggle-on requests can use all role-permitted available external sources while retaining DB.
- Old clients and history safely default to external access off.
- Known deterministic paths meet their call budgets.
- Safety suites pass.

### Phase 2 — Replace LangGraph

- Extract ordinary async route, dispatch, and answer functions.
- Preserve gather-based fan-out, SSE queue, failure isolation, cancellation, persistence, and
  background compaction.
- Carry one immutable SourceAccessPolicy snapshot through selection, dispatch, and history.
- Keep run_workbench at its current import path.
- Remove graph imports and dependencies only after repository-wide verification.
- Convert graph tests to framework-neutral orchestrator tests.

Exit:

- Event/API parity passes.
- Route and answer parity pass.
- No graph imports remain.
- Calls do not increase.

This phase simplifies code but does not itself save model calls.

### Phase 3 — Deterministic-first routing

- Promote existing lexical/catalog fallback into the primary selector.
- Run selection only against the effective source set.
- Short-circuit external-only requests while consent is off without calling the model.
- Return the DB-supported portion plus a disabled-external limitation for mixed requests.
- Return confidence, reason, policy version, and fallback-used telemetry.
- Define deterministic precedence for overlapping cues.
- Use constrained routing only for ambiguous cases.
- Build regression cases from observed misses rather than hardcoding question answers.

Exit:

- Source-set accuracy is at least 95%.
- At least 80% of representative turns avoid the router model.
- Permission/destructive-request tests pass 100%.
- External consent tests pass 100% for router, dispatch, pins, tools, and web.
- Fallback remains safe and observable.

### Phase 4 — Retrieval-only vector sources

- Introduce the common ToolResult/evidence envelope.
- Convert macro, competitive, regulatory-document, knowledge, and web paths as applicable.
- Preserve metadata, citation/page protections, source failure isolation, and degraded modes.
- Bound passages and evidence tokens.
- Keep DB behavior behind the same typed boundary.
- Require SourceAccessPolicy for every Qdrant/web ToolResult producer.

Exit:

- Source handlers return typed results.
- Vector sources do not separately synthesize before common composition.
- Existing cards render unchanged.
- Citation and limitation tests pass.

### Phase 5 — Common composer

- Implement the minimal composer prompt defined in Section 11 and a typed answer.
- Exclude the source registry, complete tool descriptions, route examples, DB catalog, and
  structured-schema prose from the composer.
- Use deterministic rendering when sufficient.
- Compose one or multiple vector evidence sets once.
- Compose DB plus vector results once.
- Keep extractive fallback.
- Aggregate all call usage into the turn.
- Remove old per-source and final synthesis paths after parity.

Exit:

- No path does both per-source and final synthesis.
- Exactly one definitive answer is emitted.
- Call budgets pass.
- Numerical and citation grounding pass.

### Phase 6 — Cache and history hardening

- Revalidate and tune the purpose-specific prefix versions established in Phase 0.
- Keep all dynamic data after each purpose-specific stable prefix.
- Verify deployed llama.cpp cached-token behavior at production-like concurrency.
- Confirm Workbench is the only prose transcript.
- Keep NLQ state structured-only.
- Persist consent as exact policy state that compaction cannot rewrite or discard.
- Re-tune transcript and compaction thresholds from measured prompts.
- Test long conversations and overflow behavior.
- After the call graph and prompts are stable, evaluate lower reasoning effort and lower
  output verbosity independently for router fallback, DB planner, and composer.
- Adopt lower settings only when task-specific correctness and grounding evaluations pass.

Exit:

- Cached-token ratio improves from baseline.
- Per-call and per-source p50/p95 token budgets pass or have a documented evidence-based
  revision.
- Selected reasoning/verbosity settings have benchmark evidence and no quality regression.
- Long-history and compaction tests pass.
- Cross-user isolation remains intact.
- Prompts contain no unauthorized data.

### Phase 7 — Rollout and cleanup

- Shadow compare legacy and new paths where possible.
- Canary by user or percentage.
- Monitor calls, tokens, cache, latency, correctness, partial answers, errors, and validation.
- Monitor denied external attempts, toggle adoption, connector use, and policy mismatches.
- Test feature-flag rollback.
- Complete an observation window.
- Remove legacy orchestration, old prompts, adapters, and dependencies.
- Update architecture and operating documentation.

Exit:

- Acceptance metrics hold through observation.
- No unresolved security, correctness, or citation regression.
- Legacy code is removed.
- Runbooks reflect the new path.

### Phase 8 — Optional native tool-calling agent

Treat this as a separate decision:

- extend message types for assistant tool calls and tool results;
- send stable tool definitions and parse calls;
- validate every call and enforce maximum steps;
- detect repeated/malformed calls;
- prove local model protocol reliability;
- retain all permission and DB validation outside model control.

Proceed only if benchmarks show better cost, quality, or extensibility than the
application-controlled orchestrator.

## 16. Testing strategy

### Unit

- routing predicates and precedence;
- role and pin filtering;
- source grouping and effective-set intersection;
- request-default, conversation restore, and toggle-off pin clearing;
- exact DB question preservation;
- typed tool/evidence contracts;
- deterministic answer selection;
- evidence sanitization and bounds;
- call accounting;
- stable prefix serialization;
- history and compaction;
- citation deduplication and limitations.

### Integration

- DB plan → compile → validate → execute → chart;
- vector retrieve → compose → cited brief;
- DB plus vector → parallel tools → grounded comparison;
- one source failing while another succeeds;
- no-result, clarification, and refusal paths;
- cancellation in selection, retrieval, DB execution, and composition;
- local-only sensitive-data policy;
- toggle-off proof that no Qdrant or web client is called;
- toggle-on role/deployment intersections;
- direct tool and workspace bypass prevention;
- MCP and direct PostgreSQL modes;
- persisted reload and follow-up.

### Contract/UI

- schema/order checks for all SSE events;
- existing frontend event consumption;
- external-source toggle defaults, labels, accessibility, state restoration, and payload;
- independence of external access, Direct/MCP transport, pinning, and local/Groq mode;
- unchanged card payload rendering;
- answer, citation, limitation, and error rendering;
- old/new history loading;
- recoverable partial turn after abort.

### Evaluation/adversarial

- golden routes and canonical NLQ questions;
- paraphrases, typos, and mixed comparisons;
- unsupported-data requests;
- user, vector, and web prompt injection;
- destructive/write SQL requests;
- PII by role;
- cross-user conversation ids;
- omitted/false/true external-source flags and forged external pins/tool calls;
- stale, empty, conflicting, and partial evidence.

## 17. Acceptance criteria

### Correctness and safety

- Existing DB validation, PII, role, and read-only tests pass 100%.
- Canonical NLQ numerical accuracy does not decrease.
- Workbench source-set accuracy is at least 95%.
- No unsupported numeric claim appears in mixed-source evaluation.
- Material vector/web claims trace to supplied evidence.
- Existing conversation records remain readable.
- Omitted or false external_sources_enabled results in zero Qdrant/web operations.
- True external_sources_enabled permits only the role/deployment-authorized intersection.
- Turning access off prevents later turns and direct tools from using external sources.

### Cost and performance

- Median model-call count falls at least 50% across the representative mix.
- Non-cached prompt tokens fall at least 40%.
- Purpose-specific p50/p95 token budgets in Section 10 pass or are revised from documented
  production evidence before becoming release thresholds.
- At least 80% of source selections avoid an LLM router.
- No turn uses more than one user-facing composition call.
- Composer prompts contain no router catalog, complete tool descriptions, DB schema, or
  duplicated structured-output specification.
- Prefix version/hash telemetry proves byte-stable reuse before cache-hit comparisons.
- Single-source p95 latency does not regress.
- Time to first source card does not regress more than 10%.

### Operations

- Every model call has a recorded purpose.
- Feature-flag rollback is tested.
- Legacy and new results can be compared during rollout.
- Dependencies and documentation are current.

## 18. Rollout and rollback

Feature flags:

- WORKBENCH_ORCHESTRATOR_V2
- WORKBENCH_DETERMINISTIC_ROUTING
- WORKBENCH_COMMON_COMPOSER
- WORKBENCH_PERSONALIZE_SUGGESTIONS
- WORKBENCH_EXTERNAL_CONNECTORS_ENABLED as the deployment-wide kill switch; user consent is
  still required when this is true.

Rollout:

1. local and CI tests;
2. evaluation harness;
3. developer dual-path environment;
4. shadow comparison;
5. internal canary;
6. percentage rollout;
7. full rollout and observation;
8. legacy deletion.

Rollback on:

- DB safety or PII failure;
- cross-user history exposure;
- numerical mismatch;
- route accuracy below threshold;
- citation loss or unsupported claims;
- material error increase;
- unacceptable p95 latency;
- broken SSE or incomplete turns.

Rollback is configuration-first. No DB schema rollback is needed in Phases 0–7.

## 19. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Deterministic selector misses unusual phrasing | Retain constrained fallback; expand from evaluated failures |
| Common composer receives too much evidence | Per-tool budgets, compact envelopes, deterministic trimming |
| Common prompt weakens domain quality | Carry concise domain policy in typed evidence; evaluate before deleting old prompts |
| Cache differs under concurrency | Measure cached tokens under realistic slot load and tune deployment |
| Safety migrates into the agent | Keep NLQ opaque and mandatory; authorize/validate outside the model |
| Suggestion UX degrades | Keep compiler suggestions and compare engagement |
| Compaction changes follow-up meaning | Preserve exact structured session state and recent turns |
| UI depends on event timing | Preserve shapes and add contract tests |
| Router fallback never disappears | Track fallback rate/classes and enforce a removal gate |
| Native agent increases calls | Keep Phase 8 optional and benchmark-gated |
| One universal prompt repeats irrelevant context | Separate router, planner, and minimal composer prompts with ownership tests |
| Early measurements use unstable prefixes | Establish deterministic serialization, hashing, and cache telemetry in Phase 0 |
| Lower reasoning/verbosity harms accuracy | Tune only after architecture changes and gate every setting with evaluations |
| UI toggle is mistaken for enforcement | Enforce one shared policy at API, routing, dispatch, tool, and connector boundaries |
| External pin/tool bypasses the chat gate | Reject server-side and cover every direct path with negative tests |
| Old clients omit the new field | Pydantic/API default is false; old history also restores false |
| Toggle is confused with Direct/MCP or local/Groq | Use data-provenance labeling and keep state fields independent |

## 20. Blast radius and effort

Actual repository blast radius after implementation: 35 tracked files changed and 20 new
files at handoff, including production code, tests, lockfile, plan/checklist, and runbooks.
There is no relational DB migration. History changes are additive JSON fields/versioning,
and the frontend/API request change is backward-compatible because consent defaults off.

Recommended Phases 0–7:

- 8–10 substantially changed production files;
- 6–9 lightly changed production files;
- 10–15 changed or new test files;
- 3–4 required frontend files for toggle state, API typing, composer UI, and tests;
- no DB migration;
- one additive JSON history-record version change;
- approximately 1,000–1,700 production lines changed/added, with substantial deletions;
- approximately 7–11 focused engineering days plus the canary observation window.

Optional Phase 8:

- 6–10 additional backend files;
- approximately 800–1,300 additional code/test lines;
- approximately 4–7 additional engineering days;
- primary risk is local tool-call protocol reliability.

## 21. Definition of done

The simplification is complete when:

1. LangGraph and unused LangChain dependencies are absent from Workbench runtime.
2. Workbench uses one plain async orchestrator and one canonical prose transcript.
3. Role/source policy is deterministic and outside model control.
4. New and old conversations default to external sources disabled.
5. One conversation-scoped toggle controls macro, competitive, regulatory, and web together.
6. Effective access is consent ∩ role ∩ deployment and is enforced at every execution path.
7. Direct/MCP, source pinning, and local/Groq settings remain independent controls.
8. Governed NLQ remains the only route to DB execution.
9. Ordinary source selection avoids an LLM call.
10. Vector tools retrieve evidence without separately generating prose.
11. A turn performs no more than one user-facing composition call.
12. Structural DB follow-ups and deterministic lookups use zero model calls.
13. Existing SSE events and old history remain compatible.
14. Telemetry proves the cost and cache targets.
15. Router, DB planner, and composer have distinct minimal prompts with no duplicated rules.
16. Per-call p50/p95 token budgets and prefix-hash checks pass.
17. Reasoning/verbosity settings are tuned only from post-refactor evaluation results.
18. Correctness, security, PII, consent, and citation suites pass.
19. Prior-image rollback and the external-connector kill switch are exercised in deployment.
20. Legacy orchestration, obsolete prompts, and dependencies are removed after rollout.
