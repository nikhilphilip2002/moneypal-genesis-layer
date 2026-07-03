"""Pre-download the bge-m3 embedding model (~570MB) so ingestion doesn't stall.

Run once per machine at Hour 0:
    python shared/download_model.py
"""
import os

from sentence_transformers import SentenceTransformer

model = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
print(f"Downloading {model} ... (first run only, ~570MB)")
SentenceTransformer(model)
print("Done. Model is cached locally.")
