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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
