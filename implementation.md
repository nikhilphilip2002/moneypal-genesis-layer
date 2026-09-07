# Implementation Plan: Governed Native-Tool Workbench

## 1. Goal

Implement the architecture in `REGEX_PLAN.md` by introducing a native-tool agent over the
existing governed MoneyPal capabilities, proving it against the current system, and then
retiring only the linguistic heuristics it safely replaces.

This plan changes orchestration, not authority. The LLM interprets language and selects
capabilities. Existing application code continues to own access, privacy, metrics, SQL,
calculations, charts, citations, lineage, persistence, and streaming.

## 2. Non-negotiable protocol rules

1. The agentic path accepts only provider-native `tool_calls`.
2. `tools` and `json_schema` are mutually exclusive request modes.
3. Assistant text containing JSON, XML-like tags, fenced JSON, or a tool name is never
   interpreted as a tool call.
4. A provider without certified native-tool support cannot run the agentic path.
5. Malformed native tool arguments may receive one native repair round; they are never sent
   through a structured-output compatibility path.
6. After repair failure, the turn degrades to an eligible deterministic path, clarification,
   or an explicit error.
7. Existing structured-output NLQ and text-to-SQL calls may remain operational during
   migration, but they are separate workflows—not fallback transports for tool calling.
8. Every call is authorized and validated again at execution time, even if its schema was
   filtered before being shown to the model.

Parsing the JSON-encoded `function.arguments` field inside a genuine native tool-call frame is
part of the native protocol and is permitted. Parsing assistant `content` as a tool call is not.

## 3. Target turn lifecycle

```text
HTTP request
  -> establish identity, role, source consent, deployment policy, and turn budget
  -> load linear history and governed session anchors
  -> run mandatory deterministic checks
       - source pin and access policy
       - destructive/unsupported operation refusal
       - exact fast path when enabled for the rollout mode
  -> native agent selection call with only authorized tools
  -> validate tool-call envelope and typed arguments
       - invalid: return native tool error and allow one repair
       - unauthorized: refuse without execution
       - external: pass through outbound policy gateway
  -> emit route and source_start frames
  -> execute independent calls concurrently under one turn budget
  -> persist and emit source_card frames as calls complete
  -> append bounded native tool-result messages to the agent transcript
  -> allow another tool round only when a result is required by a later call
  -> request final prose with tool_choice=none
  -> validate answer shape and numeric claims
       - invalid numeric claim: one focused synthesis repair
       - still invalid: omit unsupported claim or use governed source summary
  -> emit and persist answer, usage, timing, and done
```

Default limits for the first canary should be conservative and configurable:

- maximum 3 agent rounds, including selection and final synthesis;
- maximum 6 executed tool calls per turn;
- maximum 1 argument-repair round;
- maximum 1 synthesis-repair round;
- one existing end-to-end request deadline shared by model calls and tools;
- existing evidence, row, and output-token caps remain in force.

## 4. Workstream A: Native tool support in the LLM client

### Files

- `backend/app/services/nlq/llm/client.py`
- `backend/app/services/nlq/llm/messages.py`
- `backend/app/services/nlq/llm/telemetry.py`
- `backend/tests/nlq/test_llm_client.py`

### Changes

Add explicit native-tool contracts:

- `NativeToolCall`
  - `id: str`
  - `name: str`
  - `arguments: dict[str, Any]`
- Extend `LLMResult` with:
  - `tool_calls: list[NativeToolCall]`
  - the provider-native assistant message needed for tool-result replay;
- widen message typing from `dict[str, str]` to an explicit chat-message type capable of
  representing assistant `tool_calls` and `role="tool"` messages;
- extend `LLMClient.complete()` with `tools`, `tool_choice`, and
  `parallel_tool_calls` parameters;
- add `supports_native_tools` to the provider profile.

Request construction rules:

- reject a request containing both `tools` and `json_schema` before network I/O;
- include tool-related fields only in native-tool mode;
- preserve existing llama.cpp cache/thinking controls;
- never add a prompt asking the model to return tool JSON;
- do not silently remove unsupported tool fields for a provider.

Response parsing rules:

- read calls only from `choices[0].message.tool_calls`;
- require a call ID, `type="function"`, a known non-empty function name, and arguments that
  decode to an object;
