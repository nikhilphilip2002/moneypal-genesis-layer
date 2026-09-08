# LLM-Controlled Workbench TODO

Updated: 2026-09-08

## Implementation progress in the current worktree

- [x] Native tool replay now retains the complete card payload, rows, evidence, and SQL lineage.
- [x] New turns persist an ordered event stream for user messages, native LLM messages, tool
      calls, tool results, legacy cards, errors, and final answers.
- [x] Native record lookups no longer detour through mandatory legacy preflight.
- [x] Failed tools are returned to the LLM, which may select a different authorized tool.
- [x] Successful tool results return to an `auto` native-tool continuation round; the LLM may
      call additional resource tools or write the final answer.
- [x] A multi-tool test covers metric → knowledge → final LLM summary.
- [x] Scheme-wise vocabulary and catalog-context coverage were added without behavioral regex.
- [x] Live Ling probe selected `query_metrics`, `interest_collected`, and `scheme` for
      `interest collected schemewise` without application-side argument mutation.
- [x] SQL AST validation now rejects an unqualified column that exists only on a different Gold
      view and rejects ambiguous unqualified columns across joined views.
- [x] Current focused result: 159 tests passed; Ruff and `git diff --check` passed.

Items below remain the completion checklist. Checked progress above does not mean the unified
history migration, nested LLM event capture, or live Ling/Qwen evaluation is complete.

## 0. Regression tests first

- [ ] Add `interest collected schemewise` expecting the LLM's native `query_metrics` call to
      contain `metrics=[interest_collected]` and `dimensions=[scheme]`.
- [ ] Add month-wise, branch-wise, product-wise, and scheme-wise variants.
- [ ] Add the full Vanitha lookup and `include tenure and sanctioned amount` conversation.
- [ ] Assert the exact history delivered to the LLM contains the prior lookup call and result.
- [ ] Assert the LLM's follow-up call retains the agent filter and previous fields.
- [ ] Assert wrong-table `disbursement_amount` fails before PostgreSQL execution.

## 1. Lossless unified history

- [ ] Replace split legacy/native history with one ordered event stream.
- [ ] Persist every user and LLM message.
- [ ] Persist every native tool call with exact arguments.
- [ ] Persist every complete tool result and error.
- [ ] Persist nested LLM plans, generated/validated SQL, parameters, lineage, and results.
- [ ] Cover mandatory preflight and legacy lookup with the same event format.
- [ ] Replay the complete preceding exchange to the LLM.
- [ ] Remove silent 20-row/tool-payload clipping from required immediate history.
- [ ] Return an explicit context-capacity error if lossless history cannot fit.

## 2. Model-controlled agent loop

- [ ] Continue LLM execution after each tool result.
- [ ] Let the LLM choose another tool, repair, clarify, refuse, or finish.
- [ ] Keep hard limits on rounds, tool calls, time, rows, and permissions.
- [ ] Remove application-side intent merging and semantic argument rewriting.
- [ ] Remove the month-only mutation after general grouping tests pass.

## 3. Resource tools and catalog access

- [ ] Keep concrete flat provider-native tool schemas.
- [ ] Add `inspect_loan_catalog` as a read-only tool if prompt retrieval is insufficient.
- [ ] Return governed tables, columns, metrics, dimensions, joins, and vocabulary.
- [ ] Add genuine scheme-wise vocabulary to Gold YAML.
- [ ] Ensure tool results re-enter the same model conversation.
- [ ] Keep assistant-content JSON fallback prohibited.

## 4. Validated SQL boundary

- [ ] Restrict generated SQL to selected governed tables and catalog columns.
- [ ] Validate identifiers, joins, predicates, grouping, ordering, and limits through the AST.
- [ ] Return structured validation failures as tool results.
- [ ] Let the LLM decide how to correct a failed call.
- [ ] Never execute nonexistent, unauthorized, or wrong-table identifiers.

## 5. Evaluation without behavioral regex

- [ ] Assert exact LLM-native tool calls and arguments.
- [ ] Assert parsed SQL AST, bound parameters, and result shape.
- [ ] Assert the final answer agrees with the tool result.
- [ ] Run complete multi-turn transcripts and inspect what history the LLM received.
- [ ] Do not use question-specific regexes to score or repair answers.
- [ ] Expand the corpus with production failures and paraphrases.
- [ ] Run the full corpus against Ling.
- [ ] Serve Qwen and run the identical corpus.

## 6. Final verification and deployment

- [ ] Run Ruff and formatting checks.
- [ ] Run focused, catalog, SQL safety, database, and multi-turn tests.
- [ ] Review logs for complete LLM/tool replay and bounded model-driven repairs.
- [ ] Confirm `.env` and `.env.prod` remain ignored.
- [ ] Commit and push only task-owned files.
- [ ] Rebuild `backend` and `postgres-mcp`.
- [ ] Repeat the scheme-wise and Vanitha production conversations.
