from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from pypdf import PdfReader
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "backend"))

from app.core.config import DATA_DIR, MACRO_COLLECTION, settings  # noqa: E402
from app.registry import load_regulation_categories, source_paths_for_category  # noqa: E402
from app.services import institution_loader as il  # noqa: E402
from app.services.rag import chunk_text, embed_batch  # noqa: E402


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
            try:
                pdf_pages = read_pdf_pages(pdf_path)
            except Exception as exc:
                print(f"  [warn] unreadable, skipped: {pdf_path.name} ({type(exc).__name__})")
                continue
            segments = [
                (page_number, chunk)
                for page_number, page_text in pdf_pages
                for chunk in chunk_text(page_text)
            ]
            vectors = embed_batch([chunk for _, chunk in segments]) if client else []
            for chunk_index, (page_number, chunk) in enumerate(segments):
                payload = {
                    "module": "regulatory",
                    "category_id": category.id,
                    "category": category.display_name,
                    "collection": category.qdrant_collection,
                    "document": pdf_path.name,
                    "source": pdf_path.name,
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
                            vector=vectors[chunk_index],
                            payload=payload,
                        )
                    )
                    if len(points) >= 64:
                        client.upsert(collection_name=category.qdrant_collection, points=points)
                        points.clear()
            print(f"  {pdf_path.name}: {len(segments)} chunks", flush=True)
        if client and points:
            client.upsert(collection_name=category.qdrant_collection, points=points)

    with settings.local_index_path.open("w", encoding="utf-8") as file:
        for row in local_rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote local fallback index: {settings.local_index_path}")


def _qdrant():
    from qdrant_client import QdrantClient

    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=settings.qdrant_timeout,
    )


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _ingest_documents(client, collection: str, paths: list[Path], base_payload: dict) -> int:
    """Chunk, embed and upsert PDFs/markdown/text into `collection` with a uniform payload."""
    from qdrant_client.models import PointStruct

    ensure_collection(client, collection)
    points: list[PointStruct] = []
    total = 0

    def flush():
        nonlocal total
        if points:
            client.upsert(collection_name=collection, points=points)
            total += len(points)
            points.clear()

    for path in paths:
        if not path.exists():
            print(f"  missing: {path}")
            continue
        try:
            if path.suffix.lower() == ".pdf":
                segments = [(page, chunk) for page, text in read_pdf_pages(path) for chunk in chunk_text(text)]
            else:
                segments = [(None, chunk) for chunk in chunk_text(_read_text_file(path))]
        except Exception as exc:
            print(f"  [warn] unreadable, skipped: {path.name} ({type(exc).__name__})")
            continue
        vectors = embed_batch([chunk for _, chunk in segments])
        for chunk_index, ((page, chunk), vector) in enumerate(zip(segments, vectors)):
            payload = {
                **base_payload,
                "collection": collection,
                "document": path.name,
                "source": path.name,
                "page": page,
                "chunk_index": chunk_index,
                "text": chunk,
            }
            points.append(
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{path}:{page}:{chunk_index}")),
                    vector=vector,
                    payload=payload,
                )
            )
            if len(points) >= 64:
                flush()
        print(f"  {path.name}: {len(segments)} chunks", flush=True)
    flush()
    return total


def ingest_macro() -> None:
    data_dir = DATA_DIR / "macro"
    if not data_dir.is_dir():
        print(f"[skip] no data folder for macro ({data_dir})")
        return
    client = _qdrant()
    print(f"Ingesting Macro documents -> {MACRO_COLLECTION}")
    pdfs = sorted(data_dir.glob("*.pdf"))
    n = _ingest_documents(client, MACRO_COLLECTION, pdfs, {"module": "macro"})
    print(f"Macro: {n} chunks into '{MACRO_COLLECTION}'")


def ingest_competitive() -> None:
    client = _qdrant()
    for inst in il.load_all():
        data_dir = DATA_DIR / "competitive" / inst["id"]
        if not data_dir.is_dir():
            print(f"[skip] no data folder for {inst['name']} ({data_dir})")
            continue
        docs = sorted([*data_dir.glob("*.md"), *data_dir.glob("*.pdf"), *data_dir.glob("*.txt")])
        print(f"Ingesting {inst['name']} ({len(docs)} docs) -> {inst['qdrant_collection']}")
        n = _ingest_documents(
            client,
            inst["qdrant_collection"],
            docs,
            {
                "module": "competitive",
                "institution_id": inst["id"],
                "institution": inst["name"],
                "source_url": inst.get("website", ""),
            },
        )
        print(f"  -> {n} chunks")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest module documents into Qdrant.")
    parser.add_argument(
        "module", nargs="?", default="all", choices=["all", "macro", "competitive", "regulatory"]
    )
    parser.add_argument("--no-qdrant", action="store_true", help="Only create local fallback chunks (regulatory).")
    args = parser.parse_args()
    if args.module in ("all", "macro"):
        ingest_macro()
    if args.module in ("all", "competitive"):
        ingest_competitive()
    if args.module in ("all", "regulatory"):
        ingest_regulatory(use_qdrant=not args.no_qdrant)


if __name__ == "__main__":
    main()
