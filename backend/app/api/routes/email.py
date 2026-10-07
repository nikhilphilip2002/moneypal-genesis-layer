"""Mailbox attachment + health endpoints.

Answers are produced by the main console's /workbench/ask, which owns routing, consent and
prose. What remains here is the part the browser needs directly and the console cannot
inline: streaming an original attachment, and a health probe. Both are authenticated with
the same identity check the Workbench uses — an attachment is real correspondence, so it is
never served to an anonymous caller.

Retrieval is read-only and lives in a Qdrant collection owned by the email ingestion
service, so nothing here writes to the mailbox index. A degraded store returns a
partial result rather than failing the page.
"""

import re

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.routes.auth import identity_from_authorization
from app.services import email_intel
from app.services.workbench.nodes import run_email

def _require_auth(authorization: str | None = Header(default=None)) -> str:
    """Reject anonymous callers. An attachment is real correspondence, not a public asset.

    ``identity_from_authorization`` resolves a missing or unknown token to "anonymous"
    rather than raising, so the check is explicit here. The console authenticates its
    attachment fetches with the same bearer token it uses for everything else.
    """
    username, _role = identity_from_authorization(authorization)
    if username == "anonymous":
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username


# Every route on this router requires a signed-in caller.
router = APIRouter(prefix="/email", tags=["email"], dependencies=[Depends(_require_auth)])

# Openers that carry no retrieval intent. Answering these from the mailbox produced a
# confident "no excerpt matches" paragraph with a wall of unrelated citations, which reads
# as broken. They are matched as whole phrases so "hi, what documents are needed?" still
# takes the normal cited path.
_SMALL_TALK = frozenset(
    {
        "hi", "hii", "hiii", "hey", "hello", "yo", "sup", "heya",
        "hiya", "hi there", "hey there", "hello there",
        "good morning", "good afternoon", "good evening", "good night",
        "morning", "afternoon", "evening",
        "how are you", "how r u", "how are u", "hows it going", "how is it going",
        "whats up", "what is up", "wassup", "whatsup", "sup?",
        "thanks", "thank you", "thx", "ok", "okay", "cool", "nice", "bye", "goodbye",
    }
)


def _is_small_talk(question: str) -> bool:
    """True for greetings and pleasantries that should not trigger a mailbox search.

    Apostrophes are dropped rather than spaced out so contractions survive ("what's up"
    must not become "what s up"), and every other punctuation mark is treated as a
    separator so "Hello." and "hi!!" still match.
    """
    cleaned = question.lower().replace("'", "").replace("\u2019", "")
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned in _SMALL_TALK


@router.get("/status")
def status():
    """Collection health — point count, vector size and the embedding model in use.

    The embedding model matters operationally: a mismatch between the configured model and
    the model that wrote the collection produces a dimension error on every search.
    """
    return email_intel.stats()


@router.get("/search")
def search(q: str, top_k: int = 8):
    """Return the best-matching mailbox passages with their message metadata."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="q is required")
    stats = email_intel.stats()
    if not stats.get("available"):
        raise HTTPException(status_code=503, detail=stats.get("error", "mailbox index unavailable"))
    return {
        "query": q,
        "collection": stats.get("collection"),
        "hits": email_intel.search(q, top_k=top_k),
    }


@router.get("/attachment")
def attachment(path: str, download: int = 0):
    """Stream one original mail attachment from the ingestion service's file store.

    The path comes from a Qdrant payload, so it is untrusted: :mod:`email_files` confines it
    to ``EMAIL_FILES_DIR`` and this route only ever serves what survives that check. Anything
    else is a 404 rather than a 403, so a malformed payload cannot be used to probe the
    filesystem.
    """
    from fastapi.responses import FileResponse

    from app.services import email_files

    resolved = email_files.resolve(path)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Attachment not available")

    media_type = email_files.content_type(resolved.name)
    disposition = "attachment" if download else "inline"
    return FileResponse(
        resolved,
        media_type=media_type,
        # Quoted so a filename containing a space or a quote cannot break the header.
        headers={"Content-Disposition": f'{disposition}; filename="{resolved.name}"'},
    )


@router.get("/recent")
def recent(q: str = "recent loan requests and required document requests"):
    """Run the mailbox source through the same node the Workbench uses."""
    import asyncio

    return asyncio.run(run_email(q)).as_dict()


@router.post("/ask")
def ask(payload: dict):
    """Answer one question against the mailbox and return a cited card.

    Retrieval is always performed; the narrative is added on top when an answer model is
    reachable. A provider outage therefore costs the prose, not the evidence.
    """
    import asyncio

    from app.services import email_answer, email_files

    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    # Greetings and small talk: answer directly, with the same response shape so the
    # console has no special case to render. Empty sources and passages mean the
    # citation cards are simply absent, which is the point.
    if _is_small_talk(question):
        return {
            "question": question,
            "model": None,
            "answer_model": email_answer.model_name() if email_answer.available() else None,
            "answer_provider": None,
            "providers": email_answer.snapshot() if email_answer.available() else [],
            "collection": None,
            "answer": "Hello! Ask me about the mailbox — loan requests, required "
                      "documents or leave approvals.",
            "answer_error": None,
            "summary": "",
            "passages": [],
            "sources": [],
        }

    top_k = payload.get("top_k") or 8
    try:
        top_k = max(1, min(25, int(top_k)))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="top_k must be an integer")

    stats = email_intel.stats()
    if not stats.get("available"):
        raise HTTPException(status_code=503, detail=stats.get("error", "mailbox index unavailable"))

    hits = email_intel.search(question, top_k=top_k)
    passages = [
        {
            "text": hit.get("text"),
            "subject": hit.get("subject"),
            "sender": hit.get("sender"),
            "date": hit.get("received_at"),
            "filename": hit.get("filename"),
            "score": hit.get("score"),
        }
        for hit in hits
    ]

    seen: set[tuple[str, str]] = set()
    sources: list[dict] = []
    # Body text and attachment lists are per-message lookups, not per-hit work: a single
    # message often contributes several chunks, and asking Qdrant for the same body once
    # per chunk would multiply the queries for no new information.
    body_cache: dict[str, str] = {}

    for hit in hits:
        key = (hit.get("email_id") or "", hit.get("document") or "")
        if key in seen:
            continue
        seen.add(key)

        email_id = hit.get("email_id") or ""
        if email_id not in body_cache:
            body_cache[email_id] = email_intel.email_body(email_id)

        sources.append({
            "document": hit.get("document"),
            "subject": hit.get("subject"),
            "sender": hit.get("sender"),
            "date": hit.get("received_at"),
            "filename": hit.get("filename"),
            "score": hit.get("score"),
            "body": body_cache[email_id],
            "chunk_text": hit.get("text"),
            "attachment": email_files.describe(
                hit.get("file_path") or "", hit.get("filename")
            ),
        })

    narrative, answer_error = email_answer.answer(question, passages)
    served_by = (
        email_answer.served_by() if narrative and email_answer.available() else None
    )

    return {
        "question": question,
        "model": stats.get("embedding_model"),
        "answer_model": email_answer.model_name() if email_answer.available() else None,
        "answer_provider": served_by,
        "providers": email_answer.snapshot() if email_answer.available() else [],
        "collection": stats.get("collection"),
        "answer": narrative,
        "answer_error": answer_error,
        "summary": (
            f"Retrieved {len(hits)} passage{'' if len(hits) == 1 else 's'} "
            f"from {len(sources)} mailbox message{'' if len(sources) == 1 else 's'}."
            if hits
            else "No mailbox message matched this question."
        ),
        "passages": passages,
        "sources": sources,
    }
