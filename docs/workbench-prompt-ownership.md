# Workbench Prompt and Policy Ownership

Each instruction has one enforcement owner. Prompt text may remind the model of a boundary,
but reminders do not replace application enforcement.

| Concern | Owner |
|---|---|
| Source consent, role intersection, deployment kill switch | `workbench/access.py` |
| Read-only SQL, tables, columns, PII and row limits | NLQ compiler/validator/executor |
| Router output shape and allowed source IDs | `route_schema` structured output |
| DB planning output shape | NLQ planner structured output |
| Retrieval metadata, citations, failures and limitations | source result/evidence envelope |
| Grounded answer behavior and citation presentation | minimal composer system prompt |
| Final answer fields | typed application response contract |
| Conversation transcript selection and compaction | Workbench history/compaction code |

The router, DB planner, and composer use separate versioned prompt builders. Stable prefix
bytes are deterministic and logged only by SHA-256 fingerprint. JSON schemas are passed as
structured-output contracts and are not duplicated verbatim inside native-schema prompts.
