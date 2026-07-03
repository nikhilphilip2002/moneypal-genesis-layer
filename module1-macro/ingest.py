"""Ingest Module 1 documents into the macro_intel collection.

Put PDFs/TXTs in ./data first (see docs/TEAM_A_MACRO.md for the source list), then:
    python ingest.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

import rag_helpers as rag  # noqa: E402

COLLECTION = "macro_intel"

if __name__ == "__main__":
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    rag.ingest_folder(COLLECTION, data_dir)
