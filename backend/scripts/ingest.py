"""Ingest documents for all or specific modules into Qdrant.

Usage:
    python scripts/ingest.py [macro|competitive|regulatory|all]
"""
import argparse
import sys
from pathlib import Path

# Make backend app package importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from genesis_core import rag
from app.core import config
from app.services import institution_loader as il
from app.services import reg_loader as rl

def ingest_macro(base_dir: Path):
    data_dir = base_dir / "data" / "macro"
    if not data_dir.is_dir():
        print(f"[skip] no data folder for macro ({data_dir})")
        return
    print(f"Ingesting Macro documents -> {config.MACRO_COLLECTION}")
    rag.ingest_folder(config.MACRO_COLLECTION, str(data_dir))

def ingest_competitive(base_dir: Path):
    for inst in il.load_all():
        data_dir = base_dir / "data" / "competitive" / inst["id"]
        if not data_dir.is_dir():
            print(f"[skip] no data folder for competitor {inst['name']} ({data_dir})")
            continue
        print(f"Ingesting Competitor {inst['name']} -> {inst['qdrant_collection']}")
        rag.ingest_folder(
            inst["qdrant_collection"], str(data_dir), extra_payload={"institution_id": inst["id"]}
        )

def ingest_regulatory(base_dir: Path):
    for reg in rl.load_all():
        doc = reg.get("source_doc")
        path = base_dir / "data" / "regulatory" / doc if doc else None
        if not path or not path.is_file():
            print(f"[skip] missing source_doc for regulation {reg['display_name']} ({path})")
            continue
        print(f"Ingesting Regulation {reg['display_name']} -> {reg['qdrant_collection']}")
        rag.ingest_files(
            reg["qdrant_collection"], [str(path)], chunk_words=600, overlap=80,
            extra_payload={"category": reg["id"]},
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents for RAG modules.")
    parser.add_argument(
        "module",
        nargs="?",
        default="all",
        choices=["macro", "competitive", "regulatory", "all"],
        help="Module to ingest (default: all)"
    )
    args = parser.parse_args()
    
    backend_root = Path(__file__).resolve().parents[1]
    
    if args.module in ("macro", "all"):
        ingest_macro(backend_root)
    if args.module in ("competitive", "all"):
        ingest_competitive(backend_root)
    if args.module in ("regulatory", "all"):
        ingest_regulatory(backend_root)
