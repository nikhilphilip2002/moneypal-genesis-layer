"""Re-index External_customer_details to 1024-dim (matches the app's own encoder).

The console currently answers customer questions with a retryable error card because
the collection was built at 384-dim by the go-to-market encoder, but the workbench
retrieval path (nodes.run_customer -> genesis_core.rag.search_multi) embeds queries at
1024-dim. Qdrant rejects every probe (dim 384 vs 1024), and the node's consent gate is
fine — retrieval simply cannot complete.

This script:
  1. scrolls all 85 vectors, preserving each point's ID + payload verbatim (same
     governed reviewer-approved passages — no new scraping, no other customer data);
  2. deletes and recreates the same-named collection at 1024-dim (Cosine);
  3. re-embeds the *same* text with the app's exact encoder (genesis_core.rag),
     keeping the original point IDs and payloads, and upserts in batches of 64.

Usage (from repo root):
  .venv\\Scripts\\python.exe -X utf8 scripts\\reindex_external_customer.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
sys.path.insert(0, str(root / "packages" / "genesis_core" / "src"))

from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.http import models as qm  # noqa: E402

from app.core.config import EXTERNAL_CUSTOMER_COLLECTION  # noqa: E402
from app.core.config import get_settings  # noqa: E402  # same module the workbench nodes import
from genesis_core import rag  # noqa: E402  # the app's own encoder: embed_batch -> 1024-dim (bge-m3)

logger = logging.getLogger("reindex_external_customer")
DIM = 1024
BATCH = 64


def text_of(payload: dict) -> str:
    for key in ("text", "chunk_text", "excerpt", "scraped_snippet"):
        if str(payload.get(key, "")).strip():
            return str(payload[key]).strip()
    return str(payload.get("chunk", "")).strip()


def main() -> None:
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    name = EXTERNAL_CUSTOMER_COLLECTION

    before = client.get_collection(name)
    logger.info(
        "before: dim=%s points=%s", before.config.params.vectors.size, before.points_count,
    )
    """Migrate this collection's payloads as-is (same text, same consent, same point ids)."""

    # 1. Scroll everything verbatim.
    ids: list[str] = []
    payloads: list[dict] = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=name, limit=256, offset=offset,
            with_payload=True, with_vectors=False,
        )
        for point in batch:
            ids.append(str(point.id))
            payloads.append(point.payload or {})
        if not offset:
            break
    logger.info("scrolled %d points", len(ids))

    texts = [text_of(p) for p in payloads]
    nonempty = [t for t in texts if t]
    logger.info("payloads with readable text: %d", len(nonempty))

    # 2. Recreate at 1024.
    client.delete_collection(name)
    client.create_collection(
        collection_name=name,
        vectors_config=qm.VectorParams(size=DIM, distance=qm.Distance.COSINE),
        on_disk_payload=True,
    )
    logger.info("recreated at %d dim", DIM)

    # 3. Re-embed with the app's own encoder, keep ids + payloads.
    vectors = rag.embed_batch(nonempty)
    for start in range(0, len(nonempty), BATCH):
        end = min(start + BATCH, len(nonempty))
        client.upsert(
            collection_name=name,
            points=[
                qm.PointStruct(id=ids[i], vector=vectors[i], payload=payloads[i])
                for i in range(start, end)
            ],
        )
        logger.info("upserted %d..%d", start, end)

    after = client.get_collection(name)
    logger.info(
        "after: dim=%s points=%s", after.config.params.vectors.size, after.points_count,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
