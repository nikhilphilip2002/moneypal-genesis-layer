"""Question -> the catalog entries the planner needs to see.

Hybrid by design. Vector similarity handles paraphrase ("money we gave out" -> disbursement);
lexical matching handles the short acronyms that dominate this domain — PAR, DPD, NPA, EMI,
LTV embed poorly and match exactly with certainty. Scoring one without the other loses a
different half of the questions.

Two things worth stating plainly:

1. **The planner does not use retrieval for metrics and dimensions.** The full metric and
   dimension list is ~1,400 tokens — well inside the 4k budget — so it is sent whole, every
   time. Retrieval that drops the one metric the user meant is a wrong answer; retrieval
   that saves 1k tokens on a 4k budget buys nothing. `retrieve()` exists for the text-to-SQL
   path, where the ~700 columns genuinely do not fit, and for resolving enum values.

2. **Degradation is deliberate.** If Qdrant is unreachable or the embedding model cannot
   load, retrieval falls back to lexical-only and says so in `RetrievalResult.mode`. A
   slightly worse ranking beats an outage.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.nlq.catalog.index import (
    CatalogDoc,
    build_documents,
    collection_name,
    index as index_catalog,
)
from app.services.nlq.catalog.loader import Catalog, get_catalog

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9]+")

# Weight on the lexical half of the hybrid score. Set high on purpose: an exact synonym hit
# ("PAR 30") is far stronger evidence than cosine proximity in this vocabulary.
LEXICAL_WEIGHT = 1.5
VECTOR_WEIGHT = 1.0

STOPWORDS = {
    "what", "was", "our", "the", "show", "give", "tell", "how", "much", "many", "did",
    "we", "is", "are", "for", "and", "with", "by", "in", "of", "to", "me", "a", "an",
    "this", "that", "last", "each", "per", "which", "have", "has", "do", "does", "on",
}


@dataclass(slots=True)
class Hit:
    doc: CatalogDoc
    score: float
    lexical: float = 0.0
    vector: float = 0.0


@dataclass(slots=True)
class RetrievalResult:
    tables: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    enum_values: list[dict[str, Any]] = field(default_factory=list)
    joins: list[str] = field(default_factory=list)
    mode: str = "hybrid"  # hybrid | lexical
    hits: list[Hit] = field(default_factory=list)


def tokenize(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 2}


def lexical_score(question: str, doc: CatalogDoc, catalog: Catalog) -> float:
    """Exact-ish term overlap, weighted towards curated synonyms.

    A synonym is a deliberate authoring decision; a word appearing in a description is
    incidental. They should not count the same.
    """
    q_lower = question.lower()
    q_tokens = tokenize(question)
    if not q_tokens:
        return 0.0

    synonyms: list[str] = []
    label = ""
    if doc.kind == "metric":
        metric = catalog.metrics[doc.payload["entry_id"]]
        synonyms, label = list(metric.synonyms), metric.label
    elif doc.kind == "dimension":
        dim = catalog.dimensions[doc.payload["entry_id"]]
        synonyms, label = list(dim.synonyms), dim.label
    elif doc.kind == "table":
        table = catalog.tables[doc.payload["entry_id"]]
        synonyms, label = list(table.synonyms), table.label
    elif doc.kind == "column":
        column = catalog.columns[doc.payload["entry_id"]]
        synonyms, label = list(column.synonyms), column.label
    elif doc.kind == "enum_value":
        block = catalog.enums.get(doc.payload["dimension"])
        value = block.values.get(str(doc.payload["entry_id"])) if block else None
        synonyms = list(value.synonyms) if value else []
        label = doc.payload.get("label", "")

    score = 0.0
    for phrase in (*synonyms, label):
        if not phrase:
            continue
        if phrase.lower() in q_lower:
            # Multi-word phrase hits are much stronger evidence than a single token.
            score += 1.0 + 0.5 * (len(phrase.split()) - 1)

    overlap = len(q_tokens & tokenize(doc.text)) / len(q_tokens)
    return score + overlap


def _vector_hits(question: str, catalog: Catalog, limit: int) -> dict[str, float]:
    """Cosine scores by doc id, or {} when the vector stack is unavailable."""
    try:
        from genesis_core.rag import embed_text, get_qdrant
    except Exception as exc:  # noqa: BLE001
        logger.info("NLQ retrieval running lexical-only (embeddings unavailable): %s", exc)
        return {}

    try:
        client = get_qdrant()
        name = collection_name(catalog)
        query = embed_text(question)
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLQ vector preparation failed, falling back to lexical: %s", exc)
        return {}
    try:
        found = client.query_points(
            collection_name=name, query=query, limit=limit, with_payload=True,
        ).points
    except Exception as exc:  # noqa: BLE001 - a ranking aid, never a hard dependency
        # Catalog names are content-addressed, so every catalog edit intentionally points
        # at a new collection. Build that tiny collection on first use rather than leaving
        # deployments in lexical-only mode until somebody remembers a runbook command.
        message = str(exc).lower()
        if "collection" in message and ("doesn't exist" in message or "not found" in message):
            try:
                result = index_catalog(catalog)
                logger.info("Created missing NLQ catalog collection %s", result["collection"])
                found = client.query_points(
                    collection_name=name, query=query, limit=limit, with_payload=True,
                ).points
            except Exception as index_exc:  # noqa: BLE001
                logger.warning(
                    "NLQ catalog auto-index failed, falling back to lexical: %s", index_exc
                )
                return {}
        else:
            logger.warning("NLQ vector retrieval failed, falling back to lexical: %s", exc)
            return {}

    return {p.payload.get("doc_id", ""): float(p.score) for p in found if p.payload}


def retrieve(
    question: str,
    *,
    catalog: Catalog | None = None,
    top_tables: int = 8,
    top_metrics: int = 10,
    top_dimensions: int = 8,
    top_enums: int = 12,
    use_vectors: bool = True,
) -> RetrievalResult:
    """Rank catalog entries for a question."""
    cat = catalog or get_catalog()
    docs = build_documents(cat)

    vectors = _vector_hits(question, cat, limit=60) if use_vectors else {}
    mode = "hybrid" if vectors else "lexical"

    hits: list[Hit] = []
    for doc in docs:
        lexical = lexical_score(question, doc, cat)
        vector = vectors.get(doc.id, 0.0)
        if lexical <= 0 and vector <= 0:
            continue
        hits.append(
            Hit(
                doc=doc,
                score=LEXICAL_WEIGHT * lexical + VECTOR_WEIGHT * vector,
                lexical=lexical,
                vector=vector,
            )
        )
    hits.sort(key=lambda h: h.score, reverse=True)

    def take(kind: str, limit: int) -> list[str]:
        return [h.doc.payload["entry_id"] for h in hits if h.doc.kind == kind][:limit]

    metrics = take("metric", top_metrics)
    dimensions = take("dimension", top_dimensions)
    tables = [h.doc.payload["table"] for h in hits if h.doc.kind == "table"][:top_tables]

    # Exact column language such as "security value" or "IFSC code" is stronger table
    # evidence than a generic overlap with an amount metric. Put those tables first.
    column_tables = [h.doc.payload["table"] for h in hits if h.doc.kind == "column"]
    tables = list(dict.fromkeys([*column_tables, *tables]))[:top_tables]

    # A metric is useless without its own table, so pull those in regardless of whether the
    # table's own description happened to rank.
    for metric_id in metrics:
        base = cat.metrics[metric_id].base_table
        if base not in tables:
            tables.append(base)

    enum_values = [
        {
            "dimension": h.doc.payload["dimension"],
            "code": h.doc.payload["entry_id"],
            "label": h.doc.payload["label"],
        }
        for h in hits
        if h.doc.kind == "enum_value"
    ][:top_enums]

    return RetrievalResult(
        tables=tables,
        metrics=metrics,
        dimensions=dimensions,
        enum_values=enum_values,
        joins=_join_closure(cat, tables),
        mode=mode,
        hits=hits[:25],
    )


def _join_closure(catalog: Catalog, tables: list[str]) -> list[str]:
    """Every declared edge connecting the selected tables.

    Without this the text-to-SQL prompt sees two tables and no way to relate them, which is
    exactly when a model invents a join condition.
    """
    selected = set(tables)
    return [
        join.id
        for join in catalog.joins
        if join.left in selected and join.right in selected
    ]
