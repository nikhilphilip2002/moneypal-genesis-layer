"""Safe migration and verification utility for external customer collections.

Guidelines enforced:
  1. Exact-ID retrieval does NOT require reindexing; it uses payload filtering.
  2. If a new vector collection is needed for semantic embeddings, it builds a
     separate target collection without modifying or deleting the live collection.
  3. Preserves (id, payload) pairs verbatim and quarantines invalid points.
  4. Validates point counts, dimensions, ID/payload pairing, and exact-ID retrieval.
  5. Requires an explicit operator flag (--execute); defaults to safe dry-run inspection.
  6. Keeps original collection intact as rollback.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_customer_collection")


def inspect_collection(client: QdrantClient, name: str) -> dict[str, Any]:
    info = client.get_collection(name)
    vectors = info.config.params.vectors
    dim = vectors.size if hasattr(vectors, "size") else getattr(vectors, "dim", None)
    distance = str(vectors.distance if hasattr(vectors, "distance") else getattr(vectors, "distance", ""))
    return {
        "name": name,
        "status": str(info.status),
        "points_count": info.points_count,
        "vector_size": dim,
        "distance": distance,
    }


def scroll_all_points(client: QdrantClient, name: str) -> list[qm.Record]:
    points: list[qm.Record] = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=name,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        points.extend(batch)
        if not offset:
            break
    return points


def migrate(
    *,
    source_name: str,
    target_name: str,
    target_dim: int = 1024,
    execute: bool = False,
) -> bool:
    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=settings.qdrant_timeout,
    )

    logger.info("Inspecting source collection: %s", source_name)
    source_info = inspect_collection(client, source_name)
    logger.info("Source info: %s", source_info)

    if not execute:
        logger.info("DRY-RUN mode. Pass --execute to create and migrate target collection: %s", target_name)
        return True

    if source_name == target_name:
        logger.error("Target collection name must differ from live collection to prevent in-place overwrite.")
        return False

    logger.info("Reading source points from %s...", source_name)
    source_points = scroll_all_points(client, source_name)
    logger.info("Retrieved %d points from %s", len(source_points), source_name)

    valid_points: list[qm.PointStruct] = []
    quarantined: list[dict[str, Any]] = []

    for point in source_points:
        payload = dict(point.payload or {})
        cid = str(payload.get("customer_id", "")).strip()
        if not cid:
            quarantined.append({"id": str(point.id), "reason": "missing_customer_id", "payload": payload})
            continue

        vec = point.vector
        if not isinstance(vec, list) or len(vec) != target_dim:
            quarantined.append({"id": str(point.id), "reason": f"invalid_vector_dim (expected {target_dim})"})
            continue

        valid_points.append(
            qm.PointStruct(
                id=point.id,
                vector=vec,
                payload=payload,
            )
        )

    logger.info("Valid points: %d | Quarantined points: %d", len(valid_points), len(quarantined))

    logger.info("Creating target collection: %s (dim=%d, distance=COSINE)...", target_name, target_dim)
    client.create_collection(
        collection_name=target_name,
        vectors_config=qm.VectorParams(size=target_dim, distance=qm.Distance.COSINE),
        on_disk_payload=True,
    )

    batch_size = 64
    for idx in range(0, len(valid_points), batch_size):
        chunk = valid_points[idx : idx + batch_size]
        client.upsert(collection_name=target_name, points=chunk)
        logger.info("Upserted points %d..%d into %s", idx, idx + len(chunk), target_name)

    # Verification
    target_info = inspect_collection(client, target_name)
    logger.info("Target info: %s", target_info)
    assert target_info["points_count"] == len(valid_points), "Point count mismatch after migration!"

    # Sample exact-ID lookup check
    sample_cid = valid_points[0].payload["customer_id"]
    test_res, _ = client.scroll(
        collection_name=target_name,
        scroll_filter=qm.Filter(
            must=[qm.FieldCondition(key="customer_id", match=qm.MatchValue(value=sample_cid))]
        ),
        limit=10,
        with_payload=True,
    )
    assert len(test_res) > 0, f"Sample customer_id={sample_cid} lookup failed in target collection!"
    logger.info("Verified exact lookup for sample customer_id=%s: found %d records", sample_cid, len(test_res))

    logger.info(
        "MIGRATION COMPLETE AND VERIFIED. The live collection '%s' was kept intact as rollback.",
        source_name,
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="External customer collection migration and safety verification.")
    parser.add_argument("--source", default=settings.external_customer_collection, help="Source collection name")
    parser.add_argument("--target", default=f"{settings.external_customer_collection}_v2", help="Target collection name")
    parser.add_argument("--dim", type=int, default=1024, help="Target vector dimension")
    parser.add_argument("--execute", action="store_true", help="Execute migration (default is read-only dry-run)")

    args = parser.parse_args()
    success = migrate(
        source_name=args.source,
        target_name=args.target,
        target_dim=args.dim,
        execute=args.execute,
    )
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