- reject duplicate call IDs;
- preserve call order;
- permit empty `content` when valid tool calls are present;
- never call `LLMResult.json()` to recover a tool call;
- represent malformed native calls as a typed protocol error so the orchestrator can decide
  whether its one repair is still available.

Telemetry must record call count, tool names, finish reason, provider/model, duration, and
token usage. Raw arguments and tool results must use the existing sensitive logging policy;
external-policy denials must be recorded without leaking the denied value into general logs.

### Tests

- tools and `tool_choice` appear exactly in the outbound payload;
- `tools + json_schema` is rejected locally;
- one and several native tool calls parse successfully;
- native arguments are decoded and must be an object;
- missing IDs, unknown shapes, duplicate IDs, invalid JSON arguments, and content-only JSON
  fail as protocol errors;
- empty content plus valid tool calls succeeds;
- assistant tool-call messages and matching tool results replay without being coalesced or
  converted to text;
- provider profiles without native-tool support are rejected;
- existing non-tool structured-output tests continue to cover only legacy workflows.

## 5. Workstream B: Flat catalog-derived agent tool registry

### Files

- add `backend/app/services/workbench/agent_tools.py`
- add `backend/app/services/workbench/agent_contracts.py`
- retain `backend/app/services/workbench/tools.py` for the UI quick-action registry
- `backend/app/services/workbench/access.py`
- `backend/app/services/nlq/llm/schemas.py`
- add `backend/tests/workbench/test_agent_tools.py`

### Tool set

Expose one concrete native tool per materially different argument contract. Do not publish a
polymorphic `query_loan_book` schema and do not generate `oneOf`, `anyOf`, conditional, or
discriminator branches for native tool parameters.

| Native tool | Canonical argument contract | Capability |
|---|---|---|
| `query_metrics` | `QuerySpec` | Governed portfolio metrics and comparisons |
| `lookup_records` | `LookupPlan` | Borrower, account, and loan lookup |
| `run_analysis` | `AnalysisPlan` without planner metadata | Reviewed multi-chart analysis |
| `create_worklist` | `WorklistPlan` without planner metadata | Reviewed collection worklist |
| `generate_briefing` | `BriefingPlan` without planner metadata | Persona briefing |
| `run_validated_query` | validated-query request | Governed catalog-miss SQL path |
| `search_curated_knowledge` | domain plus query | Concepts, schema, macro, competitive, and regulatory collections |
| `search_public_web` | public search query | Live external retrieval through the outbound policy gateway |
| `finish_without_data` | outcome plus response fields | Clarification or refusal without data execution |

Nine flat tools are preferable to one six-branch mega-tool. Tool selection is a model routing
decision; argument validation should not also require the model and every provider to resolve a
large polymorphic object union.

#### Loan-book tool contracts

- `query_metrics` exposes the complete `QuerySpec`: one or more metrics and dimensions, typed
  filters, aggregate conditions, relative or explicit periods, comparison period, ordering,
  limit, share intent, and driver explanation. Metric, dimension, filter, and ordering values
  come from the active catalog.
- `lookup_records` exposes the complete `LookupPlan` selector, value, detail, and
  requested-field vocabulary.
- `run_analysis` accepts a catalog-derived `analysis_id`, typed period, and compatible filters.
- `create_worklist` accepts a catalog-derived `worklist_id`, the narrower worklist filter
  vocabulary, and a bounded limit.
- `generate_briefing` accepts a catalog-derived `persona_id`.
- `run_validated_query` accepts a catalog-miss intent and allowed catalog tables. It routes
  through the existing read-only SQL generator and validator while that separately governed
  capability remains supported; it is not a tool-call protocol fallback.

Example:

```json
{
  "metrics": ["par_30"],
  "dimensions": ["branch"],
  "period": {"relative": "this_month"}
}
```

Each tool has a top-level object schema with `additionalProperties: false`. Keep branch-like
keywords out of the emitted provider schemas. For a provider strict mode that requires every
declared property, represent optional values using the provider-supported nullable form and
require the property; otherwise omit optional fields normally. Inline schema fragments when a
provider cannot resolve `$ref`. Provider projections must preserve the canonical Pydantic
contract rather than weakening its semantics.

