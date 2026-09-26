# Workbench Prompt and Policy Ownership

The chat agent system prompt is built in `workbench/prompts.py`. It contains the stable
agent instructions and governed Gold schema. Question-specific catalog hints, the user's
question, and conversation history follow it. Tool names are not appended to system text;
native tool definitions are supplied through the request's `tools` field.

The request compaction prompt lives in `workbench/compaction/request.py`. It summarizes
older messages and tool observations before a request exceeds the context budget.
Compaction uses the same model endpoint without tool definitions.

`workbench/access.py` owns role, consent, and deployment source policy. The agent sends
only the tool definitions permitted by that policy and enforces the policy again before
running a tool. The frontend toggle does not authorize a call on its own.

The first chat request contains the real user's message. Disk slot snapshots, when
enabled, are scoped to a user and conversation and contain private conversation content.
