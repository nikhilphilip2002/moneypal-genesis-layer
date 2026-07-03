"""Ingest each regulation's PDF into its own collection.

Put RBI PDFs in ./data (filename must match each JSON's source_doc), then:
    python ingest.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

import reg_loader as rl  # noqa: E402
import rag_helpers as rag  # noqa: E402

if __name__ == "__main__":
    base = os.path.dirname(__file__)
    for reg in rl.load_all():
        doc = reg.get("source_doc")
        path = os.path.join(base, "data", doc) if doc else None
        if not path or not os.path.isfile(path):
            print(f"[skip] missing source_doc for {reg['display_name']} ({path})")
            continue
        print(f"Ingesting {reg['display_name']} -> {reg['qdrant_collection']}")
        rag.ingest_files(
            reg["qdrant_collection"], [path], chunk_words=600, overlap=80,
            extra_payload={"category": reg["id"]},
        )
