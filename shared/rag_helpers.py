"""Direct RAG helpers shared by all three modules.

No framework. The whole pipeline is five explicit steps you can read and debug:

    load (pypdf)  ->  chunk  ->  embed (bge-m3)  ->  store/search (Qdrant)  ->  generate (Groq)

Import these functions. Do NOT rewrite embedding/search/generation logic per module.

Typical usage
-------------
Ingestion (run once, offline):
    import rag_helpers as rag
    rag.ingest_folder("macro_intel", "./data")

Serving (inside a FastAPI route):
    answer, sources = rag.ask("macro_intel", "Summarise India's GDP outlook for MSME lenders")
"""
from __future__ import annotations

import os
import uuid
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

QDRANT_HOST = os.getenv("QDRANT_HOST", "192.168.1.183")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
VECTOR_SIZE = 1024  # bge-m3 embedding dimension


# --------------------------------------------------------------------------
# Embeddings (bge-m3, loaded lazily so importing this module stays cheap)
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL)


def embed_text(text: str) -> list[float]:
    return get_embedder().encode(text, normalize_embeddings=True).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    return get_embedder().encode(
        texts, normalize_embeddings=True, show_progress_bar=True
    ).tolist()


# --------------------------------------------------------------------------
# Qdrant
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_qdrant():
    from qdrant_client import QdrantClient

    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def ensure_collection(name: str) -> None:
    """Create the collection only if missing.

    Uses create_collection (never recreate_collection) so an existing collection
    from another project on the shared instance is never wiped.
    """
    from qdrant_client.models import Distance, VectorParams

    client = get_qdrant()
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )


# --------------------------------------------------------------------------
# Loading & chunking
# --------------------------------------------------------------------------
def load_pdf(path: str) -> list[tuple[int, str]]:
    """Return [(page_number, text), ...] for pages that have extractable text."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    out: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            out.append((i, text))
    return out


def load_text_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, chunk_words: int = 500, overlap: int = 50) -> list[str]:
    """Split text into ~chunk_words windows with `overlap` words of context carry-over."""
    words = text.split()
    if not words:
        return []
    step = max(1, chunk_words - overlap)
    chunks: list[str] = []
    for start in range(0, len(words), step):
        window = words[start : start + chunk_words]
        if window:
            chunks.append(" ".join(window))
        if start + chunk_words >= len(words):
            break
    return chunks


# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------
def ingest_files(
    collection: str,
    paths: list[str],
    chunk_words: int = 500,
    overlap: int = 50,
    extra_payload: dict | None = None,
) -> int:
    """Load, chunk, embed and upsert the given files into `collection`."""
    from qdrant_client.models import PointStruct

    ensure_collection(collection)
    client = get_qdrant()
    total = 0

    for path in paths:
        p = Path(path)
        segments: list[tuple[int | None, str]] = []  # (page, chunk_text)

        if p.suffix.lower() == ".pdf":
            for page_no, page_text in load_pdf(str(p)):
                for ch in chunk_text(page_text, chunk_words, overlap):
                    segments.append((page_no, ch))
        else:
            for ch in chunk_text(load_text_file(str(p)), chunk_words, overlap):
                segments.append((None, ch))

        if not segments:
            print(f"  [warn] no extractable text in {p.name} (scanned PDF?) — skipped")
            continue

        vectors = embed_batch([s[1] for s in segments])
        points = []
        for (page_no, ch), vec in zip(segments, vectors):
            payload = {"text": ch, "source": p.name, "page": page_no}
            if extra_payload:
                payload.update(extra_payload)
            points.append(PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload))

        client.upsert(collection_name=collection, points=points)
        total += len(points)
        print(f"  {p.name}: {len(points)} chunks")

    print(f"Ingested {total} chunks into '{collection}'")
    return total


def ingest_folder(collection: str, folder: str, **kwargs) -> int:
    """Ingest every .pdf and .txt found directly in `folder`."""
    fp = Path(folder)
    files = [str(x) for x in sorted([*fp.glob("*.pdf"), *fp.glob("*.txt")])]
    if not files:
        print(f"[warn] no .pdf/.txt files in {folder}")
        return 0
    return ingest_files(collection, files, **kwargs)


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------
def search(collection: str, query: str, top_k: int = 5) -> list[dict]:
    """Return the top_k most similar chunks with their source metadata."""
    client = get_qdrant()
    hits = client.search(
        collection_name=collection,
        query_vector=embed_text(query),
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "text": h.payload.get("text", ""),
            "source": h.payload.get("source"),
            "page": h.payload.get("page"),
            "score": h.score,
        }
        for h in hits
    ]


# --------------------------------------------------------------------------
# Generation (Groq)
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_groq():
    from groq import Groq

    return Groq(api_key=os.environ["GROQ_API_KEY"])


DEFAULT_SYSTEM = (
    "You are an intelligence analyst for the Moneypal Genesis Console, briefing the "
    "leadership of GICC — a Karnataka co-operative bank / NBFC with assets under "
    "Rs 500 crore. Write concise, decisive executive summaries suitable for directors. "
    "Ground every figure in the provided context. Clearly separate sourced fact from "
    "your own interpretation. Never invent data or citations."
)


def generate(
    prompt: str,
    context_chunks: list[dict],
    system: str = DEFAULT_SYSTEM,
    temperature: float = 0.3,
) -> str:
    """Generate an answer from a prompt grounded in retrieved context chunks."""
    context = "\n\n".join(
        f"[Source: {c.get('source')}, page {c.get('page')}]\n{c.get('text', '')}"
        for c in context_chunks
    )
    user = f"CONTEXT:\n{context}\n\n---\n\nTASK:\n{prompt}"
    resp = get_groq().chat.completions.create(
        model=GROQ_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


def ask(
    collection: str,
    prompt: str,
    top_k: int = 5,
    system: str = DEFAULT_SYSTEM,
) -> tuple[str, list[dict]]:
    """Retrieve + generate in one call. Returns (answer, source_chunks)."""
    chunks = search(collection, prompt, top_k)
    answer = generate(prompt, chunks, system)
    return answer, chunks
