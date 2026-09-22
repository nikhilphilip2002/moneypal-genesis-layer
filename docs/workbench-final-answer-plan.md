# Workbench Final Answer Simplification Plan

## Final design

The model submits exactly:

```json
{
  "insights": "In August 2026, sanctioned loans were distributed by gender...",
  "query_id": 1,
  "view": "donut"
}
```

Rules:

- One final answer selects exactly one query.
- `query_id` is the current turn's simple counter: `1`, `2`, `3`.
- Turn UUIDs remain backend-only.
- `view` selects the visualization type.
- The backend infers chart fields from the stored query result.
- Excluded queries are calculated internally.
- The model never supplies `x`, `y`, visualization IDs, exclusions, or schema versions.

## Execution flow

```text
User question
    ↓
Model runs database query
    ↓
Backend stores it as current-turn query 1
    ↓
Model calls submit_final_answer
    {
      insights,
      query_id: 1,
      view: "donut"
    }
    ↓
Backend resolves query 1
    ↓
Backend infers chart fields from columns and rows
    ↓
Backend creates and displays one visualization
```

## Query ID handling

The model sees:

```text
query_id: 1
```

Internally, the backend can continue storing a globally unique identity such as:

```text
ae96c532b0c8:q1
```

The mapping is internal:

```text
(current turn, 1) → ae96c532b0c8:q1
```

The prefixed ID must not appear in model-visible query results or tool arguments.

Retries of the same logical query keep the same integer query ID and increment only an internal attempt counter.

## Visualization inference

The backend uses column types and result rows already returned by the query.

### Table

```json
{"query_id": 1, "view": "table"}
```

Uses every returned column.

### KPI

Requirements:

- One result row.
- At least one numeric value.

The numeric value becomes the KPI.

### Donut

Requirements:

- One categorical column.
- One numeric column.

Example:

```text
gender       → category
loan_count   → value
```

### Bar

- First categorical or date column → horizontal category.
- Numeric columns → values.

### Line or area

- Date/time column → horizontal axis.
- Numeric columns → values.

### Grouped or stacked chart

- First categorical/date column → horizontal axis.
- Second categorical column → series.
- Numeric column → value.

### Scatter

- First numeric column → horizontal value.
- Second numeric column → vertical value.

### Heatmap

- First two categorical columns → axes.
- Numeric column → value.

If the result shape is ambiguous or incompatible with the requested view, the backend returns a clear validation error. It must not silently choose potentially incorrect columns. The database-query prompt should encourage queries to return a visualization-friendly shape.

## Non-query answers

The new final tool is only for query-backed answers.

- Query-backed answer → `submit_final_answer`.
- Conceptual answer requiring no query → ordinary text response.
- Clarification or refusal → `finish_without_data`.

## Model-facing tool schema

```python
async def submit_final_answer(
    insights: str,
    query_id: int,
    view: VisualizationType,
) -> ...
```

Suggested visualization types:

```text
table
kpi
donut
bar
grouped_bar
line
area
stacked_area
scatter
heatmap
```

Validation:

- `insights` may be empty when the selected view is self-explanatory.
- `query_id` must be at least `1`.
- The selected query must belong to the current turn.
- The selected query must have completed successfully.
- The selected query must contain rows.
- The result shape must support the requested `view`.

## Backend-generated metadata

The backend derives and persists:

- Internal composite query ID.
- Visualization ID, if still required internally.
- Excluded queries.
- Query attempts.
- Chart axes and measures.
- Aggregation configuration.
- Schema version.
- Lineage and provenance.

None of these are model responsibilities.

## API and frontend result

The public answer can also be simplified:

```json
{
  "insights": "In August 2026...",
  "query_id": 1,
  "view": "donut",
  "card": {
    "columns": [],
    "rows": []
  }
}
```

The frontend renders the provided card directly. It does not need `active_query_ids`, `visual_query_ids`, or `excluded_queries` to decide what to show.

## TODO

### Contract

- [ ] Replace `FinalSynthesis` fields with `insights`, `query_id`, and `view`.
- [ ] Remove model-facing `schema_version`.
- [ ] Remove `active_query_ids`.
- [ ] Remove `visual_query_ids`.
- [ ] Remove `excluded_queries`.
- [ ] Restrict `query_id` to a positive integer.
- [ ] Restrict `view` to supported visualization types.

### Query identity

- [ ] Expose integer query counters in model observations.
- [ ] Keep turn-prefixed identifiers internal.
- [ ] Add current-turn integer-to-internal-ID resolution.
- [ ] Reject query IDs from another turn.
- [ ] Preserve retry attempts under the same logical query number.

### Visualization

- [ ] Remove `visualize_query_result` from model-visible tools.
- [ ] Create visualization automatically during final submission.
- [ ] Infer chart fields from stored columns and rows.
- [ ] Implement shape validation for every supported view.
- [ ] Return clear errors for incompatible result shapes.
- [ ] Attach the generated card to the final answer.

### Attribution

- [ ] Mark the selected query as active internally.
- [ ] Derive exclusions from unselected executed queries.
- [ ] Preserve lineage and audit metadata internally.
- [ ] Remove exclusion bookkeeping from the model prompt.

### Prompt

- [ ] Document the three-field final-answer contract.
- [ ] Tell the model that query IDs are current-turn integers.
- [ ] Require one final consolidated query.
- [ ] Tell the model to shape query output for the intended view.
- [ ] Remove instructions about visualization IDs and exclusions.

### Frontend

- [ ] Render the single card attached to the final answer.
- [ ] Stop selecting cards through `visual_query_ids`.
- [ ] Remove excluded-query UI unless it remains useful for diagnostics.
- [ ] Keep internal execution details in the trace/debug interface only.

### Focused tests

- [ ] The three-field contract accepts empty `insights`.
- [ ] A valid integer selects the current-turn query and produces one view.
- [ ] An unknown, failed, or empty query is rejected.
- [ ] Internal turn UUIDs never appear in model-visible query references.
- [ ] Ambiguous or incompatible result shapes are rejected.
- [ ] Conceptual answers still work without a query.
