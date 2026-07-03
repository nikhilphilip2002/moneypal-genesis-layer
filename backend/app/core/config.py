"""Application-level configuration for the Genesis backend.

Shared infra settings (Qdrant, Groq, embeddings) come from `genesis_core.settings`.
This file holds only backend-specific constants and paths.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]   # backend/
REGISTRY_DIR = BASE_DIR / "registry"             # institution/regulation JSON configs
DATA_DIR = BASE_DIR / "data"                     # ingested PDFs/TXTs (gitignored)

# Qdrant collections
MACRO_COLLECTION = "macro_intel"
LANDSCAPE_ANCHOR = "comp_sidbi"                  # anchor collection for the landscape summary
