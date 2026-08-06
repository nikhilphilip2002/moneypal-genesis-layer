from functools import lru_cache
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

BASE_DIR = Path(__file__).resolve().parents[2]   # backend/
REGISTRY_DIR = BASE_DIR / "registry"             # institution/regulation JSON configs
DATA_DIR = BASE_DIR / "data"                     # ingested PDFs/TXTs (gitignored)

# Qdrant collections
MACRO_COLLECTION = "macro_intel1"
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

        self.regulations_dir = Path(get("REGULATIONS_DIR", str(REPO_ROOT / "Regulations")) or REPO_ROOT / "Regulations")
        self.registry_dir = Path(get("REGISTRY_DIR", str(REPO_ROOT / "backend" / "registry" / "regulations")) or REPO_ROOT / "backend" / "registry" / "regulations")
        self.local_index_path = Path(get("LOCAL_INDEX_PATH", str(REPO_ROOT / "backend" / "vector_store" / "regulatory_chunks.jsonl")) or REPO_ROOT / "backend" / "vector_store" / "regulatory_chunks.jsonl")
        self.cors_origins = ["*"]

        # --- NLQ (natural-language query layer) -------------------------------------
        # Provider-agnostic by design: the GPU node is not procured yet, so llama.cpp is
        # selected by config at deploy time and Groq carries development.
        self.nlq_llm_provider = (get("NLQ_LLM_PROVIDER", "groq") or "groq").lower()
        self.nlq_llm_base_url = get("NLQ_LLM_BASE_URL", "http://localhost:8080/v1") or "http://localhost:8080/v1"
        self.nlq_llm_model = get("NLQ_LLM_MODEL", "qwen3.6-32b-instruct-q4_K_M") or "qwen3.6-32b-instruct-q4_K_M"
        self.nlq_llm_api_key = get("NLQ_LLM_API_KEY")          # llama.cpp ignores it; kept for gateways
        self.nlq_llm_timeout_s = float(get("NLQ_LLM_TIMEOUT_S", "30") or "30")
        self.nlq_llm_max_retries = int(get("NLQ_LLM_MAX_RETRIES", "1") or "1")
        # Qwen3 and its relatives think by default, and llama-server returns that trace in
        # `reasoning_content` with `content` left empty — the planner then sees no JSON at
        # all. Nothing on this path wants free-form reasoning, so thinking is off unless a
        # deployment explicitly asks for it.
        self.nlq_llm_thinking = (get("NLQ_LLM_THINKING", "false") or "false").lower() in (
            "1", "true", "yes", "on",
        )

        # Read-only database role (see docs/GENESIS_NLQ_BUILD_PLAN.md §7.1). Separate
        # credentials from the app role — this is the real security boundary, so it must
        # never silently fall back to POSTGRES_USER.
        self.nlq_db_user = get("NLQ_DB_USER", "nlq_readonly") or "nlq_readonly"
        self.nlq_db_password = get("NLQ_DB_PASSWORD")
        self.nlq_statement_timeout_ms = int(get("NLQ_STATEMENT_TIMEOUT_MS", "15000") or "15000")
        self.nlq_max_rows = int(get("NLQ_MAX_ROWS", "5000") or "5000")

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
