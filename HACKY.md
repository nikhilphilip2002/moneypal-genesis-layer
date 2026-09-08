# Codebase Audit: Overengineered & Hacky Implementations in MoneyPal

## 1. Executive Summary & Objective

This document catalogs the overengineered, brittle, and redundant implementations across the MoneyPal codebase. The objective of this audit is to provide a clean blueprint for **simplifying and modernizing** the codebase:
- Replace custom, complex micro-frameworks with **industry-standard, minimal patterns**.
- Remove manual prompt and schema hacks that constrain modern LLM capabilities.
- Unify duplicated clients, conversation stores, and pipelines into a clean, maintainable architecture.

---

## 2. Detailed Findings: Overengineered & Hacky Subsystems

### 1. Fake Tool Calling via Massive Handcrafted JSON Schemas
* **Locations**: 
  - `backend/app/services/nlq/llm/schemas.py:L26-L320`
  - `backend/app/services/nlq/llm/client.py:L212-L252`
* **The Problem**:
  - `OpenAICompatibleClient` lacks support for native OpenAI/Groq tool calling (`tools=[...]`).
  - Instead, the codebase hand-assembles a **320-line tagged-union JSON Schema** (`plan_schema`), containing deeply nested properties for every conceivable plan type (`queryspec`, `sql`, `analysis`, `briefing`, `worklist`, `lookup`, `clarify`, `refusal`).
  - For providers without native schema-decoding BNF grammars (such as Groq), the client literally stringifies this massive schema into the system prompt:
    ```python
    # client.py:L245-L250
    "Respond with a single JSON object and nothing else. It must conform to this JSON schema:\n"
    f"{json.dumps(json_schema, separators=(',', ':'))}"
    ```
    This consumes thousands of unnecessary prompt tokens, introduces latency, and frequently confuses smaller or quantized models.
* **The Minimal Modern Solution**:
  - Use native Function Calling / Tool Calling (`tools=[{"type": "function", "function": ...}]`, `tool_choice="auto"`).
  - The model outputs clean, native function call arguments without requiring a monolithic union schema.

---

### 2. Multi-Hop Step Pipeline Instead of an Agentic Loop
* **Locations**: 
  - `backend/app/services/workbench/models.py:L28`
  - `backend/app/services/workbench/graph.py`
  - `backend/app/services/nlq/ask.py`
* **The Problem**:
  - Rather than running an agent in an unified conversational loop with tools, the orchestrator divides one turn into a sequential conveyor belt of up to 4 separate HTTP requests to the LLM:
    ```python
    # models.py line 28
    Step = Literal["route", "rewrite", "db_plan", "synthesize"]
    ```
    1. `route`: Calls LLM to choose sources.
    2. `rewrite`: Calls LLM to resolve references if elliptical.
    3. `db_plan`: Calls LLM to generate SQL or QuerySpec.
    4. `synthesize`: Calls LLM to stitch together retrieved text.
  - Each step constructs an isolated, ad-hoc prompt and calls a different client instance.
  - Furthermore, two parallel conversational pipelines exist side-by-side: `/workbench/ask` and `/nlq/ask`, each with its own state object (`WorkbenchState` vs `AskContext`).
* **The Minimal Modern Solution**:
  - A single standard ReAct agent loop: the user sends a message in the linear chat thread, the LLM decides which tools to call, inspects the tool output, and streams the answer back in the exact same conversation context.

---

### 3. Hardcoded Anti-LLM Narration & Number Policing
* **Locations**: 
  - `backend/app/services/nlq/narrator.py:L1-L10`
  - `backend/app/services/workbench/composer.py:L74-L83`
* **The Problem**:
  - The codebase explicitly forbids the LLM from providing qualitative insights or narrative analysis on numbers:
    > *"The LLM never writes prose about numbers... The narrator also never recommends. 'Collections fell 12%' is a fact; 'you should tighten underwriting' is outside the brief."* (`narrator.py:L3-L9`)
  - To enforce this, `narrator.py` builds hardcoded, robotic string templates:
    ```python
    # narrator.py:L138-L140
    f"{metric.label} was {format_value(row.get(metric_id), metric.unit)} {scope}."
    ```
  - In `composer.py`, `numbers_are_grounded` uses regex to extract every number in the LLM's response and fails if any number was not present verbatim in the retrieved text:
    ```python
    # composer.py:L74-L78
    _NUMBER = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?%?(?![\w.])")
    ```
    This actively breaks percentage changes, ratios, or inferred metrics calculated by the LLM.
* **The Minimal Modern Solution**:
  - Prompt the LLM as an executive credit analyst: provide the query results and instruct it to explain the *drivers*, *anomalies*, and *actionable business recommendations*.

---

### 4. Overengineered Conversation Compaction & Token Accounting
* **Locations**: 
  - `backend/app/services/workbench/compaction/` (`budget.py`, `state.py`, `summarize.py`, `prompts.py`, `__init__.py`)
  - `backend/app/services/workbench/graph.py:L544`
* **The Problem**:
  - The codebase implements an entire custom mini-framework inspired by coding agents (like `pi`) to track financial numbers across chat turns.
  - In `state.py`, regex figure extractors (`figures.py`) parse quantities to build pipe-separated tables (`Figure | Value | Period | Source | Turn`) injected into every prompt.
  - In `graph.py:L544`, `_spawn_background(compaction.maybe_compact)` fires an unprompted background summarization LLM call after *every completed turn*, appearing as an extra, "fresh" request on model servers.
  - With modern LLMs offering 128k context windows (Llama-3.3-70B, Qwen-32B), typical conversational banking queries (5–15 turns) use less than 3% of the context window.