Pydantic remains a mandatory execution-boundary check with `extra="forbid"`, catalog-aware
semantic validation, and normal cross-field validation inside an individual contract. It is a
second layer, not a replacement for useful tool schemas. Invalid arguments receive the one
native repair allowed in Section 2 and never execute before validation succeeds.

#### `search_curated_knowledge`

Shape:

```json
{
  "domain": "concepts | schema | macro | competitive | regulatory",
  "query": "..."
}
```

Use “curated” rather than “internal” because macro, competitive, and regulatory documents are
published external material even when the searchable index is hosted locally. The domain is
required and its enum is generated for the request from role, consent, and deployment policy.
The executor repeats that domain-level access check.

#### `search_public_web`

Shape:

```json
{
  "search_query": "..."
}
```

This tool is exposed only when live external search is authorized. Every call still crosses
the outbound policy gateway immediately before network I/O.

#### `finish_without_data`

Shape:

```json
{
  "outcome": "clarify | refuse",
  "message": "...",
  "suggestions": [],
  "reason_code": null
}
```

- `message` is the clarifying question or bounded refusal text.
- `suggestions` contains at most three choices and is empty for refusal.
- `reason_code` is null for clarification and an approved code for refusal.

Keep this as one flat object because both outcomes share the same response contract. Pydantic
enforces the outcome-dependent null/empty rules after the provider-level type validation; the
schema does not use a union.

This is a terminal tool. It performs no data access and prevents a required-tool selection
round from inventing a data call merely because the correct outcome is clarification or
refusal.

The registry owns for each tool and curated-knowledge domain:

- native function schema;
- typed argument model;
- source ID and source group;
- sensitivity classification;
- eligible roles;
- whether external consent is required;
- handler;
- execution timeout and result-size limits;
- whether calls of this type may execute in parallel.

Generate the visible tool list and allowed curated domains from the immutable request policy.
Omit an entire loan-book tool when it is not permitted. If only some curated domains are
permitted, emit only those enum values; omit the search tool if none remain. The executor must
repeat the same tool/domain checks so a forged function name, domain, or stale tool list cannot
widen access.

Do not copy catalog values into handwritten enums. Extract reusable schema fragments from the
current planner schema builder so the legacy planner and native tool registry share the same
source of truth. Keep the full governed contracts; do not revive the reduced single-metric
schema from the earlier abstract proposal.

### Tests

- every active catalog metric, dimension, analysis, worklist, persona, and lookup field is
  represented in the corresponding concrete tool;
- emitted native tool schemas contain no `oneOf`, `anyOf`, conditional, or discriminator
  branches;
- arguments belonging to another tool and unknown extra fields are rejected;
- generated schemas prohibit additional properties and require load-bearing fields;
- every tool/domain has a registered source/sensitivity/policy classification;
- role and consent combinations expose exactly the permitted tools and domains;
- forbidden curated domains cannot be recovered by forging the domain value;
- direct execution repeats access checks;
- canonical Pydantic contracts and provider schema projections cannot drift unnoticed;
- every certified provider accepts all nine schemas in a startup/CI compatibility probe;
- llama.cpp schema-to-grammar compilation is bounded and tested for each emitted schema.

## 6. Workstream C: Governed tool execution

### Files

- add `backend/app/services/workbench/agent_executor.py`
- refactor `backend/app/services/workbench/nodes.py`
- refactor reusable execution from `backend/app/services/nlq/ask.py`
- reuse:
  - `backend/app/services/nlq/pipeline.py`
  - `backend/app/services/nlq/lookup.py`
  - `backend/app/services/nlq/analysis.py`
  - `backend/app/services/worklists/runner.py`
  - existing briefing/signal services
  - current macro, competitive, regulatory, knowledge, schema, and web nodes
- add `backend/tests/workbench/test_agent_executor.py`

### Changes

Create one dispatcher that accepts a validated native call plus immutable execution context:

- user and role;
- conversation and turn IDs;
- source-access policy;
- remaining turn deadline;
- catalog version;
- data-access mode.

Map calls directly to existing governed services:

- `query_metrics(...)` -> `QuerySpec` -> `pipeline.run_spec()`;
- `lookup_records(...)` -> `LookupPlan` -> `lookup.run()`;
- `run_analysis(...)` -> existing reviewed analysis build/run/compose path;
- `create_worklist(...)` -> existing reviewed worklist runner;
- `generate_briefing(...)` -> existing signal/briefing service;
- `run_validated_query(...)` -> current validated SQL service while it remains supported; its
  internal structured-output call is not a tool-call transport;
