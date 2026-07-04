"""Direct RAG engine — no framework.

Five explicit steps you can read and debug:

    load (pypdf) -> chunk -> embed (bge-m3) -> store/search (Qdrant) -> generate (Groq)

Usage
-----
    from genesis_core import rag
    rag.ingest_folder("macro_intel", "./data")            # offline
    answer, sources = rag.ask("macro_intel", "Summarise ...")  # in a request
"""
from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path

from .config import settings


# --------------------------------------------------------------------------
# Embeddings (bge-m3, loaded lazily)
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embed_model)


@lru_cache(maxsize=512)
def embed_text(text: str) -> list[float]:
    # Cached: multi-collection retrieval reuses the same query strings many times.
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

    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def ensure_collection(name: str) -> None:
    """Create the collection only if missing (never recreate — won't wipe existing data)."""
    from qdrant_client.models import Distance, VectorParams

    client = get_qdrant()
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=settings.vector_size, distance=Distance.COSINE),
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
    """Split text into ~chunk_words windows with `overlap` words carried over."""
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
        segments: list[tuple[int | None, str]] = []

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
    hits = client.query_points(
        collection_name=collection,
        query=embed_text(query),
        limit=top_k,
        with_payload=True,
    ).points
    def clean_source(payload: dict):
        # Older module ingests used document_name/source_file keys — some hold
        # full local paths from the original scrape machine; keep the filename.
        src = payload.get("source") or payload.get("document_name") or payload.get("source_file")
        if src:
            src = str(src).replace("\\", "/").rsplit("/", 1)[-1]
        return src

    return [
        {
            "text": h.payload.get("text", ""),
            "source": clean_source(h.payload),
            "page": h.payload.get("page") or h.payload.get("page_number"),
            "score": h.score,
        }
        for h in hits
    ]


def search_multi(
    collection: str,
    queries: list[str],
    top_k: int = 4,
    min_score: float = 0.45,
    max_chunks: int = 12,
) -> list[dict]:
    """Run several focused queries against one collection, dedupe, keep the best.

    Retrieval quality note: embedding an instruction prompt ("You are the Chief
    Intelligence Officer... write HEADLINE...") matches boilerplate pages, not
    data. Callers pass short *data-seeking* queries here and keep the
    instructions for generate().
    """
    seen: set[int] = set()
    merged: list[dict] = []
    for query in queries:
        for hit in search(collection, query, top_k):
            key = hash(hit["text"][:300])
            if key in seen or hit["score"] < min_score:
                continue
            seen.add(key)
            merged.append(hit)
    merged.sort(key=lambda h: h["score"], reverse=True)
    return merged[:max_chunks]


# --------------------------------------------------------------------------
# Generation (Groq) — with secondary-key failover
# --------------------------------------------------------------------------
_PRIMARY_COOLDOWN = 60.0  # seconds to route via the secondary key after pressure
_key_state = {"primary_blocked_until": 0.0}


@lru_cache(maxsize=4)
def _groq_client(api_key: str):
    from groq import Groq

    return Groq(api_key=api_key)


def _api_keys() -> list[str]:
    return [k for k in (settings.groq_api_key, settings.groq_api_key_secondary) if k]


def _note_rate_headers(headers) -> None:
    """Fail over proactively: once >=75% of the primary key's per-minute request
    or token budget is consumed, route the next minute of calls to the secondary."""
    import time

    for kind in ("requests", "tokens"):
        try:
            remaining = float(headers.get(f"x-ratelimit-remaining-{kind}"))
            limit = float(headers.get(f"x-ratelimit-limit-{kind}"))
        except (TypeError, ValueError):
            continue
        if limit > 0 and remaining / limit <= 0.25:
            _key_state["primary_blocked_until"] = time.time() + _PRIMARY_COOLDOWN
            return


def _chat(messages: list[dict], temperature: float) -> str:
    import time

    keys = _api_keys()
    if not keys:
        raise RuntimeError("GROQ_API_KEY is not configured")

    ordered = list(keys)
    if len(keys) > 1 and time.time() < _key_state["primary_blocked_until"]:
        ordered = keys[1:] + keys[:1]

    last_error: Exception | None = None
    for key in ordered:
        try:
            raw = _groq_client(key).chat.completions.with_raw_response.create(
                model=settings.groq_model,
                temperature=temperature,
                messages=messages,
            )
            if key == keys[0]:
                _note_rate_headers(raw.headers)
            return raw.parse().choices[0].message.content.strip()
        except Exception as exc:  # 429 / transient failure -> try the next key
            last_error = exc
            if key == keys[0]:
                # Daily-quota exhaustion (TPD) won't clear in a minute — back off longer.
                daily = "per day" in str(exc).lower() or "tpd" in str(exc).lower()
                cooldown = 900.0 if daily else _PRIMARY_COOLDOWN
                _key_state["primary_blocked_until"] = time.time() + cooldown
    raise last_error  # type: ignore[misc]


DEFAULT_SYSTEM = (
    "You are the senior intelligence analyst of the Moneypal Genesis Console, briefing "
    "the leadership of GICC — a Karnataka co-operative bank with assets under Rs 500 "
    "crore that lends to MSMEs. Your briefs inform lending decisions: who to lend to, "
    "how much, what could go wrong, and what opportunities exist.\n"
    "Rules:\n"
    "- Use ONLY the provided CONTEXT. Never invent figures, schemes, or citations.\n"
    "- Cite every figure inline as (document, p.X) using the source names given; if a "
    "source has no page number, cite just (document) — never write 'page None'.\n"
    "- If the context lacks a requested figure, say 'not available in indexed sources' "
    "in one short clause and move on — never pad or speculate around a missing number.\n"
    "- Ignore administrative noise in the context (official-language policy, HR, "
    "ceremonies, committee logistics) — it is never brief-worthy.\n"
    "- Write tight, confident executive prose in short paragraphs. No filler, no "
    "restating the question, no 'as mentioned in the report'."
)


def generate(
    prompt: str,
    context_chunks: list[dict],
    system: str = DEFAULT_SYSTEM,
    temperature: float = 0.3,
) -> str:
    """Generate an answer grounded in retrieved context chunks."""

    def label(c: dict) -> str:
        page = c.get("page")
        # Markdown/web sources have no pages — a "page None" citation is noise.
        if page in (None, "", "None"):
            return f"[Source: {c.get('source')}]"
        return f"[Source: {c.get('source')}, p.{page}]"

    context = "\n\n".join(f"{label(c)}\n{c.get('text', '')}" for c in context_chunks)
    user = f"CONTEXT:\n{context}\n\n---\n\nTASK:\n{prompt}"
    return _chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature,
    )


def ask(
    collection: str,
    prompt: str,
    top_k: int = 5,
    system: str = DEFAULT_SYSTEM,
    queries: list[str] | None = None,
) -> tuple[str, list[dict]]:
    """Retrieve + generate in one call. Returns (answer, source_chunks).

    Pass `queries` (short data-seeking phrases) so retrieval matches data pages
    instead of the instruction prompt itself.
    """
    chunks = search_multi(collection, queries) if queries else search(collection, prompt, top_k)
    answer = generate(prompt, chunks, system)
    return answer, chunks
