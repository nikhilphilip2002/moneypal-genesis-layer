# Legacy and compatibility inventory

This document records legacy code and compatibility behavior around the Workbench and the
adjacent NLQ subsystem. It distinguishes compatibility that is still required from runtime
fallbacks that are part of the current design. The current `/workbench/ask` path always uses
one provider-native agent and one native conversation transcript.

## Removed legacy composition path

The separate Workbench composer system prompt, prompt version, prompt builder, compact-history
input, and non-native synthesis branch were removed in September 2026. The native agent now owns
tool selection, continuation, and final synthesis under `AGENT_SYSTEM_PROMPT`.

The internal output-limit setting and environment variable were renamed from
`workbench_composer_max_tokens` / `WORKBENCH_COMPOSER_MAX_TOKENS` to
`workbench_agent_synthesis_max_tokens` / `WORKBENCH_AGENT_SYNTHESIS_MAX_TOKENS` at the same time.

`backend/app/services/workbench/composer.py` remains despite its historical name. It does not
define or run a second agent. It contains active deterministic answer-safety utilities:
evidence bounding, numeric-claim validation, verified-fact rendering, repair instructions, and
the extractive last-resort response.

## History compatibility still retained

### Record versions 1 through 6

`backend/app/services/workbench/history.py` reads record versions 1 through 7. Older turns are
converted in memory to the version-7 ordered event stream by `derive_turn_events()`,
`migrate_turn()`, and `migrate_record()`. A later write persists the migrated representation.

Removal condition: every durable conversation has been migrated to version 7 and the agreed
retention window for older database backups has expired.

### Legacy owner

Version-1 history rows had no owner and use the synthetic `legacy` owner. They are visible only
to `moneypal_admin` through `_visible_owners()`.

Removal condition: unowned records have been deleted or assigned to a defensible owner.

### Duplicate per-turn fields

The version-7 event stream is authoritative, but turn records still expose or maintain older
fields including `sources`, `cards`, `synthesis`, `refusal`, `error`, and `agent_exchanges`.
`set_answer()` mirrors final answer text into `synthesis` for older clients.

Removal condition: all API clients and migration tooling read the event stream or the current
normalized API contract instead of the old stored fields.

### Duplicate `agent_exchanges` writes

`history.add_agent_exchange()` can write the pre-v7 `agent_exchanges` copy in addition to event
stream entries. `WORKBENCH_HISTORY_WRITE_LEGACY_EXCHANGES` controls this and currently defaults
to `true`; comments identify it as a rollback-window feature. Current v7 replay reads events.

Removal condition: close the v7 rollback window, default the flag to `false`, verify production,
then remove the flag and duplicate write.

### Legacy card persistence

`history.add_card()` records a rendered result without a native tool exchange. It exists for
the former source-handler path. The current native agent persists cards through
`add_agent_exchange()`; no production caller of `add_card()` was found in this audit.

Removal condition: confirm no external Python caller imports it, then remove it and its legacy
tests.

### One-shot history helper

`history.record_turn()` is a compatibility helper for the old one-shot history API. Current
Workbench requests use `begin_turn()`, event writers, and `complete_turn()`.

Removal condition: remove or migrate remaining tests and external callers using the helper.

### Old History-rail response normalization

`backend/app/api/routes/workbench.py::_turn_for_api()` constructs missing IDs, routes, policies,
answers, and timestamps for older records. `legacy_answer_unavailable` tells the frontend that a
version-1 question/source stub did not retain its answer. `WorkbenchTurn.tsx` renders the related
notice.

Removal condition: the API no longer needs to serve pre-current records.

## Type compatibility still retained

`backend/app/services/workbench/results.py` keeps `SourceResult` as an alias of `ToolResult` and
keeps the `kind` property as a compatibility name. New native-agent code should use
`ToolResult` and `card_type`.

Removal condition: update source handlers, audit callers, and tests to the current names.

## Separate legacy NLQ product surface

The older `/nlq` API, planner, deterministic `QuerySpec` execution pipeline, saved questions,
drilldowns, worklists, dashboards, and autocomplete support remain in the repository. They are
not an automatic fallback for `/workbench/ask`; a Workbench agent failure does not route a
question through the retired NLQ conversational path or directly to a provider.

The Workbench intentionally reuses several current NLQ assets:

- the governed Gold catalog and query contracts;
- the deterministic chart and analysis renderers;
- `/nlq/execute` for explicit saved-query and drilldown execution;
- record lookup for optional Workbench autocomplete;
- PostgreSQL MCP execution built on the governed NLQ data layer.

These shared pieces must not be deleted merely because they live under `services/nlq`.

`backend/app/services/workbench/models.py` explicitly selects the local provider for Workbench,
using the same configured LLM endpoint as `/nlq`.

## Source-adapter remnants

`backend/app/services/workbench/nodes.py` is historically named after the former graph-node
architecture, but its source adapters are active native tool handlers. The unused private helper
`_extractive_fallback()` has no caller and is a cleanup candidate.

The `history_messages` parameters formerly accepted by `run_macro()` and `run_knowledge()` were
unused remnants of per-source model calls and were removed with the composer prompt path.

## Current runtime fallbacks that are not legacy

The following behavior is intentional resilience and should not be removed as legacy cleanup:

- native tool argument, protocol, execution, and policy-denial repair within the turn budget;
- numeric-claim validation and one focused native-agent synthesis repair;
- extractive evidence when synthesis fails or every numeric sentence is unsupported;
- deterministic chart summaries when an extra model synthesis is unnecessary;
- in-memory conversation retention when the history database is temporarily unavailable;
- conversation checkpointing and explicit context-overflow errors;
- source-local degradation: catalog definitions for concepts, registry metadata for competitors,
  regulation details when regulatory vector search has no hits, and typed unavailable cards;
- empty optional autocomplete results during database cooldown;
- privacy refusal and source-access enforcement.

## Known cleanup candidates

1. Disable and later remove duplicate `agent_exchanges` writes.
2. Remove `history.add_card()` after confirming there are no external callers.
3. Remove `history.record_turn()` after migrating compatibility callers and tests.
4. Remove `nodes._extractive_fallback()`, which currently has no callers.
5. Remove pre-v7 migration and API normalization only after stored-history retention permits it.
6. Consider renaming `composer.py` to `grounding.py` so its active role is unambiguous.
