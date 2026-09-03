# Workbench Single-Agent Simplification Plan

## Document status

- Status: proposed for implementation
- Scope: backend orchestration, model-call reduction, prompt-cache stability, and conversation state
- Compatibility target: preserve the Workbench HTTP API, SSE events, cards, history UI, and governed NLQ safety boundary
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

The target is one conversational-agent experience, not necessarily one model invocation for
every request. DB planning may remain a separate constrained call because it produces
validated structured intent rather than user-facing prose.

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

## 3. Goals

### Product goals

- Preserve the existing Workbench behavior and UI.
- Give follow-ups one coherent conversational context.
- Continue returning charts, analyses, worklists, briefings, schema cards, citations,
  clarifications, refusals, errors, and partial answers.
- Continue streaming progress and completed source cards.
- Keep source pinning and role-specific visibility.

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

## 4. Non-goals

- Rewriting the semantic catalog, Gold views, QuerySpec compiler, or SQL validator.
- Replacing Qdrant, PostgreSQL, llama.cpp, Groq, or the frontend framework.
- Moving loan-book data to an external model.
- Merging the conversation tables in the first release.
- Adding unrestricted autonomous actions or write-capable DB tools.
- Changing the /api/v1/workbench/ask request shape.
- Redesigning Workbench cards or navigation.
- Completing the separate semantic-view/catalog initiative in this change.

## 5. Baseline to measure

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
- answer correctness, completeness, and refusal correctness;
- SQL validation and repair rates;
- retrieval latency and empty-result rate.

## 6. Target architecture

    canonical Workbench conversation
                 │
    user → auth/role → transcript + structured follow-up resolution
                 │
                 v
       deterministic policy/source selection
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
3. enforce roles, visible sources, and pins;
4. resolve safe structural follow-ups;
5. select tools deterministically where confidence is high;
6. run independent tools concurrently;
7. stream source lifecycle events;
8. isolate individual source failures;
9. render deterministically when one result already answers the question;
10. call one composer when evidence requires prose or comparison;
11. persist the definitive answer and usage;
12. trigger bounded compaction after the turn only when required.

### Source-selection policy

Selection is layered:

1. Authorization removes sources the role cannot use.
2. An allowed explicit pin selects a source without a model.
3. Deterministic grammar recognizes schema, record lookup, DB value, explicit web,
   freshness, regulatory, macro, competitor, and stable-definition requests.
4. Exact and lexical catalog evidence confirms DB coverage.
5. The existing constrained router handles only genuinely ambiguous requests.
6. All model selections are post-validated against role and registered-source policy.
7. Refusal occurs only after policy and catalog checks find no permitted supporting source.

The model router is a temporary ambiguity fallback, not a mandatory stage. Remove it only
after deterministic routing and fallback behavior meet acceptance thresholds.

## 7. Governed tool contracts

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

Macro, competitive, regulatory-document, and knowledge tools return ranked passages and
metadata. They do not each write prose on multi-source requests. A common composer handles
one or several evidence sets. Extractive fallbacks remain available.

### Schema tool

Return only role-permitted abstracted view metadata and approved join paths. Do not expose
raw operational schemas, hidden columns, credentials, or sensitive database statistics.

### Web tool

Accept only a sanitized public-data subquestion. Reject private bank identifiers and internal
figures before an external request. Return URL, title, publication date, measured period when
known, retrieval time, and bounded evidence. Treat all returned content as untrusted.

## 8. Answer composition

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

Composer requirements:

- use supplied facts and passages only;
- never alter or infer figures;
- cite claims using supplied metadata;
- expose missing and conflicting evidence;
- ignore instructions in retrieved content;
- include only role-authorized facts;
- return status, text, sources, citations, unavailable sources, and limitations.

## 9. Model-call budgets

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
| History compaction | 0 normally; 1 only past threshold |

Retries must be reported separately from planned calls.

## 10. Prompt and cache design

Build the common prompt in this order:

1. fixed identity and security rules;
2. fixed, versioned source/tool descriptions in stable sorted order;
3. fixed output contract;
4. bounded conversation transcript;
5. current retrieved evidence;
6. current user request.

Rules:

