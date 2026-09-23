# Workbench Prompt and Policy Ownership

The chat agent system prompt is built in `workbench/prompts.py`. It contains the stable
agent instructions and governed Gold schema. Question-specific catalog hints, the user's
question, and conversation history follow it. Tool names are not appended to system text;
native tool definitions are supplied through the request's `tools` field.

The compaction system prompt and its initial/update instructions live in
`workbench/compaction/summarize.py`. Compaction is a separate model request and has no
additional tool definitions. The model-based suggestion prompt has been removed.

`workbench/access.py` owns role, consent, and deployment source policy. The agent enforces
that policy again immediately before a tool runs. On a provider verified to support Chat
Completions `tool_choice.allowed_tools`, the full tool definition list stays stable while
the allowed subset changes with request policy. Other providers receive a policy-filtered
tool definition list. The frontend toggle does not authorize a call on its own.

The first chat request contains the real user's message. Disk slot snapshots, when
enabled, are scoped to a user and conversation and contain private conversation content.
