from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

from pipeline_common import BASE_DIR, DEFAULT_CONFIG_DIR, DEFAULT_CONFIG_PATH, DEFAULT_STRUCTURED_ROOT, Institution, load_institutions


load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")

QDRANT_HOST = os.getenv("QDRANT_HOST", "192.168.1.183")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
VECTOR_DISTANCE = models.Distance.COSINE

def configured_institutions() -> list[Institution]:
    if DEFAULT_CONFIG_DIR.exists():
        return load_institutions(DEFAULT_CONFIG_DIR)
    return load_institutions(DEFAULT_CONFIG_PATH)


def collection_by_slug() -> dict[str, str]:
    return {institution.slug: institution.collection or f"comp_{institution.slug}" for institution in configured_institutions()}


COLLECTION_BY_SLUG = collection_by_slug()

APPLICABILITY_BY_CATEGORY = {
    "state_financial_corporation": "Karnataka MSME and industrial finance competitive intelligence",
    "cooperative_apex_bank": "Karnataka cooperative banking and agriculture/MSME finance benchmark",
    "nbfc_msme_lender": "MSME lending, small-business credit, and NBFC product benchmarking",
    "cooperative_bank": "Cooperative banking competitive intelligence",
    "district_central_cooperative_bank": "District cooperative banking, agriculture, MSME, and local credit intelligence",
    "industrial_cooperative_bank": "Industrial cooperative banking and local business finance intelligence",
    "urban_cooperative_bank": "Urban cooperative banking, retail, MSME, and local credit intelligence",
    "msme_ecosystem_benchmark": "MSME ecosystem benchmark for products, policy language, and development finance",
}

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", flags=re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    text: str
    section: str
    chunk_index: int


_model: SentenceTransformer | None = None


def get_client() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, check_compatibility=False)


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def vector_size() -> int:
    model = get_model()
    if hasattr(model, "get_embedding_dimension"):
        return int(model.get_embedding_dimension())
    return int(model.get_sentence_embedding_dimension())


def structured_file_for(institution: Institution, structured_root: Path) -> Path:
    primary = structured_root / f"{institution.slug}.md"
    if primary.exists() or not institution.legacy_slug:
        return primary
    return structured_root / f"{institution.legacy_slug}.md"


def document_metadata(institution: Institution) -> dict:
    category = institution.category
    return {
        "id": institution.slug,
        "display_name": institution.name,
        "category": category,
        "institution_url": institution.start_url,
        "source_doc": f"{institution.slug}.md",
        "qdrant_collection": institution.collection or f"comp_{institution.slug}",
        "applicability": APPLICABILITY_BY_CATEGORY.get(category, "Competitive intelligence for financial services benchmarking"),
        "effective_date": None,
        "priority": "high" if institution.slug in {"kinara_capital", "sidbi"} else "medium",
        "description": institution.description,
    }


def document_registry(slugs: Iterable[str] | None = None) -> list[dict]:
    return [document_metadata(institution) for institution in load_selected_institutions(slugs)]


def load_selected_institutions(slugs: Iterable[str] | None = None) -> list[Institution]:
    institutions = configured_institutions()
    wanted = {slug for slug in slugs or []}
    if not wanted:
        return institutions
    return [institution for institution in institutions if institution.slug in wanted]


def split_sections(markdown: str) -> list[tuple[str, str]]:
    matches = list(SECTION_RE.finditer(markdown))
    if not matches:
        return [("Document", markdown.strip())]

    sections = []
    for index, match in enumerate(matches):
        section = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        body = markdown[start:end].strip()
        if body:
            sections.append((section, body))
    return sections


def chunk_text(text: str, chunk_chars: int = 1800, overlap_chars: int = 250) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= chunk_chars:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        if end < len(text):
            paragraph_break = text.rfind("\n\n", start, end)
            if paragraph_break > start + 400:
                end = paragraph_break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap_chars)
    return chunks


def chunks_from_markdown(markdown: str) -> list[Chunk]:
    chunks = []
    for section, body in split_sections(markdown):
        for text in chunk_text(body):
            chunks.append(Chunk(text=text, section=section, chunk_index=len(chunks)))
    return chunks


def point_id(institution_slug: str, section: str, chunk_index: int, text: str) -> str:
    digest = hashlib.sha1(f"{institution_slug}:{section}:{chunk_index}:{text}".encode("utf-8")).hexdigest()
    return str(uuid.UUID(digest[:32]))


def ensure_collection(client: QdrantClient, collection_name: str, size: int) -> str:
    if client.collection_exists(collection_name):
        return "exists"

    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=size, distance=VECTOR_DISTANCE),
    )
    return "created"


def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [vector.tolist() for vector in vectors]


def ingest_institution(
    institution: Institution,
    client: QdrantClient,
    structured_root: Path = DEFAULT_STRUCTURED_ROOT,
    batch_size: int = 32,
) -> dict:
    collection_name = institution.collection or f"comp_{institution.slug}"
    source_path = structured_file_for(institution, structured_root)

    if not source_path.exists():
        return {
            "institution": institution.name,
            "slug": institution.slug,
            "collection": collection_name,
            "status": "missing_file",
            "source_file": str(source_path),
            "points_upserted": 0,
        }

    markdown = source_path.read_text(encoding="utf-8")
    chunks = chunks_from_markdown(markdown)
    collection_status = ensure_collection(client, collection_name, vector_size())

    total = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        vectors = embed_texts([chunk.text for chunk in batch])
        points = []

        for chunk, vector in zip(batch, vectors):
            metadata = document_metadata(institution)
            points.append(
                models.PointStruct(
                    id=point_id(institution.slug, chunk.section, chunk.chunk_index, chunk.text),
                    vector=vector,
                    payload={
                        **metadata,
                        "team": "competitive_intelligence",
                        "institution": institution.name,
                        "institution_slug": institution.slug,
                        "section": chunk.section,
                        "chunk_index": chunk.chunk_index,
                        "text": chunk.text,
                    },
                )
            )

        client.upsert(collection_name=collection_name, points=points, wait=True)
        total += len(points)

    return {
        "institution": institution.name,
        "slug": institution.slug,
        "collection": collection_name,
        "collection_status": collection_status,
        "source_file": str(source_path),
        "chunks_found": len(chunks),
        "points_upserted": total,
        "status": "ok",
    }


def ingest_all(slugs: Iterable[str] | None = None) -> dict:
    client = get_client()
    institutions = load_selected_institutions(slugs)
    results = [ingest_institution(institution, client) for institution in institutions]
    return {
        "qdrant_host": QDRANT_HOST,
        "qdrant_port": QDRANT_PORT,
        "embedding_model": EMBEDDING_MODEL,
        "institutions_processed": len(results),
        "total_points_upserted": sum(item.get("points_upserted", 0) for item in results),
        "results": results,
    }


def collection_counts() -> list[dict]:
    client = get_client()
    counts = []
    for institution in configured_institutions():
        slug = institution.slug
        collection = institution.collection or f"comp_{slug}"
        if not client.collection_exists(collection):
            counts.append({"slug": slug, "collection": collection, "exists": False, "points_count": 0})
            continue
        count = client.count(collection_name=collection, exact=True).count
        counts.append({"slug": slug, "collection": collection, "exists": True, "points_count": count})
    return counts
