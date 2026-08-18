"""Central configuration via pydantic-settings.

Reads environment variables and a `.env` file. Services running from their own
directory will pick up the repo-root `.env` via the relative fallbacks below.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Groq LLM (secondary key takes over when the primary is 75% rate-limited or 429s)
    groq_api_key: str = ""
    groq_api_key_secondary: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Qdrant (shared instance — must be on Aroha_T1 / Aroha_G1 WiFi)
    # QDRANT_URL is the canonical setting and wins when set; host/port remain for
    # deployments that predate it. Keeping both in sync by hand is what let the API
    # (which read QDRANT_URL) and the RAG engine (which read host/port) drift apart.
    qdrant_url: str = ""
    qdrant_host: str = "192.168.1.183"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""
    qdrant_timeout: float = 10.0

    # Embeddings
    embed_model: str = "BAAI/bge-m3"
    vector_size: int = 1024  # bge-m3 dimension


settings = Settings()
