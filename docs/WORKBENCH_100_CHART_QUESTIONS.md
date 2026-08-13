# Workbench: 100 Chart-Output Questions

Paste these questions into the Workbench one at a time. They are written against the
current governed loan-book catalog. The **Expected chart** column names the chart selected
by `backend/app/services/nlq/charts.py` when the planner produces the intended QuerySpec
and the query returns data.

## How result shape maps to charts

| Result structure | Simplified expectation | Actual selector behavior |
|---|---|---|
| One metric, no dimension | KPI | KPI |
| Category + metric | Bar chart | Bar up to 12 rows; ranking above 12 |
| Time + metric | Line chart | Area for flows; line for ratios and stocks |
| Composition/share | Donut or part-to-whole | Donut, stacked area, or stacked bar |
| Current versus previous | Variance/dumbbell | Variance without category; dumbbell with one category up to 20 rows |
| Many categories | Ranking/table | Ranking for one category; table for complex shapes |
| Mixed units or complex rows | Table | Table, except two metrics across one category use scatter |
| Two categorical dimensions | — | Heatmap |
| Two same-unit metrics + category | — | Grouped bar |
| Time + more than six category series | — | Small multiples |

Chart selection is deterministic. The LLM plans metrics, dimensions, filters and periods;
it does not choose the chart directly.

## A. KPI — one metric, no dimension (15)

| ID | Question | Expected chart |
|---:|---|---|
| 001 | What was our total disbursement last quarter? | KPI |
| 002 | How many disbursement events occurred last month? | KPI |
| 003 | What is the total sanctioned amount this financial year to date? | KPI |
| 004 | How many loans have we sanctioned in total? | KPI |
| 005 | How many borrowers are in the complete loan book? | KPI |
| 006 | What is our average ticket size across the complete loan book? | KPI |
| 007 | What is the average interest rate across all loans? | KPI |
| 008 | What is the classified principal outstanding today? | KPI |
| 009 | What is the current principal outstanding across the whole loan book? | KPI |
| 010 | How much principal is overdue today? | KPI |
| 011 | How many accounts are delinquent today? | KPI |
| 012 | What is our PAR 30 today? | KPI |
| 013 | What is our current NPA ratio? | KPI |
| 014 | What is collection efficiency this financial year to date? | KPI |
| 015 | How much did we collect last month? | KPI |

## B. Bar — one metric across a small category set (15)

| ID | Question | Expected chart |
|---:|---|---|
| 016 | Show loan count by product. | Bar |
| 017 | Show disbursement by product last quarter. | Bar |
| 018 | Show sanctioned amount by product this financial year. | Bar |
| 019 | How many borrowers are there by product? | Bar |
| 020 | Show average ticket size by product. | Bar |
| 021 | Show average interest rate by product. | Bar |
| 022 | Show principal outstanding by asset classification today. | Bar |
| 023 | Show overdue principal by asset classification today. | Bar |
| 024 | Show delinquent account count by asset classification today. | Bar |
| 025 | Break down principal outstanding by DPD bucket today. | Bar |
| 026 | Show loan count by loan type. | Bar |
| 027 | Show sanctioned amount by loan type. | Bar |
| 028 | Show loan count by open or closed account status. | Bar |
| 029 | Show GL balance by GL branch for FY26. | Bar |
| 030 | Show collection efficiency by product this financial year. | Bar |

## C. Time trends — area for flows, line for ratios/stocks (15)

| ID | Question | Expected chart |
|---:|---|---|
| 031 | Show monthly disbursement during FY26. | Area |
| 032 | Show the number of disbursement events by month during FY26. | Area |
| 033 | Show sanctioned amount by month during FY26. | Area |
| 034 | Show loans sanctioned by month during FY26. | Area |
| 035 | Show borrower count by month during FY26. | Area |
| 036 | Show amount collected month by month over the last 12 months. | Area |
| 037 | Show principal collected month by month over the last 12 months. | Area |
| 038 | Show interest collected month by month over the last 12 months. | Area |
| 039 | Show amount due month by month over the last 12 months. | Area |
| 040 | Show collection shortfall month by month over the last 12 months. | Area |
| 041 | Show scheduled instalment amount by month during FY26. | Area |
| 042 | Show average ticket size by month during FY26. | Line |
| 043 | Show average interest rate by month during FY26. | Line |
| 044 | Show collection efficiency month by month over the last 12 months. | Line |
| 045 | Show PAR 30 by month over the last 90 days. | Line |

## D. Composition and part-to-whole (10)

Use explicit words such as **share**, **mix**, **composition**, or **split** so the planner
sets `as_share=true`.

| ID | Question | Expected chart |
|---:|---|---|
| 046 | What is our product mix by principal outstanding today? | Donut |
| 047 | What share of all loans belongs to each product? | Donut |
| 048 | Show last quarter's disbursement share by product. | Donut |
| 049 | Show the sanctioned amount composition by product this financial year. | Donut |
| 050 | Show principal outstanding composition by asset classification today. | Donut |
| 051 | Show the overdue-principal share by asset classification today. | Donut |
| 052 | What is the loan-count split between EMI and bullet loans? | Donut |
| 053 | Show sanctioned amount mix by loan type. | Donut |
| 054 | Show the loan-count split between open and closed accounts. | Donut |
| 055 | Show principal-outstanding composition by DPD bucket today. | Donut |

