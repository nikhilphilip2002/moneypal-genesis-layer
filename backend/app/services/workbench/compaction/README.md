# Workbench conversation compaction

Long conversations are **checkpointed**, not truncated. Three layers, each useful
without the one above it:

```
┌─ layer 1  checkpoint summary    prose, one LLM call, may be lossy, optional
├─ layer 2  session state         figures/sources/refusals, exact, always present
└─ layer 3  recent turns          verbatim, as many as the token budget allows
```

`history.transcript()` assembles all three. Turns that fit none of them are dropped
whole rather than clipped mid-sentence — whatever mattered about them is in layer 2.

## Why not just port the coding agent's design

This is modelled on `pi/packages/coding-agent/src/core/compaction`, with three
deliberate departures.

**No mid-turn cutting.** A coding turn grows without bound through tool calls, so pi
must be able to cut inside one — hence `findCutPoint`, `isSplitTurn`, and a second
prompt for the orphaned turn prefix. A workbench turn is bounded (route → cards →
synthesis) and `transcript()` is built once per turn at `graph.py`, so we always cut on
a turn boundary. None of that machinery is ported.

**Different summary template.** pi summarizes into `Goal / Progress (Done, In Progress,
Blocked) / Next Steps` because its conversations converge on a finished task. Ours is an
analyst investigating — nothing is "blocked", there is no task to complete. See
`prompts.py`: `Line of Enquiry / Resolved Context / Open Threads / Caveats & Refusals`.
The refusals section has no pi equivalent and is load-bearing: forgetting that a role was
denied data makes the model re-promise it next turn.

**Figures never pass through the model.** This is the important one. If pi's summary
loses a file path, the agent re-reads the file. If ours rounds "MSME credit grew 6.5%" to
"about 6%", a wrong number reaches a bank's briefing. pi's answer to the same class of
problem is mechanical file tracking (`extractFileOpsFromMessage`); ours is `state.py`,
which parses figures, periods, sources and refusals straight out of the stored card
payloads and renders them as tagged blocks. Layer 2 is regenerated from the turns on
every request, so it cannot drift from what the summary claims.

## Layout

| Module | LLM | Role |
|---|---|---|
| `budget.py` | no | token accounting, `should_compact` |
| `state.py` | no | figures / sources / metrics / refusals |
| `prompts.py` | — | the two templates |
| `summarize.py` | yes | writes the checkpoint |
| `__init__.py` | — | `maybe_compact` / `compact_now` |

## Token accounting

Trust the provider where it has spoken, estimate only what came after — pi's
`estimateContextTokens`. `set_usage()` records the real `prompt_tokens` on each turn at
synthesis time; turns added since are estimated at a conservative `chars/4`.

```
transcript_tokens = last measured prompt_tokens + estimate(turns after it)
should_compact    = transcript_tokens > CONTEXT_WINDOW - RESERVE_TOKENS
```

## When it runs

From `complete_turn`, **after** the turn, detached via `_spawn_background`. Compacting
where pi does — at context-build time — would put a summarization call between the
user's question and their first streamed token. Our turns are durable, so the checkpoint
can be written while the user reads the previous answer.

Failure is logged and swallowed. `maybe_compact` never raises, and a conversation with no
checkpoint simply falls back to layers 2 and 3.

## Storage

`record_json.compaction` in `workbench_conversations`, at `record_version` 3:

```json
{
  "summary": "## Line of Enquiry …",
  "first_kept_turn_id": "a1b2c3",
  "state": { "figures": [...], "sources_consulted": [...], "refusals": [...] },
  "tokens_before": 24610,
  "created_at": "2026-08-18T…Z"
}
```

v1/v2 records load with `compaction=None` and behave exactly as before; the first write
upgrades them. **Nothing is ever deleted** — `first_kept_turn_id` only moves where
verbatim replay starts. `history.set_compaction(cid, user, None)` discards a checkpoint
and restores full replay, which is the recovery path if one ever proves misleading.

## Config

```bash
WORKBENCH_CONTEXT_WINDOW=32768
WORKBENCH_RESERVE_TOKENS=8192      # headroom for the next turn's prompt and output
WORKBENCH_KEEP_RECENT_TURNS=6
WORKBENCH_COMPACTION_ENABLED=false # layers 2+3 work regardless
WORKBENCH_COMPACTION_MAX_TOKENS=1200
```

Layers 2 and 3 are always on. `WORKBENCH_COMPACTION_ENABLED` gates only the LLM
summarization, so the deterministic behaviour can ship and be observed first.

## Running out of room

Every layer is bounded, so a transcript can always be made to fit:

| Layer | Cap |
|---|---|
| checkpoint summary | `SUMMARY_SHARE` (25%) of the budget, clipped |
| session state | `COMPRESSED_SHARE` (50%) minus the summary; oldest figures shed first |
| figures / refusals / metrics | `MAX_FIGURES` 40 / `MAX_REFUSALS` 8 / `MAX_METRICS` 30 |
| newest turn | always kept, clipped if it alone exceeds the budget |

The newest turn is the one thing never dropped — a transcript without the current
exchange is useless. If it has to be clipped, `Transcript.overflow` is set and the user
is told to start a new session, because no amount of retrying in *this* conversation
will help.

The same message covers the runtime case. `WORKBENCH_RESERVE_TOKENS` is only an estimate
of the system prompt, catalog grammar and question, so a request can still be rejected by
the provider. `_is_context_overflow` in `graph.py` matches those 4xx bodies and surfaces
the identical message with `retryable: false`, rather than the generic "the workbench hit
an error" which would invite a pointless retry.

## Safety properties (asserted in `tests/workbench/test_compaction_integration.py`)

- summarization is always routed `sensitive=True`, so a checkpoint describing loan-book
  turns can never reach Groq
- a response containing a tool call, or no text, is rejected rather than stored
- a summarizer failure leaves the record untouched and the transcript usable
- an unknown `first_kept_turn_id` falls back to full replay
