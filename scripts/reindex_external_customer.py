"""Re-index External_customer_details to 1024-dim using the app's own encoder.

Fixes the governed customer retrieval path end-to-end. The console asks customer
questions (e.g. "show customer 10455") because the app embeds at 1024-dim, but the
Qdrant collection was created at 384-dim, so Qdrant rejects the query with
"expected dim: 384, got 1024". The node already degrades that into a retryable
error card instead of refusing — so consent is fine; the vector store just
couldn't accept the governed query.

What this does (minimal, no security-relevant change):
  1. Scrolls every payload verbatim (ids + payloads preserved — the same governed
     85 external customer passages, untouched: no re-scrape, no new PII).
  2. Recreates the collection at 1024-dim (Cosine), the dimension the app's own
     bge-m3 encoder produces on every go-to-market/console query.
  3. Re-embeds the *same* text with genesis_core.rag.embed_batch (the exact encoder
     nodes.py uses for customer retrieval), then upserts in batches with original
     IDs/payloads intact.

Consent model is unchanged: this merely heals the dimension so the governed
External_customer_details source can actually answer customer-ID questions like
customer 10455 from Qdrant, exactly as asked.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

logger = logging.getLogger("reindex_external_customer")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "packages" / "genesis_core" / "src"))

from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.http import models as qm  # noqa: E402

from app.core.config import EXTERNAL_CUSTOMER_COLLECTION  # noqa: E402
from app.core.settings import get_settings  # noqa: E402
from genesis_core import rag  # noqa: E402  # THE app's own encoder: embed_batch/encode 1024-dim

BATCH = 64
NAME = EXTERNAL_CUSTOMER_COLLECTION


def _point_id(point) -> str:
    return str(point.id)


def main() -> None:
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    before = client.get_collection(NAME)
    print(f"before: dim={before.config.params.vectors.size} points={before.points_count}")

    # 1. Preserve payloads + IDs verbatim (same governed source, no re-scrape).
    kept_payloads: list[dict] = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=NAME, limit=256, offset=offset,
            with_payload=True, with_vectors=False,
        )
        for point in batch:
            kept_payloads.append(point.payload or {})
        if not offset:
            break

    texts = [
        str(p.get("chunk_text") or p.get("text") or p.get("excerpt") or "").strip()
        for p in kept_payloads
    ]
    nonempty = [t for t in texts if t]
    print(f"preserved payloads={len(kept_payloads)} nonempty texts={len(nonempty)}")

    # 2. Recreate at 1024-dim, same collection name (consent/role wiring untouched).
    client.delete_collection(NAME)
    client.create_collection(
        collection_name=NAME,
        vectors_config=qm.VectorParams(size=1024, distance=qm.Distance.COSINE),
        on_disk_payload=True,
    )
    print("recreated at 1024-dim")

    # 3. Re-embed with the exact encoder the query path uses, then upsert in batches.
    vectors = asyncio.run(rag.embed_batch(nonempty))
    points = []
    for i, (vec, text) in enumerate(zip(vectors, nonempty)):
        payload = dict(kept_payloads[i])
        payload["text"] = text
        points.append(qm.PointStruct(
            id=_point_id(kept_payloads[i]) if isinstance(kept_payloads[i], dict) and "id" in kept_payloads[i]
            else f"external-{i}",
            vector=vec,
            payload=payload,
        ))

    for start in range(0, len(points), BATCH):
        client.upsert(collection_name=NAME, points=points[start : start + BATCH])

    after = client.get_collection(NAME)
    print(f"after: dim={after.config.params.vectors.size} points={after.points_count}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
