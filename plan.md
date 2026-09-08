# LLM-Controlled Workbench Agent Plan

Updated: 2026-09-08

## 0. Current implementation status

This plan is actively being implemented on branch `fix/regex-removal`. The worktree is not
yet ready for a final commit or production deployment.

Completed in the current worktree:

- provider-native flat tools remain the only agent tool-call protocol; assistant-content JSON
  is not accepted as a tool call;
- the bounded agent can execute multiple tools, feed every result back to the local LLM, and
  let the LLM either call another tool or write the final answer;
- failed executions and invalid continuation arguments are returned as tool results and may be
  repaired by the LLM within the shared round/tool/time limits;
- complete native tool payloads, rows, errors, evidence, facts, and SQL lineage are persisted;
- native transcript replay now reads the ordered event stream and fails explicitly when the
  exact transcript cannot fit the context window;
- named record lookups such as `customers under vanitha` enter the native agent path instead
  of being diverted through mandatory legacy preflight;
- `inspect_loan_catalog` is available as a concrete read-only native tool and returns relevant
  governed metrics, dimensions, tables, columns, joins, vocabulary, and limitations;
- the native agent no longer uses the month/period regex argument canonicalizer and the
  generated-query tool disables legacy phrase-specific SQL shortcuts;
- nested text-to-SQL requests, assistant responses, candidate SQL, validation failures,
  validated SQL, model, and provider are attached to the parent tool result lineage;
- SQL validation rejects unqualified columns that are absent from the selected tables or
  ambiguous across joined tables;
- the native-agent corpus contains 120 prompts over every governed Gold view, including
  month-, scheme-, branch-, and product-wise interest collection variants.

Still in progress:

- persist and replay route-stage LLM responses and every remaining legacy/preflight LLM event
  through the same ordered history representation;
- complete the migration away from the compatibility `agent_exchanges` field after stored
  version-5 conversations no longer require it;
- run the complete test suite after the latest catalog-tool and nested-trace changes;
- execute the same 120-case live evaluation against Ling and Qwen, record model IDs and
  failures, and optimize only general prompts/catalog metadata—not question-specific regex;
- deploy and repeat the two production regressions after tests and evaluation pass.

## 1. Intended architecture

The local LLM is the agent and remains in control of the conversation. The application gives
the LLM a bounded set of tools for authorized resources. The LLM decides:

- what the user means;
- which tool to call;
- which governed metrics, dimensions, filters, tables, and fields to request;
- how a follow-up relates to previous calls and results;
- whether a tool result answers the question;
- whether to correct a failed or incomplete call;
- when to provide the final answer or refuse.

The application does not take over semantic planning. It must not rewrite the user's intent,
silently add dimensions, merge follow-ups through hard-coded rules, select business metrics,
or manufacture tool calls for the model.

Application code is responsible only for:

- exposing authorized tools and relevant catalog information;
- enforcing authentication, authorization, privacy, and read-only access;
- validating tool arguments and SQL safety;
- executing accepted calls;
- returning exact results and errors to the LLM;
- preserving and replaying complete conversation history;
- enforcing bounded rounds, time, rows, and context limits.

## 2. Clarification: native tool arguments versus structured-output JSON

Provider-native function calling necessarily represents tool arguments as a JSON object. For
example, the model may natively call:

```text
query_metrics(metrics=[interest_collected], dimensions=[scheme], period=all_time)
```

That is an actual provider-native tool call, not a structured-output workaround.

The prohibited design is asking the model to print JSON in assistant content and then parsing
that text as though it were a tool call. This project must never do that. It also must not use
a six-branch `oneOf` mega-schema. Each resource tool keeps one concrete, flat, portable schema.

Internal persistence may store messages and events in database JSON columns, but storage
encoding does not control the agent and is not an LLM structured-output protocol.

## 3. Provider-native agent loop

Every turn follows a genuine model-controlled loop:

1. Send the system prompt, complete available conversation history, authorized native tools,
   and only relevant governed catalog context to the LLM.