- `search_curated_knowledge(domain=...)` -> the matching knowledge, schema, macro,
  competitive, or regulatory node;
- `search_public_web(...)` -> the outbound policy gateway and existing web node;
- `finish_without_data(outcome=...)` -> the existing clarification or refusal contract.

Refactor the non-streaming plan execution currently embedded in `ask.py` into reusable service
functions rather than invoking `ask_once()` and causing a second planning pass. Both legacy
`ask_stream()` and agent tools should consume those functions so execution behavior cannot
diverge.

Return two representations from each execution:

1. the complete existing `ToolResult`/card payload for UI, persistence, export, and lineage;
2. a bounded `AgentToolResult` for model replay containing status, summary, facts, citations,
   limitations, and a card reference—but not unrestricted rows, SQL, hidden lineage, or tool
   traces.

Use a structured error envelope with stable codes such as:

- `INVALID_TOOL_ARGUMENTS`
- `TOOL_ACCESS_DENIED`
- `PII_POLICY_VIOLATION`
- `COMPILE_REJECTED`
- `NO_MATCHING_ROWS`
- `TOOL_TIMEOUT`
- `SOURCE_UNAVAILABLE`

Errors exposed to the model must be sufficient for repair without exposing schemas, private
matches, raw database errors, or secrets.

### Tests

- every tool/domain maps to the correct existing governed service;
- compiler, masking, lineage, and chart behavior match the legacy path for identical plans;
- independent calls execute concurrently and dependent calls do not;
- one failed source does not cancel successful independent sources;
- shared deadline and per-turn tool limits are enforced;
- tool-result replay is bounded and excludes SQL/private fields not intended for synthesis;
- stable error codes map to repairable versus terminal behavior.

## 7. Workstream D: Outbound policy gateway

### Files

- add `backend/app/services/workbench/outbound_policy.py`
- update `backend/app/services/workbench/web.py`
- update `backend/app/services/workbench/access.py`
- add `backend/tests/workbench/test_outbound_policy.py`
- extend `backend/tests/workbench/test_web.py`

### Changes

Make the gateway the only callable boundary to live external connectors. Calling the Exa
client directly from an agent handler must not be possible.

Validation order:

1. confirm the tool is a live-external capability;
2. enforce role, deployment availability, and per-conversation consent;
3. recursively collect every string from the tool arguments;
4. normalize Unicode, whitespace, punctuation variants, and identifier separators;
5. detect government IDs, phone numbers, account/customer/loan identifiers, repayment-detail
   requests, and private entities available in the current session;
6. remove the internal half of an explicitly separable public comparison only when the
   result remains a complete public query;
7. reject otherwise ambiguous or private requests;
8. apply length, domain, result-count, rate, and timeout bounds;
9. audit allow/deny and only then perform network I/O.

Reuse and strengthen `web.public_query()` rather than creating a second competing sanitizer.
Preserve official-source prioritization, URL normalization, citation metadata, result bounds,
and the explicit untrusted-content wrapper.

On denial, return `PII_POLICY_VIOLATION` as the native tool result for that call ID. Permit one
agent repair. Run the repaired call through the entire gateway again; never reuse the prior
decision. A second denial becomes a refusal and performs no network request.

The primary agent always uses the local provider because its input may contain private history.
Any optional external-model synthesis must receive only gateway-approved public material and
must remain outside the private agent transcript.

### Tests

- all existing private-query cases remain blocked;
- formatted and unformatted Aadhaar, PAN, phones, account/customer IDs, Unicode separators,
  and mixed-case values are covered;
- nested arguments are scanned;
- denied calls invoke no connector;
- repaired calls are independently revalidated;
- the second violation refuses;
- consent, role, deployment, rate, and domain rules fail closed;
- public macro/regulatory queries still succeed;
- web content remains marked untrusted and cannot create new tool instructions.

## 8. Workstream E: Agent loop and orchestration

### Files

- add `backend/app/services/workbench/agent.py`
- add agent prompt builders to `backend/app/services/workbench/prompts.py`
- update `backend/app/services/workbench/orchestrator.py`
- update `backend/app/services/workbench/graph.py`
- update `backend/app/services/workbench/models.py`
- update `backend/app/core/config.py`
- add `backend/tests/workbench/test_agent.py`
- extend `backend/tests/workbench/test_graph.py`

