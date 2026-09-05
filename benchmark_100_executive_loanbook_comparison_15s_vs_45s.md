# GICC Executive Loan-Book Benchmark — 15s vs 45s SLA

## Headline

Raising the per-question SLA from 15 to 45 seconds increased the API-level answer rate
from **24% to 30%**, but increased wall-clock time from **19m 37.57s to 53m 19.41s**.
Only three questions were genuinely recovered by waiting beyond 15 seconds; three other
questions changed from timeout to a sub-two-second answer, indicating run-to-run
route/service variability rather than an SLA benefit.

| Metric | 15-second SLA | 45-second SLA | Change |
|---|---:|---:|---:|
| Answered/partial | 24 | 30 | +6 |
| Fully answered | 23 | 29 | +6 |
| Partial | 1 | 1 | 0 |
| Refused/no match | 3 | 3 | 0 |
| Timed out | 73 | 67 | -6 |
| Complete five-turn chains | 0 | 0 | 0 |
| Wall-clock time | 1,177.57s | 3,199.41s | +2,021.84s |
| Mean latency | 11.78s | 31.99s | +20.21s |
| Median latency | 15.55s | 45.41s | +29.86s |
| P95 latency | 15.77s | 45.70s | +29.93s |

## Answers genuinely recovered by the longer SLA

| Question | Latency | Assessment |
|---|---:|---|
| Q094 — Which branch has the highest average ticket size? | 26.70s | Answered: Head Office — Credit Division, ₹3.98 L. |
| Q095 — Which branches have declining monthly disbursements? | 39.81s | Partially useful: returned branch/month trend data, but the summary described aggregate growth rather than clearly listing declining branches. |
| Q097 — Now rank them by total disbursed amount. | 38.51s | Answered: Vanitha led the returned agents at ₹12.38 Cr. |

There were no successful responses between 15.00 and 26.69 seconds.

## Fast outcomes that varied between runs

These questions timed out in the 15-second run but answered almost immediately in the
45-second rerun. They were not rescued by waiting longer:

| Question | 45s-run latency | Result |
|---|---:|---|
| Q056 — What is the average sanctioned ticket size? | 1.15s | ₹3.98 L. |
| Q081 — Which ten schemes have the highest sanctioned loan count? | 0.82s | MSME Loans led at 1,588. |
| Q086 — How many borrowers are female and how many are male? | 1.29s | Returned a three-gender breakdown; M led at 3,142. |

## Effective usefulness

The Workbench API's `answered` status is not a correctness judgment. Applying the same
strict relevance review used for the 15-second run gives approximately **17 useful or
partially useful responses out of 100** for the 45-second run, compared with approximately
11 at 15 seconds. Several unchanged API-labelled answers still returned the wrong metric,
lost the requested grouping/filter, or supplied only a definition.

## Executive decision

A 45-second SLA is not a good primary remedy:

- It adds **33m 41.84s** to this sequential 100-question workload.
- It recovers only three genuinely slow answers.
- Sixty-seven questions still exceed 45 seconds.
- No five-turn executive conversation completes successfully.
- Median latency moves to the timeout boundary, at 45.41 seconds.

Keep the user-facing SLA closer to 15 seconds and fix the stalled planning/fallback paths.
Where a query legitimately needs longer analysis, return progress and execute it as an
explicit asynchronous analysis instead of holding the chat turn open without a result.

## Files

- 15s full report: `benchmark_100_executive_loanbook_chains.md`
- 15s raw JSON: `benchmark_100_executive_loanbook_chains.json`
- 45s full report: `benchmark_100_executive_loanbook_chains_45s.md`
- 45s raw JSON: `benchmark_100_executive_loanbook_chains_45s.json`
- Reusable runner: `scripts/run_100_executive_loanbook_chains.py`

