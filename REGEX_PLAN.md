# Architectural Plan: Governed Agentic Workbench

## 1. Decision

Evolve MoneyPal from broad linguistic regex interception toward native LLM tool calling,
but do so incrementally and without weakening deterministic governance.

- use the LLM for language understanding, source selection, and ambiguous follow-ups;
- use governed tools for metrics, records, analyses, worklists, and external retrieval;
- keep deterministic code for authorization, privacy, calculation, validation, and rendering;
- retain proven fast paths until the agent demonstrates equal or better accuracy and latency;
- remove individual heuristics only after their replacements pass measured rollout gates.

This supersedes a wholesale replacement. Native tool calling is adopted as an orchestration
interface.


## 2. Findings and Responses

### Finding 1: Linguistic regexes are carrying too much product behavior

Routing, record-intent recognition, metric shortcuts, and conversational rewrites contain a
large and growing collection of phrasing-specific rules. These rules improve known queries
but are costly to extend and fragile for unseen language.

**Response:** Move ambiguous natural-language interpretation to a tool-capable agent.

### Finding 2: The governed semantic layer is the system’s strongest asset

`QuerySpec`, the metric and dimension catalogs, reviewed analyses and worklists, the compiler,
parameterized execution, chart construction, lineage, and masking provide correctness that
raw text-to-SQL or loosely structured tools cannot match.

**Response:** Make these capabilities the implementation behind agent tools. Tool calls must
map to the complete governed contracts rather than a reduced approximation. The agent may
choose and populate a capability; it may not invent formulas, SQL, catalog identifiers, or
authorization rules.

The governed interface must retain feature parity for:

- one or more metrics and dimensions;
- typed filters and aggregate conditions;
- relative and explicit periods;
- comparisons, ordering, limits, shares, and driver explanations;
- record lookups and requested record fields;
- reviewed analyses, worklists, and briefings;
- clarification and refusal outcomes;
- the validated fallback path for catalog misses, while that path remains supported.

Schemas should be derived from the same catalog and typed contracts used for validation so
the tool interface cannot drift from executable behavior.

### Finding 3: Native tool calling is useful, but not inherently safer or cheaper

Native function calling gives the orchestrator a standard agent/tool transcript and removes
some custom response conventions. It does not eliminate schemas, argument parsing, semantic
validation, provider incompatibilities, or token cost.

**Response:** Make native tool calling the only protocol accepted by the agentic path. Do not
emulate a tool call by asking for a JSON object in assistant content, do not parse prose or
code fences into tool calls, and do not fall back to `response_format` or prompt-described
JSON when native tool calling is unavailable.

Every native tool call must still be parsed, validated, authorized, and bounded by the
application before execution. A provider/model combination may run the agent only after its
native tool support, parallel-call behavior, argument encoding, tool-result replay, and error
behavior have been certified. An absent or malformed native tool call receives at most the
configured native-tool repair attempt; continued failure degrades to an existing deterministic
capability, clarification, or explicit error—not a JSON-emulated tool call.

Separate structured-output callers may coexist temporarily during migration, but they are
independent legacy workflows and are never a fallback transport for agent tools. The existing
structured planner remains available for legacy NLQ/MCP callers until those callers are
deliberately migrated.

### Finding 4: Numeric grounding is too rigid, but removing it would weaken trust

The current numeric string matcher rejects valid derived figures when their exact text is not
present in evidence. However, prompt instructions alone cannot prevent a model from inventing
financial figures.

**Response:** Replace string matching with governed numeric provenance:

- source facts are supplied to synthesis in a machine-readable fact set;
- common deltas, rates, shares, and comparisons are calculated deterministically;
- any model-requested calculation uses an approved calculator over cited operands;
- derived claims retain their operands, operation, unit, and source references;
- when validation finds an unsupported numeric claim, return a focused repair message to the
  LLM identifying that claim and instruct it to use only the supplied results and governed
  calculations;
- allow one synthesis repair attempt, then omit the unsupported claim or use the governed
  source summary if the repaired answer still fails validation.

Qualitative observations and recommendations may be generated, but they must be visibly
separate from verified facts and must not introduce unsupported numbers.

### Finding 5: Conversation quality needs semantic state as well as a transcript

Linear `user`, `assistant`, and `tool` messages are the right representation for an agentic
thread, but transcript replay alone does not guarantee that “Why?”, “those schemes,” or “the
leading agent” resolves to the intended chart, row, filter, or metric.

**Response:** Use a linear transcript together with compact structured session state. Persist
the last governed plan, visible filters, selected entities, result references, and offered
drill actions. The agent receives both the dialogue and these exact anchors. Deterministic
drill actions remain available because they are faster and more reliable than reconstructing
a prior query from prose.

