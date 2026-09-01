from functools import lru_cache
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

BASE_DIR = Path(__file__).resolve().parents[2]   # backend/
REGISTRY_DIR = BASE_DIR / "registry"             # institution/regulation JSON configs
DATA_DIR = BASE_DIR / "data"                     # ingested PDFs/TXTs (gitignored)

# Qdrant collections. MACRO_COLLECTION is bound from settings at the bottom of this
# module (the env loader is defined below); it stays a module-level constant so the
# existing `from app.core.config import MACRO_COLLECTION` imports keep working.
LANDSCAPE_ANCHOR = "comp_sidbi"                  # anchor collection for the landscape summary


def _load_env_file() -> dict[str, str]:
    env_path = REPO_ROOT / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class Settings:
    def __init__(self) -> None:
        env_file = _load_env_file()

        def get(name: str, default: str | None = None) -> str | None:
            return os.environ.get(name) or env_file.get(name) or default

        self.groq_api_key = get("GROQ_API_KEY")
        self.groq_api_key_secondary = get("GROQ_API_KEY_SECONDARY")
        self.groq_model = get("GROQ_MODEL", "llama-3.3-70b-versatile") or "llama-3.3-70b-versatile"

        self.qdrant_url = get("QDRANT_URL", "http://localhost:6333") or "http://localhost:6333"
        self.qdrant_api_key = get("QDRANT_API_KEY")
        self.qdrant_timeout = float(get("QDRANT_TIMEOUT", "20.0") or "20.0")

        self.embedding_model = get("EMBEDDING_MODEL", "BAAI/bge-m3") or "BAAI/bge-m3"
        self.vector_size = int(get("VECTOR_SIZE", "1024") or "1024")
        self.collection_prefix = get("COLLECTION_PREFIX", "reg_") or "reg_"

        # --- Macro intelligence ingestion pipeline ----------------------------------
        # Point MACRO_COLLECTION at a scratch collection to exercise the refresh/purge
        # cycle without touching the collection the macro API serves from.
        self.macro_collection = get("MACRO_COLLECTION", "macro_intel1") or "macro_intel1"
        self.macro_data_dir = Path(get("MACRO_DATA_DIR", str(DATA_DIR / "macro")) or DATA_DIR / "macro")
        self.macro_state_file = Path(
            get("MACRO_STATE_FILE", str(DATA_DIR / "macro" / "state.json")) or DATA_DIR / "macro" / "state.json"
        )
        self.macro_sources_file = Path(
            get("MACRO_SOURCES_FILE", str(BASE_DIR / "scripts" / "macro_pipeline" / "sources.txt"))
            or BASE_DIR / "scripts" / "macro_pipeline" / "sources.txt"
        )
        # Weekly refresh. APScheduler day_of_week names: mon,tue,wed,thu,fri,sat,sun.
        self.macro_schedule_day = get("MACRO_SCHEDULE_DAY", "sun") or "sun"
        self.macro_schedule_hour = int(get("MACRO_SCHEDULE_HOUR", "10") or "10")
        self.macro_schedule_minute = int(get("MACRO_SCHEDULE_MINUTE", "0") or "0")
        self.macro_schedule_tz = get("MACRO_SCHEDULE_TZ", "Asia/Kolkata") or "Asia/Kolkata"
        # Off by default: a container restart should not trigger a full crawl.
        self.macro_run_on_startup = (get("MACRO_RUN_ON_STARTUP", "false") or "false").lower() in (
            "1", "true", "yes", "on",
        )
        # Stale-point purge. The min-ratio rail stops a blocked crawl from emptying the
        # collection — three of the four configured sources are auth/JS/TLS gated today.
        self.macro_purge_stale = (get("MACRO_PURGE_STALE", "true") or "true").lower() in (
            "1", "true", "yes", "on",
        )
        self.macro_purge_min_ratio = float(get("MACRO_PURGE_MIN_RATIO", "0.5") or "0.5")
        # Off by default: macro_intel1 holds points from an earlier ingest with a
        # different payload schema, covering sources the crawler cannot reach today.
        # Retiring them is a deliberate migration (`run.py migrate`), not a side effect
        # of the first weekly refresh.
        self.macro_purge_legacy = (get("MACRO_PURGE_LEGACY", "false") or "false").lower() in (
            "1", "true", "yes", "on",
        )
        self.macro_max_pages_per_site = int(get("MACRO_MAX_PAGES_PER_SITE", "100") or "100")
        self.macro_max_depth = int(get("MACRO_MAX_DEPTH", "2") or "2")
        self.macro_max_files_per_site = int(get("MACRO_MAX_FILES_PER_SITE", "50") or "50")
        self.macro_max_download_mb = int(get("MACRO_MAX_DOWNLOAD_MB", "80") or "80")
        self.macro_request_delay_s = float(get("MACRO_REQUEST_DELAY_S", "1.0") or "1.0")
        self.macro_request_timeout_s = float(get("MACRO_REQUEST_TIMEOUT_S", "45") or "45")
        self.macro_respect_robots = (get("MACRO_RESPECT_ROBOTS", "true") or "true").lower() in (
            "1", "true", "yes", "on",
        )

        self.regulations_dir = Path(get("REGULATIONS_DIR", str(REPO_ROOT / "Regulations")) or REPO_ROOT / "Regulations")
        self.registry_dir = Path(get("REGISTRY_DIR", str(REPO_ROOT / "backend" / "registry" / "regulations")) or REPO_ROOT / "backend" / "registry" / "regulations")
        self.local_index_path = Path(get("LOCAL_INDEX_PATH", str(REPO_ROOT / "backend" / "vector_store" / "regulatory_chunks.jsonl")) or REPO_ROOT / "backend" / "vector_store" / "regulatory_chunks.jsonl")
        self.cors_origins = ["*"]

        # --- Standing signals --------------------------------------------------------
        # The background scan. Off by default in tests and in any process that should not be
        # holding read-only connections; on in the deployed API, where it is the only way
        # "what are the emerging issues?" gets a baseline to answer against.
        self.signals_scan_enabled = (
            get("SIGNALS_SCAN_ENABLED", "true") or "true"
        ).lower() in ("1", "true", "yes", "on")
        self.signals_scan_interval_s = int(get("SIGNALS_SCAN_INTERVAL_S", "21600") or "21600")

        # --- NLQ (natural-language query layer) -------------------------------------
        # Provider-agnostic by design: the GPU node is not procured yet, so llama.cpp is
        # selected by config at deploy time and Groq carries development.
        self.nlq_llm_provider = (get("NLQ_LLM_PROVIDER", "groq") or "groq").lower()
        self.nlq_llm_base_url = get("NLQ_LLM_BASE_URL", "http://localhost:8080/v1") or "http://localhost:8080/v1"
        self.nlq_llm_model = get("NLQ_LLM_MODEL", "qwen3.6-32b-instruct-q4_K_M") or "qwen3.6-32b-instruct-q4_K_M"
        self.nlq_llm_api_key = get("NLQ_LLM_API_KEY")          # llama.cpp ignores it; kept for gateways
        self.nlq_llm_timeout_s = float(get("NLQ_LLM_TIMEOUT_S", "30") or "30")
        self.nlq_llm_max_retries = int(get("NLQ_LLM_MAX_RETRIES", "1") or "1")
        # End-to-end budget for one streamed NLQ turn. Local llama.cpp deployments
        # can need more than 20 seconds to evaluate a cold Gold-catalog prompt even
        # when both the model and database are healthy.
        self.nlq_request_budget_s = float(
            get("NLQ_REQUEST_BUDGET_S", "60") or "60"
        )
        # Qwen3 and its relatives think by default, and llama-server returns that trace in
        # `reasoning_content` with `content` left empty — the planner then sees no JSON at
        # all. Nothing on this path wants free-form reasoning, so thinking is off unless a
        # deployment explicitly asks for it.
        self.nlq_llm_thinking = (get("NLQ_LLM_THINKING", "false") or "false").lower() in (
            "1", "true", "yes", "on",
        )
        # The text-to-SQL long tail can augment catalog matching with embeddings. Keep it
        # configurable because an isolated MCP container may not carry a warm model cache;
        # downloading bge-m3 during a user request exceeds the MCP deadline. Lexical mode
        # still uses the catalog's curated labels and synonyms and never changes SQL safety.
        self.nlq_catalog_vectors = (get("NLQ_CATALOG_VECTORS", "true") or "true").lower() in (
            "1", "true", "yes", "on",
        )

        # Read-only database role (see docs/GENESIS_NLQ_BUILD_PLAN.md §7.1). Separate
        # credentials from the app role — this is the real security boundary, so it must
        # never silently fall back to POSTGRES_USER.
        self.nlq_db_user = get("NLQ_DB_USER", "nlq_readonly") or "nlq_readonly"
        self.nlq_db_password = get("NLQ_DB_PASSWORD")
        self.nlq_statement_timeout_ms = int(get("NLQ_STATEMENT_TIMEOUT_MS", "15000") or "15000")
        self.nlq_max_rows = int(get("NLQ_MAX_ROWS", "5000") or "5000")
        # Temporary rollout mode requested by the product owner: all authenticated
        # Workbench roles can query and view governed PII fields. Set false when the
        # role-permission matrix is ready; the existing masking code becomes active again.
        self.nlq_open_pii_access = (
            get("NLQ_OPEN_PII_ACCESS", "true") or "true"
        ).lower() in ("1", "true", "yes", "on")

        # PostgreSQL access can be switched between the in-process adapter and the MCP
        # service. Direct remains the safe fallback; `mcp` makes the protocol boundary real
        # so deployments can measure its latency and operational trade-offs.
        self.postgres_access_mode = (get("POSTGRES_ACCESS_MODE", "direct") or "direct").lower()
        if self.postgres_access_mode not in ("direct", "mcp"):
            self.postgres_access_mode = "direct"
        self.postgres_mcp_url = get("POSTGRES_MCP_URL", "http://postgres-mcp:8001/mcp") or "http://postgres-mcp:8001/mcp"
        self.postgres_mcp_timeout_s = float(get("POSTGRES_MCP_TIMEOUT_S", "30") or "30")

        # Exa is a public-web boundary. It is independently gated so deployments can keep
        # the private Workbench running when the external search quota or network is down.
        self.exa_api_key = get("EXA_API_KEY")
        self.exa_mcp_enabled = (get("EXA_MCP_ENABLED", "false") or "false").lower() in (
            "1", "true", "yes", "on",
        )
        self.exa_mcp_url = (
            get(
                "EXA_MCP_URL",
                "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa,web_search_advanced_exa",
            )
            or "https://mcp.exa.ai/mcp"
        )
        self.exa_mcp_timeout_s = float(get("EXA_MCP_TIMEOUT_S", "30") or "30")
        self.exa_search_max_results = max(
            1, min(10, int(get("EXA_SEARCH_MAX_RESULTS", "8") or "8"))
        )
        self.exa_fetch_max_pages = max(
            0, min(3, int(get("EXA_FETCH_MAX_PAGES", "2") or "2"))
        )
        self.exa_cache_ttl_s = max(0, int(get("EXA_CACHE_TTL_S", "3600") or "3600"))
        self.exa_daily_user_limit = max(
            1, int(get("EXA_DAILY_USER_LIMIT", "10") or "10")
        )

        # --- Workbench (unified chat orchestrator) ----------------------------------
        # Completely local by default: every orchestration step runs on the llama.cpp
        # provider regardless of what NLQ_LLM_PROVIDER is set to. Groq stays wired but is
        # only reachable when a deployment explicitly opts in AND the step is non-sensitive
        # (public macro/competitive/regulatory synthesis, never the loan book).
        self.workbench_local_only = (get("WORKBENCH_LOCAL_ONLY", "true") or "true").lower() in (
            "1", "true", "yes", "on",
        )
        self.workbench_groq_opt_in = (get("WORKBENCH_GROQ_OPT_IN", "false") or "false").lower() in (
            "1", "true", "yes", "on",
        )
        # Router and synthesizer may point at two different local models later; today they
        # default to the same NLQ local model, so one llama-server serves both.
        self.workbench_router_model = get("WORKBENCH_ROUTER_MODEL") or self.nlq_llm_model
        self.workbench_synth_model = get("WORKBENCH_SYNTH_MODEL") or self.nlq_llm_model

        # --- Workbench conversation compaction --------------------------------------
        # The transcript budget was previously expressed in characters because no token
        # count was persisted. Real prompt_tokens from the provider are now recorded per
        # turn, so the budget is stated in the unit the context window is actually in.
        self.workbench_context_window = int(get("WORKBENCH_CONTEXT_WINDOW", "32768") or "32768")
        # Headroom for the next turn's system prompt, catalog grammar and output. Smaller
        # than a coding agent's: workbench answers are 300-500 tokens, not long diffs.
        self.workbench_reserve_tokens = int(get("WORKBENCH_RESERVE_TOKENS", "8192") or "8192")
        self.workbench_keep_recent_turns = int(get("WORKBENCH_KEEP_RECENT_TURNS", "6") or "6")
        # Summarization stays dark until the deterministic phases are proven in place;
        # with it off the transcript still gets token-accurate budgeting and the
        # mechanically extracted session state.
        self.workbench_compaction_enabled = (
            get("WORKBENCH_COMPACTION_ENABLED", "false") or "false"
        ).lower() in ("1", "true", "yes", "on")
        self.workbench_compaction_max_tokens = int(
            get("WORKBENCH_COMPACTION_MAX_TOKENS", "1200") or "1200"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

MACRO_COLLECTION = settings.macro_collection
