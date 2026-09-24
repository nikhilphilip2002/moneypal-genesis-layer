# Workbench Prompt and Cache Plan

## Implemented

- The chat system text has one builder in `backend/app/services/workbench/prompts.py`.
  It no longer appends `AUTHORIZED FUNCTIONS`; question-specific catalog context follows
  the stable prefix.
- The compaction system and checkpoint instructions live with their caller in
  `backend/app/services/workbench/compaction/summarize.py`.
- The unused model-based suggestion prompt, module, tests, and setting were removed.
- The first real chat request goes directly to the model. Synthetic user messages,
  `/apply-template` warm-up, zero-token `/completion`, and global initial-slot restore
  were removed.
- The agent sends a policy-filtered tool catalog and omits `tool_choice` for
  llama-server compatibility. The backend continues to authorize every actual tool call.
- Conversation-scoped disk snapshots are implemented behind
  `LLAMA_SLOT_SNAPSHOTS_ENABLED=false`. When enabled, a successful real model call is
  followed by a slot save, and only the same user's conversation may restore it. The
  snapshot identity includes the model, system prompt, and tool schema. Snapshot files
  contain private conversation content.

## Deployment validation

1. Test the deployed Chat Completions endpoint with the policy-filtered `tools` list and
   no `tool_choice`. Confirm that the request succeeds and excluded tools are not emitted.
   Compare rendered prefixes and measured cached tokens with the source toggle on and off.
   The existing `search_curated_knowledge` function spans internal and external domains,
   so backend argument-level authorization remains necessary.
2. Measure cold, immediate-repeat, and save → erase → restore → repeat requests on the
   deployed Qwen build. Inspect actual reused prompt tokens and first-token latency, not
   just `n_saved` or `n_restored`. Enable snapshots only if restore yields useful reuse
   and the replayed response remains correct.
3. Before enabling snapshots, keep `--slot-save-path` owner-only and configure retention
   for private per-conversation snapshot files. Clear old snapshot files after changing the
   GGUF, llama.cpp build, or chat template. The app currently has no conversation-delete
   endpoint, so snapshot file expiry is an operator responsibility.

## Verification

- `pytest backend/tests/workbench backend/tests/nlq -q`: 1087 passed, 97 skipped.
- `ruff check` on changed Python modules and tests: passed.
- A live llama.cpp cache-hit measurement remains outstanding; optional cache switches
  remain disabled until the deployment checks above pass.