- No timestamps, random ids, availability state, or evidence in the stable prefix.
- Keep provider/model affinity within a conversation when policy permits.
- Record prompt version, tool-contract version, catalog version, provider, and model.
- Record provider-reported cached tokens.
- Keep tool descriptions byte-for-byte stable.
- Avoid normal-path per-source system prompts.
- Verify exact prefix reuse; logical history equality alone is not a cache hit.
- Preserve the warmed Gold prefix for NLQ until the separate compact-pack work replaces it.
- Test cache behavior under concurrent llama.cpp slots.

## 11. Conversation state

public.workbench_conversations is the canonical user-visible store. Model history contains:

- bounded checkpoint summary;
- mechanically extracted exact session facts and source bindings;
- newest complete turns;
- final assistant answers, not duplicate source-card prose;
- no raw SQL, full chart payloads, large row sets, or hidden lineage.

Keep public.nlq_conversations temporarily for structured analytics state only. A later
migration can place active QuerySpec, entities, and sticky filters in the Workbench record.
Do not combine that migration with the orchestration rollout.

## 12. API and frontend compatibility

Keep:

- POST /api/v1/workbench/ask
- existing question, conversation_id, pinned_source, and data_access fields;
- text/event-stream response;
- conversation, stage, route, source_start, source_card, answer, refusal, error, and done
  events and their current shapes;
- readable version-1 through version-3 history records.

No frontend behavior change should be necessary. Run type-check, production build, and a
streaming end-to-end smoke test. Change frontend code only if an undocumented dependency on
stage timing or route labels appears.

## 13. Repository change map

