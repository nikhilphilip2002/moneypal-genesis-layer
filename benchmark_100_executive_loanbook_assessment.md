# GICC Executive Loan-Book Benchmark — Assessment

## Executive verdict

The live Workbench completed the full 100-question, 20-conversation benchmark in
**1,177.57 seconds (19m 37.57s)** under a **15-second per-question SLA** with one
conversation running at a time.

| Outcome | Questions | Rate |
|---|---:|---:|
| API returned answered/partial | 24 | 24% |
| Strictly useful after relevance review | 11 | 11% |
| Refused/no matching record | 3 | 3% |
| Timed out | 73 | 73% |
| Complete five-turn conversations | 0 / 20 | 0% |

The 24% API answer rate is an upper bound, not a correctness score. Manual review found
10 clearly responsive answers and one partially useful response. Thirteen responses were
marked answered by the API but did not answer the question asked.

## Performance

| Metric | Result |
|---|---:|
| Mean latency, all questions | 11.78s |
| Median latency, all questions | 15.55s |
| P90 | 15.70s |
| P95 | 15.77s |
| Maximum | 16.25s |
| Mean latency, answered/partial | 1.47s |
| Median latency, answered/partial | 1.18s |
| Mean latency, timed out | 15.60s |

The system is bimodal: governed fast paths usually answer in one to three seconds, while
questions that miss those paths generally run until the client SLA expires.

## Results by executive role

| Role | Questions | API answered/partial | Errors | Mean latency |
|---|---:|---:|---:|---:|
| CEO | 35 | 10 | 25 | 11.42s |
| CFO | 35 | 6 | 29 | 13.26s |
| CGO | 30 | 8 | 19 | 10.45s |

## Conversation-depth result

| Turn depth | API answered/partial | Errors |
|---:|---:|---:|
| 1 | 10 / 20 | 9 |
| 2 | 3 / 20 | 16 |
| 3 | 3 / 20 | 16 |
| 4 | 3 / 20 | 17 |
| 5 | 5 / 20 | 15 |

No five-turn chain completed successfully. Contextual phrases such as “break that down,”
“now show it,” “for those schemes,” and “for the leading agent” are therefore the largest
product-level reliability gap.

## What worked

The strongest path was deterministic governed retrieval. Examples include:

- FY27 disbursement: **₹137.16 Cr** (Q006).
- Distinct sanctioned borrowers: **5,719** (Q011).
- Current NPA ratio: **0.02%** (Q021, definition pending sign-off).
- Scheme principal outstanding ranking led by MSME Loans at **₹59.81 Cr** (Q031).
- Share capital: **₹85.50 L** (Q066, definition pending sign-off).
- Agent customer ranking led by Vanitha with **338 borrowers** (Q071).
- Vanitha customer retrieval returned **338 customers** (Q072).
- The chained refinement “Add scheme name and tenure” returned **338 linked loan rows**
  with the requested fields in 2.66 seconds (Q073).

Nineteen of the 24 API-level answered/partial responses used the deterministic router.

## Material correctness failures

Several responses were syntactically successful but semantically wrong:

- Q015 asked for the top ten agents by customers and returned a scalar borrower count of 0.
- Q016 asked for whole-book principal outstanding and silently filtered to Standard assets.
- Q032 asked for disbursement by previously listed schemes and returned whole-book principal outstanding.
- Q036 asked to compare sanctioned and disbursed amounts and returned only sanctioned amount.
- Q043 asked for collection efficiency by scheme and returned amount collected by scheme.
- Q050 asked for the weighted average interest rate and returned only its definition.
- Q068 asked for outstanding relative to share capital and returned share capital only.
- Q080 asked for Ujire-branch outstanding and returned whole-book outstanding.
- Q082 asked for scheme-level sanctioned amounts and returned a whole-book scalar.
- Q084 asked for the schemes' average ticket size and returned only its definition.
- Q096 asked for an agent ranking and returned a scalar loan count of 0.
- Q100 asked for the leading agent's customers and returned whole-book principal outstanding.

These should be treated as failed answers even though the API labelled them answered.

## Refusals and timeouts

- All 73 errors were `Request timed out after 15s`.
- Ujire customer retrieval and its next two refinements were refused as having no matching
  customer or loan records (Q076–Q078).
- The recently pushed named-branch lookup must be deployed and then checked against the
  actual branch name/code in `gold.semantic_branch` before retesting this chain.

## Recommended priorities

1. Cancel server-side work when the SSE client disconnects or its deadline expires; timed-out
   work appears capable of occupying the local model/MCP path after the client has left.
2. Add deterministic structural follow-up handling for pronouns and references such as
   “that,” “it,” “those schemes,” “that branch,” and “the leading agent.”
3. Validate answer shape against question shape before marking a turn answered: rankings
   require grouped rows, comparisons require both metrics, and ratios require a numeric result.
4. Prevent the concepts source from satisfying a request for the bank's numeric value with
   only a metric definition.
5. Add regression chains for agent, branch, scheme, gender, collections, and CFO ratio questions.

## Evidence

- Full per-question results, answers and SQL: `benchmark_100_executive_loanbook_chains.md`
- Machine-readable raw results: `benchmark_100_executive_loanbook_chains.json`
- Reusable runner and 100-question corpus: `scripts/run_100_executive_loanbook_chains.py`