Conversation storage consolidation remains a separate data migration. This project must not
delete behavior used by the legacy NLQ conversation path before that migration occurs.

### Finding 6: Compaction is already threshold-governed

The workbench schedules a post-turn check, but the summarization model is called only when
compaction is enabled and the transcript exceeds its configured token budget. Compaction is
disabled by default. Therefore there is no per-turn summarization problem to redesign.

**Response:** Preserve the current context-window-aware policy. Any threshold must be derived
from the active model’s context window and reserved headroom, never a fixed 60k–80k value.
The lightweight post-turn check may be skipped when compaction is disabled, but compaction is
otherwise outside the critical path of this migration.

### Finding 7: External-data protection must be stronger than a regex claim

The existing public-query boundary already blocks several categories of private data. More
complete detection is valuable, but a regex and customer-name blocklist cannot provide an
absolute guarantee: formatting, obfuscation, normalization, false positives, and stale entity
data all matter.

**Response:** Establish one mandatory outbound policy gateway for every live external tool.
It must enforce consent, role and deployment policy, normalize and inspect all arguments,
redact or reject private data, apply request bounds, and produce an auditable decision before
network execution. Existing authority ranking, citation normalization, and treatment of web
content as untrusted evidence must be preserved.

A rejected call may receive one bounded repair opportunity. The external request remains
blocked until the repaired arguments independently pass the gateway. Repeated failure ends in
a clear refusal. The full agent handling private context must run locally; only explicitly
public, sanitized inputs may cross an external model or connector boundary.

### Finding 8: Proven deterministic paths currently outperform model-dependent paths

The existing benchmark shows that governed fast paths usually answer in one to three seconds,
while questions that miss those paths frequently reach the timeout boundary. It also shows
poor multi-turn completion and cases where syntactically valid answers have the wrong metric,
filter, grouping, or shape.

**Response:** Do not replace all fast paths at once. Introduce the agent in shadow mode,
compare its proposed calls with current decisions, and promote it gradually. Optimize for
answer correctness and completed conversations—not for regex count or architectural novelty.


## 3. Target Architecture

```text
User question + linear history + governed session state
                         |
                         v
                  Local LLM agent
                         |
          +--------------+---------------+
          |              |               |
          v              v               v
  Governed internal   Reviewed local   Public external
       tools             sources           tools
          |              |               |
          |              |        Outbound policy gateway
          |              |               |
          +--------------+---------------+
                         |
                         v
          Typed results, facts, citations, lineage
                         |
                         v
          Governed calculation and provenance
                         |
                         v
              Bounded analytical synthesis
                         |
                         v
               Existing UI/SSE contracts
```

### Agent responsibilities

- Interpret the user’s language and conversational references.
- Select one or more capabilities from the authorized tool set.
- Supply structured arguments and repair validation errors within strict limits.
- Combine supported findings into a concise response.

### Application responsibilities

- Decide which tools are visible for the user, role, consent state, and deployment.
- Validate every tool call against catalog-derived typed contracts.
- Enforce read-only execution, PII masking, outbound privacy, and resource limits.
- Perform governed calculations and retain provenance.
- Build charts, tables, citations, limitations, and lineage.
- Preserve streaming, cancellation, persistence, telemetry, and deterministic degradation.


## 4. Governed Capability Model

The agent should see modular capabilities rather than one underspecified catch-all tool.
The conceptual capability set is:

1. **Query governed metrics** — full `QuerySpec` semantics and catalog-derived identifiers.
2. **Look up governed records** — complete selector, detail, and requested-field vocabulary.
3. **Run a reviewed analysis** — select and bind a catalog analysis preset.
4. **Create a governed worklist** — select and bind an authorized action-list preset.
5. **Build a role/persona briefing** — select a reviewed briefing definition.
6. **Search indexed knowledge** — macro, competitive, regulatory, concepts, and schema
   capabilities exposed according to role and consent.
7. **Search the live public web** — only through the outbound policy gateway.
8. **Clarify or refuse** — explicit non-execution outcomes when safe, complete arguments
   cannot be formed.

These may be represented as separate native tools or as a smaller number of discriminated,
typed tools. The deciding criteria are validation quality, provider reliability, token cost,
and evaluation results—not the smallest number of schema lines.

Parallel execution is allowed only for independent calls. Dependent calls remain ordered and
the overall turn has a shared time and retry budget.


## 5. Compatibility Commitments

The migration must preserve:

- audited metric definitions and sign-off status;
- parameterized, read-only SQL and existing validation;
- chart selection, driver decomposition, drill actions, exports, and lineage;
- role-based masking and source visibility;
- per-conversation external-source consent;
- source authority ranking, normalized citations, and untrusted-content boundaries;
- the complete SSE lifecycle, including conversation, progress, route, source cards, answer,
  refusal/error, and completion events;
