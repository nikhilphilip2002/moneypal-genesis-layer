"""Ingest each institution's documents into its own collection.

Put files in ./data/<institution_id>/ (see docs/TEAM_B_COMPETITIVE.md), then:
    python ingest.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

import institution_loader as il  # noqa: E402
import rag_helpers as rag  # noqa: E402

if __name__ == "__main__":
    base = os.path.dirname(__file__)
    for inst in il.load_all():
        data_dir = os.path.join(base, "data", inst["id"])
        if not os.path.isdir(data_dir):
            print(f"[skip] no data folder for {inst['name']} ({data_dir})")
            continue
        print(f"Ingesting {inst['name']} -> {inst['qdrant_collection']}")
        rag.ingest_folder(
            inst["qdrant_collection"], data_dir, extra_payload={"institution_id": inst["id"]}
        )
