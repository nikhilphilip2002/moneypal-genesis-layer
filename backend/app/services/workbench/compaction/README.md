# Workbench conversation compaction

The native agent checks context before every model request, including continuations
within a turn. `request.py` summarizes the oldest complete exchanges and sends the
checkpoint followed by the retained messages to the next request. The current question
and latest tool exchange remain verbatim; assistant tool calls stay with their results.
The cut point is selected by token size, so a few large exchanges can trigger compaction.

## Token accounting

- `GET /v1/models` supplies the active runtime context window through `meta.n_ctx`.
  If it is missing or invalid, use `WORKBENCH_CONTEXT_WINDOW` as the fallback.
  `meta.n_ctx_train` is not used for request budgeting.
- `POST /v1/messages/count_tokens` counts the prepared system text, messages, tool calls,
  results, and tool definitions. Chat Completions messages are converted to the Messages
  format: separate system text, `tool_use`/`tool_result` blocks, and `input_schema` tools.
- If counting is unsupported or unavailable, the client uses a serialized-request
  character estimate and avoids querying that endpoint again for 60 seconds. Estimates
  are not guaranteed exact. Observed completion usage corrects undercounting upwards.
- Streamed completion usage already records prompt, completion, cached, and uncached
  tokens per call and turn. Cached tokens still occupy context. Budget measurements use
  the latest conversation call, excluding compaction calls; cost totals include all calls.

Input must fit the effective window minus output space and a small safety margin. Output
is capped at the smaller of `WORKBENCH_RESERVE_TOKENS` and one quarter of the window.
Summary requests are counted separately, chunked to fit, capped at 40% of the
context window (up to `WORKBENCH_COMPACTION_MAX_TOKENS`), and bounded by the turn deadline.

Endpoint formats: [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

## Persistence and recovery

A successful compaction appends a `request_compaction` event to the current turn. It stores
one checkpoint plus the retained message suffix and before/after token counts. Replay
starts with the latest such snapshot, then includes subsequent events and turns. Original
turns, query records, and tool results remain stored. Further compactions merge the prior
checkpoint into the new one. Older record-level checkpoints remain readable.

A context rejection triggers one retry with a smaller input target. A generation ending
with `finish_reason=length` before reaching its requested output cap also triggers this
recovery when prompt usage is available. Truncated tool arguments are never executed.
An ordinary output-token limit is reported as incomplete, without a compaction retry.
The recovery consumes a model round and stays within the original turn deadline.

If the fixed instructions, current question, and newest exchange cannot fit, or the retry
still overflows, the existing context-capacity error is returned. A failed summary leaves
persisted history unchanged. Summaries can be lossy; stored query results remain the
source for exact figures. Compaction uses the same deployment-controlled model endpoint.

## Configuration

```bash
WORKBENCH_CONTEXT_WINDOW=32768       # fallback when meta.n_ctx is unavailable
WORKBENCH_RESERVE_TOKENS=8192        # output budget, capped at window / 4
WORKBENCH_COMPACTION_ENABLED=true
# WORKBENCH_COMPACTION_MAX_TOKENS=4096 # optional override; defaults to 40% of context window
```

`WORKBENCH_KEEP_RECENT_TURNS` only applies to the older explicit `compact_now` helper.
The native request path chooses retained history by token size. It no longer schedules
background compaction after a completed turn.

Regression coverage lives in `test_request_compaction.py`, `test_agent.py`,
`test_compaction_budget.py`, `test_compaction_integration.py`, and `test_llm_client.py`.