- quick actions and their HTTP endpoints;
- legacy NLQ and MCP behavior until separately migrated;
- deterministic operation for saved queries and dashboards when the LLM is unavailable.

Renaming the quick-actions module is optional housekeeping. If performed, retain a compatibility
import during the migration so internal consumers do not break.


## 6. Migration Plan

### Phase 0: Establish the baseline

- Freeze a representative benchmark covering the existing 100-question corpus, multi-turn
  chains, exact record lookups, metric comparisons, analyses, worklists, and external queries.
- Record route accuracy, semantic-plan accuracy, answer-shape accuracy, useful-answer rate,
  timeout rate, P50/P95 latency, model calls, token usage, and privacy outcomes.
- Add adversarial cases for prompt injection, malformed tool calls, unauthorized tools, PII
  encodings, and repeated repair attempts.

### Phase 1: Introduce native tools without behavior removal

- Add provider-level native tool-call support and typed validation.
- Expose the existing governed capabilities through catalog-derived tool contracts.
- Reject assistant-content JSON as a tool call; there is no structured-output compatibility
  mode for the agentic path.
- Leave current structured-output NLQ/MCP callers operational as separate legacy paths, not as
  a fallback for native tools.
- Preserve deterministic paths during rollout.
- Prove tool support against every deployed provider/model combination.

Exit condition: tools execute the same governed contracts and return the same renderable
results as the existing paths.

### Phase 2: Shadow agent orchestration

- Run agent source/tool selection alongside the current router without executing the shadow
  decision.
- Compare selected sources, arguments, security decisions, expected result shape, latency,
  and token cost.
- Correct tool descriptions and contracts based on failures; do not add new phrase-matching
  rules to force the benchmark.

Exit condition: the shadow agent meets the agreed semantic and privacy thresholds over the
full benchmark and adversarial suite.

### Phase 3: Canary ambiguous requests

- Use the agent for ambiguous requests and complex multi-source questions.
- Keep exact deterministic fast paths. When the agent or provider fails, degrade to one of
  those paths, clarification, or an explicit error—never an emulated JSON tool call.
- Enable governed tool repair with strict per-turn call, retry, and time budgets.
- Validate answer shape before an answer is marked successful.

Exit condition: canary traffic improves useful-answer and multi-turn completion rates without
regressing P95 latency, privacy, or governed correctness.

### Phase 4: Governed synthesis and calculations

- Introduce the fact ledger and deterministic calculation/provenance layer.
- Allow richer analytical synthesis only after numeric-claim validation is active.
- Replace all-or-nothing numeric fallback with claim-level validation and limitations.

Exit condition: derived figures are reproducible from cited operands, unsupported-number
tests pass, and qualitative prose remains useful when a numeric claim is rejected.

### Phase 5: Retire proven-obsolete heuristics

- Measure which linguistic regexes are no longer reached or no longer improve outcomes.
- Remove them in small groups with focused regression coverage and an easy rollback.
- Retain semantic validators, authorization rules, privacy checks, exact identifier handling,
  and deterministic drill actions regardless of implementation style.
- Migrate legacy callers before removing shared planner schemas or conversation behavior.

Exit condition: each removal is neutral or positive against the baseline and can be rolled
back independently.


## 7. Release Gates

Production promotion requires all of the following:

- no regression in audited metric calculations or lineage;
- no regression in record-lookup fields, masking, or role enforcement;
- no unauthorized or unconsented tool execution;
- no private data reaching external connectors in the adversarial suite;
- materially better useful-answer and five-turn completion rates;
- answer-shape validation for rankings, comparisons, ratios, filters, and groupings;
- P95 latency and timeout rate at or better than the agreed baseline;
- bounded tool calls, repairs, output size, and total turn duration;
- full frontend rendering and SSE compatibility;
- native tool calls are never reconstructed from assistant-content JSON, prose, or code fences;
- provider failure degrades to a governed fast path, clarification, or explicit limitation.

The exact numeric thresholds should be recorded with the Phase 0 benchmark rather than
invented in advance. Privacy, authorization, audited calculation, and contract compatibility
are zero-regression gates.


## 8. Non-Goals

The following remain separate projects:

- replacing the governed semantic catalog with raw text-to-SQL;
- allowing the model to choose chart types or define financial formulas;
- database/conversation-store consolidation;
- cross-container model-server locking redesign;
- unrestricted autonomous web browsing;
- emulating native tool calls through structured-output JSON;
- removing every regex, including those used for security, normalization, parsing bounded
  formats, or exact deterministic recognition.


## 9. Expected Outcome

MoneyPal gains broader natural-language and multi-turn understanding without trading away the
properties that make financial answers trustworthy. The LLM becomes the flexible interpreter
and orchestrator; governed application code remains the authority for access, data, math,
privacy, provenance, and presentation.