### Configuration

Add an explicit rollout mode:

- `WORKBENCH_AGENT_MODE=off|shadow|canary|on`
- `WORKBENCH_AGENT_CANARY_PERCENT`
- `WORKBENCH_AGENT_MAX_ROUNDS`
- `WORKBENCH_AGENT_MAX_TOOL_CALLS`
- `WORKBENCH_AGENT_ARGUMENT_REPAIRS=1`
- `WORKBENCH_AGENT_SYNTHESIS_REPAIRS=1`

`off` retains current behavior. `shadow` records native agent selections without executing
them. `canary` uses a stable conversation/user hash so a conversation does not switch
orchestrators mid-thread. `on` uses the agent after mandatory policy checks and retained exact
fast paths.

### Selection call

Build messages in this order:

1. stable agent system prompt;
2. mechanically rendered governed session state;
3. recent linear transcript;
4. current user question.

Pass only policy-visible native tools. Use native `tool_choice="required"` where the certified
provider supports it; otherwise treat a content-only selection response as a protocol failure,
not as an answer or JSON plan. The system prompt names only the tools emitted for that request
and requires one or more calls, using `finish_without_data` when the correct outcome is
clarification or refusal.

Validate the full batch before starting execution. Reject the individual invalid call without
executing it; independent valid calls may proceed only if doing so cannot produce a misleading
partial answer. Preserve model call order for transcript replay and use a stable source order
for the route frame.

### Multi-round behavior

- Execute independent calls concurrently with the existing source isolation behavior.
- Append the original native assistant tool-call message followed by one matching `role=tool`
  message per call ID.
- Permit a later tool round only when a new call depends on prior results.
- Count validation failures and denied calls against the total round/call budgets.
- Stop immediately on a terminal clarification/refusal tool.
- Final synthesis uses the same native conversation but `tool_choice="none"`; any further tool
  call is rejected as a phase error.

### Deterministic paths retained initially

- access and source-pin decisions;
- destructive-operation refusal;
- exact identifier/record resolution where confidence is deterministic;
- compiler-generated drill actions and exact active-plan refinements;
- saved-query/dashboard execution;
- current proven metric fast paths while shadow/canary evidence is collected.

Do not add new linguistic regexes during rollout. Instrument which retained rules fire and
remove them individually in the final phase when the agent demonstrates better outcomes.

### SSE behavior

Keep the current public protocol:

- `conversation`
- `stage`
- `route`
- `source_start`
- `source_card`
- `answer`
- `refusal` or `error` where applicable
- `done`

Agent rounds and repairs should use existing stage frames or optional additive diagnostic
metadata; do not expose raw tool arguments or internal reasoning. `done` remains exactly once
and last. Cancellation must stop the agent request and all in-flight tool tasks.

### Tests

- every concrete loan-book tool and every permitted curated-knowledge domain;
- one-tool, parallel multi-tool, dependent two-round, clarification, and refusal turns;
- parallel calls using different concrete tools and repeated calls to the same tool;
- content-only JSON never executes;
- one native argument repair and hard stop after the second failure;
- route/source card ordering and exactly-once completion;
- cancellation propagates to model and tools;
- access policy cannot be bypassed by a forged call;
- local provider is always selected when private history is present;
- deterministic degradation works without invoking legacy JSON as tool calls;
- shadow mode never executes shadow tools or changes the user-visible result;
- canary assignment is stable for the conversation.

## 9. Workstream F: Numeric fact ledger and synthesis repair

### Files

- add `backend/app/services/workbench/facts.py`
- add `backend/app/services/workbench/calculations.py`
- update `backend/app/services/workbench/composer.py`
- update `backend/app/services/workbench/prompts.py`
- update `backend/app/services/workbench/graph.py`
- add `backend/tests/workbench/test_facts.py`
- extend `backend/tests/workbench/test_results.py`

### Fact contract

Create a typed fact record with:

- stable fact ID;
- label and normalized numeric value;
- display value and unit;
- period and dimensions;
- source/card/row reference;
- verification status;
- optional formula, operand fact IDs, and operation for derived facts.