## E. Period comparison — variance and dumbbell (12)

| ID | Question | Expected chart |
|---:|---|---|
| 056 | Compare total disbursement this quarter with last quarter. | Variance |
| 057 | Compare amount collected this month with last month. | Variance |
| 058 | Compare loans sanctioned this quarter with last quarter. | Variance |
| 059 | Compare borrower count this quarter with last quarter. | Variance |
| 060 | Compare collection efficiency this quarter with last quarter. | Variance |
| 061 | Compare sanctioned amount by product this quarter versus last quarter. | Dumbbell |
| 062 | Compare disbursement by product this quarter versus last quarter. | Dumbbell |
| 063 | Compare loan count by loan type this quarter versus last quarter. | Dumbbell |
| 064 | Compare amount collected by product this month versus last month. | Dumbbell |
| 065 | Compare collection efficiency by product this quarter versus last quarter. | Dumbbell |
| 066 | Compare overdue principal by asset classification today versus last month. | Dumbbell |
| 067 | Compare principal outstanding by DPD bucket today versus last month. | Dumbbell |

## F. Ranking and table — many categories or complex output (12)

| ID | Question | Expected chart |
|---:|---|---|
| 068 | Rank every scheme by total sanctioned amount. | Ranking |
| 069 | Rank every scheme by loan count. | Ranking |
| 070 | Rank every scheme by average interest rate. | Ranking |
| 071 | Rank every scheme by average ticket size. | Ranking |
| 072 | Rank all branches by disbursement last quarter. | Ranking |
| 073 | Rank all branches by collection efficiency this financial year. | Ranking |
| 074 | Rank all branches by borrower count. | Ranking |
| 075 | Rank all branches by principal outstanding today. | Ranking |
| 076 | Rank all GL accounts by GL balance for FY26. | Ranking |
| 077 | Show total sanctioned amount, loan count, and average interest rate for the complete book. | Table |
| 078 | Show sanctioned amount, loan count, and average interest rate by product. | Table |
| 079 | Show sanctioned amount by branch, product, and scheme. | Table |

## G. Heatmap — one metric across two categorical dimensions (5)

| ID | Question | Expected chart |
|---:|---|---|
| 080 | Show disbursement by branch and product last quarter. | Heatmap |
| 081 | Show loan count by branch and product. | Heatmap |
| 082 | Show collection efficiency by branch and product this financial year. | Heatmap |
| 083 | Show principal outstanding by asset classification and product today. | Heatmap |
| 084 | Show sanctioned amount by loan type and product. | Heatmap |

## H. Scatter — two metrics across one category (5)

| ID | Question | Expected chart |
|---:|---|---|
| 085 | Compare sanctioned amount and loan count across products. | Scatter |
| 086 | Compare average ticket size and average interest rate across products. | Scatter |
| 087 | Compare amount collected and collection shortfall across products this financial year. | Scatter |
| 088 | Compare principal outstanding and overdue principal across asset classifications today. | Scatter |
| 089 | Compare loan count and borrower count across products. | Scatter |

## I. Grouped bar — multiple same-unit metrics across one category (4)

| ID | Question | Expected chart |
|---:|---|---|
| 090 | Show principal collected and interest collected by product this financial year. | Grouped bar |
| 091 | Show amount due and amount collected by product this financial year. | Grouped bar |
| 092 | Show overdue principal and total overdue by asset classification today. | Grouped bar |
| 093 | Show principal outstanding and overdue principal by asset classification today. | Grouped bar |

## J. Small multiples — time plus more than six category series (3)

| ID | Question | Expected chart |
|---:|---|---|
| 094 | Show monthly disbursement by branch during FY26. | Small multiples |
| 095 | Show monthly loan count by branch during FY26. | Small multiples |
| 096 | Show monthly amount collected by branch over the last 12 months. | Small multiples |

## K. Stacked composition over time and multi-series line (4)

| ID | Question | Expected chart |
|---:|---|---|
| 097 | Show monthly disbursement mix by product during FY26. | Stacked area |
| 098 | Show monthly collection share by product over the last 12 months. | Stacked area |
| 099 | Show monthly principal-outstanding composition by asset classification over the last 90 days. | Stacked bar |
| 100 | Show monthly collection efficiency by product over the last 12 months. | Line |

## Interpreting deviations

If a question does not produce the expected chart, inspect the response lineage and plan:

1. **Different metric/dimension plan:** the planner interpreted the wording differently.
2. **Empty data:** an empty dimensional result renders as a table; an empty aggregate renders as a KPI.
3. **Row threshold:** bar becomes ranking above 12 rows; line becomes small multiples above six series.
4. **Unsupported combination:** the compiler should refuse rather than invent a join.
5. **Generated SQL path:** chart choice is inferred from returned columns, so it may be a KPI,
   bar/ranking, or table instead of the QuerySpec chart listed above.

For repeatable QA, record the returned `chart_type`, `lineage.path`, SQL, row count, warnings,
and planner route for every question.
