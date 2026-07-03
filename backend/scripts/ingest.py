from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from pypdf import PdfReader
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.registry import load_regulation_categories, source_paths_for_category  # noqa: E402
from app.services.rag import chunk_text, embed_text  # noqa: E402


def read_pdf_pages(path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((index, text))
    return pages


def ensure_collection(client, collection_name: str) -> None:
    from qdrant_client.models import Distance, VectorParams

    collections = {item.name for item in client.get_collections().collections}
    if collection_name in collections:
        client.delete_collection(collection_name)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=settings.vector_size, distance=Distance.COSINE),
    )


def ingest_regulatory(use_qdrant: bool = True) -> None:
    client = None
    if use_qdrant:
        from qdrant_client import QdrantClient

        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=settings.qdrant_timeout,
        )

    settings.local_index_path.parent.mkdir(parents=True, exist_ok=True)
    local_rows: list[dict[str, object]] = []
    categories = load_regulation_categories()

    for category in categories:
        print(f"Ingesting {category.display_name} -> {category.qdrant_collection}")
        if client:
            ensure_collection(client, category.qdrant_collection)

        points: list[PointStruct] = []
        for pdf_path in source_paths_for_category(category):
            if not pdf_path.exists():
                print(f"  missing: {pdf_path}")
                continue
            for page_number, page_text in read_pdf_pages(pdf_path):
                for chunk_index, chunk in enumerate(chunk_text(page_text)):
                    payload = {
                        "category_id": category.id,
                        "category": category.display_name,
                        "collection": category.qdrant_collection,
                        "document": pdf_path.name,
                        "path": str(pdf_path.relative_to(ROOT)),
                        "page": page_number,
                        "chunk_index": chunk_index,
                        "text": chunk,
                        "source_url": category.rbi_url,
                    }
                    local_rows.append(payload)
                    if client:
                        from qdrant_client.models import PointStruct

                        points.append(
                            PointStruct(
                                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{pdf_path}:{page_number}:{chunk_index}")),
                                vector=embed_text(chunk),
                                payload=payload,
                            )
                        )
                        if len(points) >= 64:
                            client.upsert(collection_name=category.qdrant_collection, points=points)
                            points.clear()
        if client and points:
            client.upsert(collection_name=category.qdrant_collection, points=points)

    with settings.local_index_path.open("w", encoding="utf-8") as file:
        for row in local_rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote local fallback index: {settings.local_index_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest regulation PDFs into Qdrant.")
    parser.add_argument("module", nargs="?", default="regulatory", choices=["regulatory"])
    parser.add_argument("--no-qdrant", action="store_true", help="Only create local fallback chunks.")
    args = parser.parse_args()
    ingest_regulatory(use_qdrant=not args.no_qdrant)


if __name__ == "__main__":
    main()