* **The Minimal Modern Solution**:
  - Maintain a standard linear sliding window of the last $N$ turns directly in memory/PostgreSQL.
  - Background summarization is only needed if token usage exceeds a realistic threshold (e.g. > 80k tokens).

---

### 5. Brittle Regex & String-Slicing JSON Recovery
* **Location**: `backend/app/services/nlq/llm/client.py:L112-L148`
* **The Problem**:
  - In `LLMResult.json()`, manual string slicing and regular expressions are used to salvage malformed JSON completions:
    ```python
    # client.py:L136-L146
    stripped = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", self.text.strip())
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    start, end = stripped.find("{"), stripped.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            pass
    ```
    This brittle heuristic breaks on escaped characters, nested markdown, or top-level JSON arrays.
* **The Minimal Modern Solution**:
  - Use native OpenAI/Groq structured output support (`response_format=PydanticModel`) or Pydantic validation on parsed model output.

---

### 6. OS-Level File-Lock Polling Across Docker Containers
* **Location**: `backend/app/services/nlq/llm/client.py:L44-L75`
* **The Problem**:
  - To serialize local model requests across the API and MCP containers, `client.py` uses an OS-level file descriptor lock (`fcntl.flock`) in an asynchronous polling loop:
    ```python
    # client.py:L64-L69
    while not acquired:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            await asyncio.sleep(0.05)
    ```
  - Using filesystem lock polling across container volumes adds latency, introduces potential stale-lock deadlocks on container crashes, and works around container networking rather than using standard rate limits.
* **The Minimal Modern Solution**:
  - Standard in-process `asyncio.Semaphore` or server-side queuing (e.g., standard concurrency settings in `llama-server` / vLLM / Ollama).

---

### 7. Duplicated LLM Clients, RAG Engines, and Databases
* **The Problem**:
  1. **Duplicate LLM Clients**:
     - Client A: `backend/app/services/nlq/llm/client.py` (custom `httpx.AsyncClient` wrapper with custom retry loops and telemetry).
     - Client B: `packages/genesis_core/src/genesis_core/rag.py` (official `groq.Groq` SDK client with manual rate-limit header snooping).
  2. **Duplicate Conversation Tables**:
     - `public.workbench_conversations` (used by `/workbench/ask`).
     - `public.nlq_conversations` (used by `/nlq/ask`).
  3. **Duplicate RAG Implementations**:
     - Engine A: `backend/app/services/rag.py` (sentence-transformers + custom hash fallback + Qdrant REST).
     - Engine B: `packages/genesis_core/src/genesis_core/rag.py` (SentenceTransformer + QdrantClient).
  4. **Third Caching Database**:
     - `backend/app/services/brief_cache.py`: A local SQLite database (`genesis.db`) storing cached brief JSONs with manual version hashes (`CACHE_VERSION = "v3"`) alongside PostgreSQL.
* **The Minimal Modern Solution**:
  - Consolidate on **one** standard `AsyncOpenAI` client for all model calls.
  - Consolidate on **one** conversation table in PostgreSQL.
  - Consolidate on **one** unified RAG retrieval module.

---

## 3. Summary Comparison Table

| Subsystem | Overengineered / Hacky Implementation | Minimal Modern Pattern |
| :--- | :--- | :--- |
| **Tool Calling** | 320-line JSON Schema union (`schemas.py`) | Standard tool definitions (`tools=[...]`) |
| **Orchestration** | 4-step conveyor belt (`route` -> `rewrite` -> `db_plan` -> `synthesize`) | Single ReAct agentic execution loop |
| **Output Narration** | Hardcoded sentence builder banning LLM insights (`narrator.py`) | LLM prompt synthesizing drivers, anomalies & actions |
| **Conversation Memory** | Multi-layer compaction framework & figure tables (`compaction/`) | Standard sliding window of message turns |
| **Structured Output** | Regex code-fence stripping & substring bracket slicing | Pydantic models / native structured outputs |
| **Concurrency Control** | Cross-container `fcntl.flock` file-lock polling loop | Standard `asyncio.Semaphore` or inference server queue |
| **Client Stacks** | Duplicate LLM clients (`client.py` httpx vs `rag.py` Groq SDK) | Unified `AsyncOpenAI` client instance |
| **Data Persistence** | 2 Postgres conversation tables + 1 SQLite cache (`genesis.db`) | Single `conversations` table in Postgres |

---

## 4. Recommended Simplification Plan

1. **Unify the LLM Client**:
   - Standardize on `AsyncOpenAI` across the entire backend, supporting both Groq and local endpoints via `base_url` and `api_key`.
   - Remove `fcntl.flock` polling and custom code-fence regex salvage.
2. **Implement Native Tool Calling**:
   - Replace the 320-line `plan_schema` and `route_schema` with clean, modular function definitions in `tools.py`.
3. **Collapse Multi-Step Conveyor Belts**:
   - Merge `/workbench/ask` and `/nlq/ask` into a single, clean agent loop that streams SSE frames.
4. **Enable Narrative Insight Generation**:
   - Retire `narrator.py` string templates and regex number policing in `composer.py`.
   - Prompt the LLM to provide meaningful analysis, risk context, and recommendations.
5. **Clean Up Redundant Storage**:
   - Remove the SQLite `genesis.db` cache and merge `nlq_conversations` into `workbench_conversations`.
