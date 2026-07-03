"""Pre-download the bge-m3 embedding model (~570MB) so ingestion doesn't stall.

Run once per machine at Hour 0:
    python scripts/download_model.py
"""
from sentence_transformers import SentenceTransformer

from genesis_core import settings

print(f"Downloading {settings.embed_model} ... (first run only, ~570MB)")
SentenceTransformer(settings.embed_model)
print("Done. Model is cached locally.")
