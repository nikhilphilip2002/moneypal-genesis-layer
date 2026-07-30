"""Embed the catalog into Qdrant, once, at build time.

Reuses the embedding and Qdrant plumbing already in genesis_core (bge-m3, cosine, the same
host) against a new `nlq_catalog` collection, so there is one vector stack in the product
rather than two.

Run after any catalog edit:
    python -m app.services.nlq.catalog.index

The collection is versioned by the catalog's content hash. A catalog edit therefore lands
in a new namespace instead of leaving stale vectors behind that would keep answering with
the old synonyms.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from app.services.nlq.catalog.loader import Catalog, get_catalog

logger = logging.getLogger(__name__)

COLLECTION = "nlq_catalog"


@dataclass(frozen=True, slots=True)
class CatalogDoc:
    """One retrievable catalog entry."""

    id: str
    kind: str  # metric | dimension | table | enum_value
    text: str  # what gets embedded
    payload: dict[str, Any]


def build_documents(catalog: Catalog | None = None) -> list[CatalogDoc]:
    """Flatten the catalog into embeddable documents.

    The embedded text leads with the business language a user would actually type and only
    then mentions the underlying table. Leading with `gnlnac_lndisb_amt` would pull the
    vector towards a token no question will ever contain.
    """
    cat = catalog or get_catalog()
    docs: list[CatalogDoc] = []

    for metric in cat.metrics.values():
        terms = ", ".join(metric.synonyms)
        docs.append(
            CatalogDoc(
                id=f"metric:{metric.id}",
                kind="metric",
                text=(
                    f"{metric.label}. {metric.description or metric.formula} "
                    f"Also called: {terms}. Measured in {metric.unit}."
                ).strip(),
                payload={
                    "entry_id": metric.id,
                    "label": metric.label,
                    "unit": metric.unit,
                    "grain": metric.grain,
                    "base_table": metric.base_table,
                    "requires_signoff": metric.requires_signoff,
                },
            )
        )

    for dim in cat.dimensions.values():
        terms = ", ".join(dim.synonyms)
        docs.append(
            CatalogDoc(
                id=f"dimension:{dim.id}",
                kind="dimension",
                text=(
                    f"{dim.label}. {dim.description} Group or filter by {terms}."
                ).strip(),
                payload={
                    "entry_id": dim.id,
                    "label": dim.label,
                    "type": dim.type,
                    "table": dim.table,
                },
            )
        )

    for table in cat.tables.values():
        terms = ", ".join(table.synonyms)
        docs.append(
            CatalogDoc(
                id=f"table:{table.id}",
                kind="table",
                text=f"{table.label}. {table.description} Also called: {terms}.".strip(),
                payload={
                    "entry_id": table.id,
                    "table": table.table,
                    "grain": table.grain,
                    "contains_pii": table.contains_pii,
                },
            )
        )

    # Enum values are indexed individually so "Aluva" or "tractor loans" can find its code
    # without the whole enum block having to win on similarity.
    for block in cat.enums.values():
        for value in block.values.values():
            terms = ", ".join(value.synonyms)
            docs.append(
                CatalogDoc(
                    id=f"enum:{block.dimension}:{value.code}",
                    kind="enum_value",
                    text=f"{value.label} ({block.dimension}). {value.note} {terms}".strip(),
                    payload={
                        "entry_id": value.code,
                        "dimension": block.dimension,
                        "label": value.label,
                    },
                )
            )

    return docs


def collection_name(catalog: Catalog | None = None) -> str:
    cat = catalog or get_catalog()
    return f"{COLLECTION}_{cat.version}"


def index(catalog: Catalog | None = None, *, batch_size: int = 64) -> dict[str, Any]:
    """Embed and upsert every catalog document. Idempotent per catalog version."""
    from genesis_core.rag import embed_batch, ensure_collection, get_qdrant
    from qdrant_client.models import PointStruct

    cat = catalog or get_catalog()
    docs = build_documents(cat)
    name = collection_name(cat)
    ensure_collection(name)
    client = get_qdrant()

    written = 0
    for start in range(0, len(docs), batch_size):
        batch = docs[start : start + batch_size]
        vectors = embed_batch([d.text for d in batch])
        client.upsert(
            collection_name=name,
            points=[
                PointStruct(
                    id=abs(hash(doc.id)) % (2**63),
                    vector=vector,
                    payload={"doc_id": doc.id, "kind": doc.kind, "text": doc.text, **doc.payload},
                )
                for doc, vector in zip(batch, vectors)
            ],
        )
        written += len(batch)

    logger.info("Indexed %d catalog documents into %s", written, name)
    return {"collection": name, "documents": written, "catalog_version": cat.version}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    result = index()
    print(f"Indexed {result['documents']} documents into {result['collection']}")


if __name__ == "__main__":
    main()