| File/area | Change | Risk |
|---|---|---|
| backend/app/services/workbench/graph.py | Replace StateGraph with plain async orchestration; preserve run_workbench | Medium |
| backend/app/services/workbench/router.py | Deterministic-first selection, confidence, reason, optional model fallback | Medium |
| backend/app/services/workbench/nodes.py | Split retrieval/execution from per-source prose; typed results | Medium-high |
| backend/app/services/workbench/models.py | Simplify model purposes; retain sensitive/local enforcement | Low |
| backend/app/services/workbench/history.py | Aggregate usage and source/tool state compatibly | Medium |
| backend/app/services/workbench/compaction/* | Adapt only if result envelope changes require it | Low-medium |
| backend/app/services/workbench/suggestions.py | Remove default critical-path model call | Low |
| backend/app/api/routes/workbench.py | Import/documentation changes only | Low |
| backend/app/services/nlq/ask.py | Telemetry/tool-boundary metadata; preserve behavior | Low-medium |
| backend/app/services/nlq/llm/client.py | Call-purpose telemetry; no native tools initially | Low |
| pyproject.toml, uv.lock, backend/Dockerfile | Remove unused graph dependencies | Low |
| backend/tests/workbench/* | Framework-neutral orchestration, routing, contract, budget tests | Medium |
| frontend | Expected no functional change; verify contracts | Low |

No DB migration is required for the recommended rollout.

## 14. Implementation phases

### Phase 0 — Baseline and safeguards

- Add call-purpose and per-turn usage telemetry.
- Build a representative fixture for all sources and mixed paths.
- Measure current calls, tokens, cache behavior, latency, correctness, and failures.
- Add model-call-budget test helpers.
- Add flags for the new orchestrator, deterministic routing, common composer, and optional
  suggestion personalization.
- Run existing backend, NLQ, Workbench, and frontend checks.

Exit:

- Baseline is recorded.
- Every target path has a measured call count.
- Legacy/new selection is tested.
- Current suites pass or existing failures are documented.

### Phase 1 — Remove optional critical-path calls

- Disable LLM next-step personalization by default.
- Return existing compiler-checked suggestions.
- Bypass model routing for allowed pins, deterministic lookups, and structural DB follow-ups.
- Preserve exact DB question text.

Exit:

- DB drill UX works.
- Known deterministic paths meet their call budgets.
- Safety suites pass.

### Phase 2 — Replace LangGraph

- Extract ordinary async route, dispatch, and answer functions.
- Preserve gather-based fan-out, SSE queue, failure isolation, cancellation, persistence, and
  background compaction.
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
- Return confidence, reason, policy version, and fallback-used telemetry.
- Define deterministic precedence for overlapping cues.
- Use constrained routing only for ambiguous cases.
- Build regression cases from observed misses rather than hardcoding question answers.

Exit:

- Source-set accuracy is at least 95%.
- At least 80% of representative turns avoid the router model.
- Permission/destructive-request tests pass 100%.
- Fallback remains safe and observable.

### Phase 4 — Retrieval-only vector sources

- Introduce the common ToolResult/evidence envelope.
- Convert macro, competitive, regulatory-document, knowledge, and web paths as applicable.
- Preserve metadata, citation/page protections, source failure isolation, and degraded modes.
- Bound passages and evidence tokens.
- Keep DB behavior behind the same typed boundary.

Exit:

- Source handlers return typed results.
- Vector sources do not separately synthesize before common composition.
- Existing cards render unchanged.
- Citation and limitation tests pass.

### Phase 5 — Common composer

- Define a stable versioned composer prompt and typed answer.
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

- Freeze and version the common prefix.
- Keep all dynamic data after it.
- Verify deployed llama.cpp cached-token behavior at production-like concurrency.
- Confirm Workbench is the only prose transcript.
- Keep NLQ state structured-only.
- Re-tune transcript and compaction thresholds from measured prompts.
- Test long conversations and overflow behavior.

Exit:

- Cached-token ratio improves from baseline.
- Long-history and compaction tests pass.
- Cross-user isolation remains intact.
- Prompts contain no unauthorized data.

### Phase 7 — Rollout and cleanup

- Shadow compare legacy and new paths where possible.
- Canary by user or percentage.
- Monitor calls, tokens, cache, latency, correctness, partial answers, errors, and validation.
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

## 15. Testing strategy

### Unit

- routing predicates and precedence;
- role and pin filtering;
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
- MCP and direct PostgreSQL modes;
- persisted reload and follow-up.

### Contract/UI

- schema/order checks for all SSE events;
- existing frontend event consumption;
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
- stale, empty, conflicting, and partial evidence.

## 16. Acceptance criteria

### Correctness and safety

- Existing DB validation, PII, role, and read-only tests pass 100%.
- Canonical NLQ numerical accuracy does not decrease.
- Workbench source-set accuracy is at least 95%.
- No unsupported numeric claim appears in mixed-source evaluation.
- Material vector/web claims trace to supplied evidence.
- Existing conversation records remain readable.

### Cost and performance

- Median model-call count falls at least 50% across the representative mix.
- Non-cached prompt tokens fall at least 40%.
- At least 80% of source selections avoid an LLM router.
- No turn uses more than one user-facing composition call.
- Single-source p95 latency does not regress.
- Time to first source card does not regress more than 10%.

### Operations

- Every model call has a recorded purpose.
- Feature-flag rollback is tested.
- Legacy and new results can be compared during rollout.
- Dependencies and documentation are current.

## 17. Rollout and rollback

Feature flags:

- WORKBENCH_ORCHESTRATOR_V2
- WORKBENCH_DETERMINISTIC_ROUTING
- WORKBENCH_COMMON_COMPOSER
- WORKBENCH_PERSONALIZE_SUGGESTIONS

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

## 18. Risks and mitigations

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

## 19. Blast radius and effort

Recommended Phases 0–7:

- 5–7 substantially changed production files;
- 4–6 lightly changed production files;
- 8–12 changed or new test files;
- zero expected frontend behavior changes;
- no DB migration;
- approximately 700–1,200 production lines changed/added, with substantial deletions;
- approximately 5–8 focused engineering days plus the canary observation window.

Optional Phase 8:

- 6–10 additional backend files;
- approximately 800–1,300 additional code/test lines;
- approximately 4–7 additional engineering days;
- primary risk is local tool-call protocol reliability.

## 20. Definition of done

The simplification is complete when:

1. LangGraph and unused LangChain dependencies are absent from Workbench runtime.
2. Workbench uses one plain async orchestrator and one canonical prose transcript.
3. Role/source policy is deterministic and outside model control.
4. Governed NLQ remains the only route to DB execution.
5. Ordinary source selection avoids an LLM call.
6. Vector tools retrieve evidence without separately generating prose.
7. A turn performs no more than one user-facing composition call.
8. Structural DB follow-ups and deterministic lookups use zero model calls.
9. Existing SSE events and history records remain compatible.
10. Telemetry proves the cost and cache targets.
11. Correctness, security, PII, and citation suites pass.
12. Feature-flag rollback is tested.
13. Legacy orchestration, obsolete prompts, and dependencies are removed after rollout.