2. Require a provider-native tool call when data or an external resource is needed.
3. Validate the selected tool and arguments at the security boundary.
4. Execute the tool if valid; otherwise return a structured tool error to the LLM.
5. Inject the complete tool result or error into the same LLM conversation.
6. Let the LLM decide whether to call another tool, repair its previous call, clarify, refuse,
   or answer.
7. Continue until the model finishes or a configured round/tool/time limit is reached.

The current execution path stops too early after some calls and performs application-side
canonicalization. Replace that with the iterative loop above. A result such as one all-time
interest total for a `schemewise` request must be shown to the LLM; the LLM must recognize that
its call omitted `scheme` and issue the corrected native call.

## 4. Tools available to the LLM

Keep concrete resource tools rather than a polymorphic mega-tool:

- `query_metrics`: governed metrics, dimensions, filters, periods, ordering, and comparison.
- `lookup_records`: borrower/account/entity lookup.
- `run_validated_query`: governed row/detail requests that reviewed metrics cannot express.
- `run_analysis`: reviewed multi-chart analyses.
- `create_worklist`: reviewed operational worklists.
- `generate_briefing`: governed management briefings.
- `search_curated_knowledge`: internal concepts, schema, regulatory, and macro resources.
- `search_public_web`: authorized public information only.
- `finish_without_data`: clarification, refusal, or explanation without executing data tools.

The implemented read-only catalog inspection tool lets the model request exact metadata when
the retrieved prompt surface is insufficient:

```text
inspect_loan_catalog(topic, tables=[])
```

It returns relevant governed metrics, dimensions, columns, tables, joins, vocabulary, and
coverage limitations. The LLM decides whether to call it. The response is then included in
history like every other tool result.

Tool availability is determined only by user permissions and resource policy. Retrieval may
narrow enum values and catalog entries shown inside a tool schema, but it must not secretly
choose the user's business intent or modify the tool call after generation.

## 5. Complete LLM and tool history

Everything produced during a conversation must be durably stored and replayed to the LLM in
the original order:

1. Every user message.
2. Every LLM assistant message and native tool call.
3. Every tool's complete result or error.
4. Nested LLM-generated plans and SQL used inside `run_validated_query`.
5. Generated SQL, validated SQL, bound parameters, lineage, and execution results.
6. Repair calls and repair results.
7. Final assistant answers.

This requirement applies equally to native calls, mandatory lookup/preflight, legacy paths,
catalog inspection, and nested text-to-SQL. There must not be separate history formats where
one path retains tool calls and another retains only a rendered chart.

Remove silent replay truncation such as retaining only 20 rows or omitting SQL and arguments.
Durable history always retains the complete exchange. When the required transcript cannot fit
the configured model context and compaction is disabled, report an explicit context-capacity
error rather than silently changing history. Any future compaction must be explicit and must
not alter the durable event record.

This complete replay is what allows the LLM—not application-side follow-up rules—to understand:

```text
customers under vanitha
include tenure and sanctioned amount with the above details
```

The model must see the exact previous lookup call, its filter, selected fields, SQL/lineage,
and result before generating the next native call.

## 6. Fixing grouping while keeping the LLM in control

The production question:

```text
interest collected schemewise
```

must lead the LLM to call `query_metrics` with `interest_collected` and `scheme`. The fix is:

- add genuine vocabulary such as `scheme wise`, `schemewise`, and `by scheme` to the governed
  scheme dimension;
- ensure the retrieved catalog context clearly labels matching dimensions as user-requested
  grouping candidates;
- strengthen the system/tool prompt: every explicitly requested breakdown must appear in the
  native call's dimensions;
- return the executed metric specification and result shape to the LLM;
- allow the LLM another tool round to correct an omitted dimension.

Do not fix this by a `_SCHEME_RE`, a special-case argument mutation, or application code that
adds `scheme` after the LLM call. Remove the existing month-specific behavioral correction once
the general model-controlled loop passes month, branch, product, and scheme tests.

## 7. Follow-up behavior while keeping the LLM in control

Do not build an application-side intent merger that decides what `include` or `above details`
means. Replay the complete preceding messages, calls, and results. The prompt instructs the LLM
to preserve prior constraints unless the user changes them and to emit a complete replacement
tool call for the new request.