Build facts directly from typed chart columns/rows and reviewed analysis findings. External
document numbers remain evidence claims with citations and must not be promoted to audited
loan-book facts.

Provide deterministic calculations for supported operations such as absolute difference,
percentage change, share, ratio, sum, and weighted average. Reject divide-by-zero, mixed-unit,
missing-period, and incompatible-grain calculations.

### Validation and repair

Replace `numbers_are_grounded()` with claim-aware validation:

1. compare numeric claims in the draft with supplied facts and approved derived facts;
2. retain harmless non-data numbers only through an explicit allowlist, such as ordered-list
   markers—not by accidental regex behavior;
3. if unsupported claims exist, append a focused repair instruction naming the unsupported
   claim and reiterating that only provided results and governed calculations may be used;
4. request one new final answer with `tool_choice="none"`;
5. revalidate from scratch;
6. if still invalid, remove unsupported numeric sentences when that is unambiguous; otherwise
   use the governed source summary and attach a composer limitation.

Do not discard a valid qualitative paragraph because a separate numeric sentence failed.
Do not allow the repair turn to call tools, introduce new evidence, or receive a refreshed
budget.

### Tests

- exact facts with formatting variants pass;
- deterministically computed growth/share/delta claims pass with provenance;
- invented values, wrong units, wrong periods, and altered signs fail;
- one repair can recover the answer;
- a second failure removes the claim or selects the governed summary;
- valid prose survives removal of an invalid numeric sentence;
- source citations and limitations remain attached.

## 10. Workstream G: History and governed session anchors

### Files

- update `backend/app/services/workbench/history.py`
- update `backend/app/services/workbench/compaction/state.py`
- update `backend/app/services/workbench/compaction/summarize.py`
- retain legacy behavior in `backend/app/services/nlq/conversation.py`
- extend `backend/tests/workbench/test_history.py`
- extend `backend/tests/workbench/test_compaction_integration.py`
- extend `backend/tests/nlq/test_conversation.py`

### Changes

Persist enough information to reconstruct a valid native transcript and exact semantic
references without persisting chain-of-thought:

- sanitized native call ID, tool name, and validated arguments;
- bounded tool-result envelope;
- source/card reference;
- last governed `QuerySpec` or reviewed plan reference;
- active filters and selected entities;
- ordered/ranked row references needed by phrases such as “the leading agent”;
- offered deterministic drill actions;
- fact ledger references;
- repair/error outcome and tool/model usage.

Add an agent transcript builder that emits valid `user`, assistant-with-`tool_calls`, `tool`,
and final `assistant` messages. Tool results must match their call IDs. Clip whole completed
tool exchanges rather than leaving an assistant call without its result.

Extend mechanically extracted session state with governed plan/entity/result anchors. Continue
to derive exact figures and state from stored structured cards rather than from an LLM summary.

Do not remove the legacy NLQ conversation resolver or table in this project. Legacy `/nlq`
continues to use it until the separate storage migration is complete.

Compaction behavior remains context-window-derived and disabled by default. The only immediate
change is to skip scheduling its post-turn check when disabled. When enabled, summary output
must never replace exact tool exchanges or governed anchors needed for execution.

### Tests

- native transcripts preserve valid call/result pairing;
- clipping never creates orphaned tool messages;
- “why,” “those schemes,” “that branch,” and ranked-entity follow-ups resolve from anchors;
- no cross-user or cross-conversation state leakage;
- compaction preserves exact facts and active plan references;
- legacy NLQ conversation tests remain unchanged and passing.

## 11. Workstream H: UI quick actions and naming

### Files

- optionally rename `backend/app/services/workbench/tools.py` to
  `backend/app/services/workbench/quick_actions.py`
- update `backend/app/api/routes/workbench.py`
- retain a temporary compatibility import if renamed
- `backend/tests/workbench/test_tools.py`
- `backend/tests/workbench/test_api.py`
- `backend/tests/workbench/test_frontend_contract.py`

This rename is housekeeping and should be its own small change. It must not be coupled to the
agent rollout. Preserve `GET /workbench/tools`, `POST /workbench/tool/{tool_id}`, response
payloads, role checks, and frontend behavior. Agent tools live only in `agent_tools.py`; UI
quick actions are not automatically callable by the LLM.

## 12. Delivery sequence

Deliver as reviewable changes with the following dependency order:

1. **Native client contracts and tests**
   - no orchestration change;
   - hard prohibition on JSON-emulated tool calls.
2. **Catalog schema extraction and agent registry**
   - schema parity tests;
   - no tools executed by production traffic.
3. **Reusable governed plan execution**
   - legacy and tool handlers share execution services;
   - parity tests against existing outputs.
4. **Outbound policy gateway**
   - move existing web execution behind it before agent web access exists.
5. **Agent executor and bounded result envelopes**
   - direct unit/integration tests only.
6. **History/tool transcript and semantic anchors**
   - additive record version with backward reads.
7. **Shadow agent mode**
   - compare selections; never execute shadow calls.
8. **Numeric fact ledger and synthesis repair**
   - enable before richer agent-generated financial prose.
9. **Canary mode for ambiguous traffic**
   - stable assignment, immediate kill switch, deterministic degradation.
10. **Broader agent rollout**
    - promote only after release gates pass.
11. **Regex retirement batches**
    - one behavior group per change, each independently reversible.
12. **Optional quick-action rename**
    - isolated from functional migration.

## 13. Evaluation and release gates

### Automated suites

Run at minimum:

- all `backend/tests/nlq` tests;
- all `backend/tests/workbench` tests;
- API and frontend contract tests;
- the 100-question executive corpus at the production request deadline;
- complete five-turn chain evaluation;
- a new native-tool protocol conformance suite;
- a new privacy/prompt-injection adversarial suite.

### Metrics

Compare old and candidate paths on:

- correct source set;
- exact tool/plan type;
- metric, dimension, period, filter, comparison, and ordering accuracy;
- answer-shape correctness;
- audited result equivalence;
- useful-answer rate;
- complete five-turn conversation rate;
- refusal and clarification quality;
- timeout rate and P50/P95 latency;
- model calls, tool calls, retries, and token use per successful answer;
- unsupported numeric claim rate;
- policy-denial and private-egress results.

### Zero-regression gates

- no private data reaches a live external connector in the adversarial suite;
- no role, consent, or deployment policy bypass;
- no change to audited metric values, formulas, sign-off, masking, or lineage;
- no native tool call is reconstructed from assistant content;
- no raw or unvalidated SQL reaches execution;
- no breaking SSE, chart, history, quick-action, or frontend contract change.

### Promotion gates

- shadow results meet the agreed tool-selection and argument-accuracy target;
- canary useful-answer and five-turn completion rates materially exceed baseline;
- P95 latency and timeout rates are no worse than baseline;
- native-tool repair remains within configured limits;
- provider failures consistently produce a governed deterministic result, clarification, or
  explicit error;
- every rollout mode has been exercised and the kill switch verified.

Record concrete thresholds alongside the frozen Phase 0 benchmark before enabling canary
traffic.

## 14. Rollback strategy

- `WORKBENCH_AGENT_MODE=off` immediately restores the current orchestrator.
- Keep existing router/planner modules intact through shadow and canary.
- Store agent history additively with a record version that older readers can ignore.
- Do not delete a heuristic in the same change that first enables its agent replacement.
- Keep each regex-retirement batch independently revertible.
- Outbound policy enforcement is not rolled back with the agent; it remains the mandatory web
  boundary after introduction.
- Numeric provenance is not bypassed during rollback; the current conservative grounding
  behavior remains until the replacement validator is active and proven.

## 15. Definition of done

The migration is complete when:

- production agent turns use provider-native tool calls exclusively;
- all agent tools are catalog-derived, typed, policy-filtered, and reauthorized on execution;
- the full governed capability set has parity with the previous NLQ/workbench behavior;
- conversation references resolve using a valid native transcript plus exact semantic anchors;
- external calls pass one audited outbound gateway with bounded native repair;
- derived financial figures are reproducible from stored facts and calculations;
- unsupported numeric claims receive one repair and cannot silently ship;
- existing UI, SSE, history, chart, citation, export, masking, and lineage contracts pass;
- benchmark accuracy and completed-chain results meet the recorded promotion thresholds;
- model/provider failure never triggers JSON-emulated tool calling;
- obsolete linguistic regexes have been retired only where measured evidence supports removal;
- legacy structured-output callers are either explicitly retained as separate supported
  workflows or migrated in a separately reviewed change.
