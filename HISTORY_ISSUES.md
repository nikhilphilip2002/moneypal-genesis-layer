# Workbench LLM History and Prompt-Cache Findings

## Summary

A Workbench turn can produce multiple requests to the shared OpenAI-compatible
`/chat/completions` endpoint. The normal native-agent requests are separate HTTP calls,
but they do **not** use disconnected conversation histories: each request reconstructs
the prior conversation and appends the current turn's assistant tool calls and tool
results.

There are, however, other completion paths that use genuinely independent prompts. All
of them share the same llama.cpp server and single request slot, so one of these calls can
replace the KV-cache prefix used by the Workbench agent. The next Workbench request can
then require prompt evaluation from near the beginning even though its message history is
correct.

## Main Workbench Agent History

The main agent loop uses cumulative history:

1. `graph.py` loads the conversation with
   `history.build_native_transcript()`.
2. `agent._select()` builds the prompt from that prior history and the current question.
3. The loop keeps this turn's assistant messages and tool observations in `exchange`.
4. Each subsequent agent request appends `exchange` to the prompt.

Relevant code:

- `backend/app/services/workbench/graph.py:470-472`
- `backend/app/services/workbench/history.py:1173-1215`
- `backend/app/services/workbench/agent.py:209-229`
- `backend/app/services/workbench/agent.py:700-721`
- `backend/app/services/workbench/agent.py:785-790`

Consequently, `agent_select`, `agent_continue`, and the normal `agent_synthesize` round
represent one logical, cumulative transcript. Seeing every request begin with the system
message in llama-server logs is expected because `/chat/completions` is stateless and the
client must retransmit the message array.

The usual tool sequence still requires at least two inference rounds:

```text
agent request -> assistant tool call
local/MCP tool execution -> tool observation
agent request -> final answer or another tool call
```

The second inference cannot be part of the first completion because its input includes a
tool result that does not exist until the first completion has finished and the backend
has executed the tool.

## Completion Calls with Separate Histories

### 1. Conversation compaction

`backend/app/services/workbench/compaction/summarize.py:80` sends a dedicated compaction
system prompt and serialized old turns. It does not use the native agent prompt or the
normal Workbench message array.

Compaction is scheduled after a completed Workbench turn at
`backend/app/services/workbench/graph.py:602-606`, but an LLM request is made only when
the replay exceeds the configured token budget. The check is implemented in
`backend/app/services/workbench/compaction/__init__.py:28-61`.

This feature is disabled by default and is also disabled in the checked-in production
environment configuration:

```text
WORKBENCH_COMPACTION_ENABLED=false
```

If enabled, a compaction call uses a different prefix and can evict the active Workbench
prefix from a single llama.cpp cache slot.

### 2. Startup catalog cache warmup (removed)

The application previously performed an automatic one-token completion using the
standalone NLQ planner prompt and JSON schema during application startup. That warmup was
removed because its prefix was unrelated to the Workbench native-agent prefix and could
displace the useful Workbench prompt from the single llama.cpp cache slot.

This history is unrelated to the Workbench native-agent history. If it runs immediately
before a Workbench request, the llama.cpp slot may contain the planner prefix rather than
the Workbench prefix.

Its shared-client metadata was:

```text
call_purpose=db_plan
call_kind=warmup
```

### 3. Standalone RAG generation

`backend/app/services/rag.py:140-174` sends a direct `/chat/completions` request with its
own regulatory-intelligence system prompt and a single generated user prompt. It bypasses
the normal shared LLM client and does not carry Workbench history or `call_purpose`
metadata.

Legacy macro, regulatory, competitive, policy, and platform services call this RAG
generation path. The current Workbench agent nodes retrieve passages without invoking
RAG generation, so an ordinary Workbench tool execution should not trigger this call.
Another page, API request, scheduled operation, or concurrent user can still invoke it
against the same llama.cpp server and replace the cached Workbench prefix.

### 4. Suggestion personalization

`backend/app/services/workbench/suggestions.py:55-65` has an independent system prompt,
user message, and JSON schema. It does not use the main Workbench transcript.

No production caller for `suggestions.personalize()` currently exists, so this is a real
completion call site but is not presently responsible for requests observed during a
Workbench turn.

## Claim Repair and Fallback Synthesis

The claim-repair request in `backend/app/services/workbench/graph.py:121-156` is a
separate HTTP completion, but it is not built from an unrelated history. It starts with
the saved `agent_synthesis_messages` context and appends:

- the assistant's candidate answer; and
- a user message containing unsupported-claim feedback and verified facts.

Similarly, fallback synthesis at `backend/app/services/workbench/graph.py:310-340` starts
from the saved native synthesis context and appends a facts message when needed.

These requests should retain a large common prompt prefix unless another request has
already displaced the llama.cpp slot or the provider invalidates its reusable prompt
state.

## Why a Correct History Can Still Have a Cold Cache

All shared-client calls acquire the global gate in
`backend/app/services/nlq/llm/client.py:38-74`. The gate serializes inference, but it does
not associate a persistent KV-cache with a conversation or call purpose.

With llama-server configured as `--parallel 1 --cache-prompt`, there is effectively one
active cached prompt sequence. Any intervening request with a different prefix can
replace it, including:

- a standalone `/nlq` request;
- compaction, if enabled and over its threshold;
- a legacy RAG generation request;
- another user's Workbench request; or
- another application process that targets the same model endpoint without using the
  shared lock.

Serialization prevents simultaneous inference but does not prevent this cache eviction.
Therefore, low cached-token percentages do not by themselves prove that the Workbench
agent dropped its conversation history.

## How to Identify the Cold Request

The shared client records `call_purpose`, `call_kind`, prompt-token counts, and cached
prompt-token counts in `backend/app/services/nlq/llm/client.py:455-616`.

Use these fields to distinguish requests:

| `call_purpose` | History/prompt source |
| --- | --- |
| `agent_select` | Main cumulative Workbench agent history |
| `agent_continue` | Main cumulative Workbench agent history plus tool exchanges |
| `agent_synthesize` | Main synthesis/repair context |
| `compaction` | Independent compaction prompt |
| `suggestions` | Independent suggestion prompt |
| Missing normal purpose metadata | Possible direct legacy RAG request |

Correlating the cold llama-server request with the backend's `call_purpose` is necessary
to determine which independent path displaced the cache.

## Confirmed Conclusions

- Multiple sequential LLM HTTP requests per Workbench turn exist.
- Normal native-agent rounds carry cumulative conversation and tool history.
- Several other completion paths use genuinely separate histories.
- All paths can contend for the same llama.cpp slot and prompt cache.
- The global file lock serializes requests but does not preserve per-conversation caches.
- Compaction is a separate-history call, but it is disabled in the checked-in production
  configuration.
- The unrelated startup planner warmup has been removed.
- Direct legacy RAG generation also uses a separate prefix and bypasses shared-client
  purpose telemetry.
- A cold prompt must be correlated with `call_purpose` before attributing it to lost
  Workbench history.