For the Vanitha example, the LLM should generate a complete native call that retains the agent
constraint and customer/loan identity fields, then adds tenure and `sanction_amount`.

The application validates that call but does not invent it. If required information is missing,
the LLM may call `inspect_loan_catalog` or clarify with the user.

## 8. SQL safety is validation, not agent control

The LLM may select `run_validated_query` and generate a governed detail intent. The downstream
generator is still constrained by the selected Gold tables and allowed catalog columns.

Use SQL AST validation—not behavioral regex—to reject:

- nonexistent or wrong-table columns;
- unauthorized schemas or tables;
- undeclared joins;
- writes and unsafe functions;
- unbounded queries;
- invalid grouping or aggregation.

For `gold.semantic_loan_account`, `sanction_amount` is valid and
`disbursement_amount` is not. Return an exact tool error to the LLM when validation fails. The
LLM then decides whether to inspect the catalog, regenerate the call, or explain the failure.

Never convert an invalid assistant text response into executable JSON or SQL.

## 9. Evaluation without behavioral regex

Evaluation observes what the LLM actually does; it does not repair the answer or use regex to
declare success.

For each isolated question, assert:

- native tool name;
- exact metrics and dimensions;
- filters and entity values;
- tables and requested fields;
- period, ordering, and limit;
- validation outcome;
- parsed SQL AST and governed identifiers;
- executed result columns and grouping shape;
- final answer consistency with the tool result.

For each multi-turn conversation, assert that the model received the exact previous user,
assistant, tool-call, and tool-result sequence. Then assert that the LLM's next native call
retains or changes the correct constraints based on the user's words.

Required regression conversations include:

- interest collected scheme-wise, branch-wise, product-wise, and month-wise;
- customer lookup followed by additional fields;
- changing and removing filters;
- changing periods while preserving other constraints;
- showing underlying accounts after an aggregate;
- misspellings such as `santioned`;
- mandatory lookup/preflight followed by a native call;
- invalid generated SQL followed by an LLM-directed correction.

Use parser/AST inspection and exact structured tool-call assertions. Do not use query-specific
regexes as an oracle. Run the identical corpus against Ling and Qwen and record the actual model
ID, prompt/catalog versions, calls, results, latency, and failure category.

## 10. Implementation order

1. Add failing production regression tests before implementation.
2. Implement one lossless history/event stream across native, legacy, preflight, and nested
   text-to-SQL calls.
3. Make the LLM transcript replay every prior message, tool call, and complete tool result.
4. Convert execution into a bounded iterative LLM → tool → result → LLM loop.
5. Finish integrating the catalog inspection tool and governed vocabulary/context into live
   Ling and Qwen evaluations.
6. Keep application-side semantic argument mutation removed and verify equivalent behavior
   through the agent loop.
7. Strengthen table/column SQL AST validation and return failures as tool errors to the LLM.
8. Expand isolated and multi-turn evaluation without regex-based scoring.
9. Run all tests and the full Ling evaluation.
10. Serve Qwen and run the identical evaluation.
11. Commit, push, rebuild the shared backend image, and repeat production conversations.

## 11. Completion criteria

The work is complete when:

- the LLM controls tool selection, arguments, corrections, and final answers;
- application code only exposes resources, enforces policy, validates, and executes;
- no assistant-content JSON fallback or `oneOf` mega-tool exists;
- every LLM message, native call, tool result, generated SQL artifact, and answer is replayable;
- groupings requested by the user are present because the LLM generated them;
- follow-ups work from complete history without application-side intent rewriting;
- invalid identifiers never reach PostgreSQL;
- structural, execution, and multi-turn evaluations pass on Ling and Qwen;
- the two observed production conversations return correct results after deployment.

## 12. Security boundaries

LLM control does not mean permission control. The model cannot grant itself tools, bypass role
policy, expose PII to public search, write to PostgreSQL, invent joins, or execute rejected SQL.
Those deterministic restrictions remain outside the model.

`.env` and `.env.prod` remain ignored and must never be committed.
