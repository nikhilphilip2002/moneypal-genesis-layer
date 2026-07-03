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

    # Groq LLM
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Qdrant (shared instance — must be on Aroha_T1 / Aroha_G1 WiFi)
    qdrant_host: str = "192.168.1.183"
    qdrant_port: int = 6333

    # Embeddings
    embed_model: str = "BAAI/bge-m3"
    vector_size: int = 1024  # bge-m3 dimension


settings = Settings()
