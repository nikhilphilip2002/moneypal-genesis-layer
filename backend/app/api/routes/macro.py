"""Macro-economic intelligence endpoints (Team A) — thin handlers.

Briefs are LLM-generated, so each is served from the SQLite brief cache;
pass ?refresh=1 to force regeneration.
"""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from genesis_core import IntelligenceResponse

from app.services import brief_cache, macro

router = APIRouter(prefix="/macro", tags=["macro"])

_BRIEFING_CACHE_KEY = f"{brief_cache.CACHE_VERSION}:macro:briefing"


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/snapshot", response_model=IntelligenceResponse)
def snapshot(refresh: bool = False):
    return brief_cache.cached("macro:snapshot", macro.snapshot, refresh)


@router.get("/karnataka", response_model=IntelligenceResponse)
def karnataka(refresh: bool = False):
    return brief_cache.cached("macro:karnataka", macro.karnataka, refresh)


@router.get("/msme", response_model=IntelligenceResponse)
def msme(refresh: bool = False):
    return brief_cache.cached("macro:msme", macro.msme, refresh)


@router.get("/briefing", response_model=IntelligenceResponse)
def briefing(refresh: bool = False):
    return brief_cache.cached("macro:briefing", macro.briefing, refresh)


@router.get("/briefing/stream")
def briefing_stream(refresh: bool = False):
    """Server-sent stream of the executive brief.

    Emits `token` events as the LLM generates, then a final `done` event carrying
    the full IntelligenceResponse (which is also written to the brief cache). A
    fresh cache hit is returned immediately as a single `done` event, so the
    client can use this endpoint uniformly.
    """

    def gen():
        if not refresh:
            hit = brief_cache.get(_BRIEFING_CACHE_KEY)
            if hit is not None:
                yield _sse("done", hit)
                return
        try:
            sources, tokens = macro.briefing_stream()
            parts: list[str] = []
            for token in tokens:
                if not token:
                    continue
                parts.append(token)
                yield _sse("token", {"t": token})
            summary = "".join(parts).strip()
            if not summary:
                yield _sse("error", {"message": "No content was generated."})
                return
            payload = brief_cache.put(_BRIEFING_CACHE_KEY, macro.briefing_response(summary, sources))
            yield _sse("done", payload)
        except Exception as exc:  # surface generation/rate-limit failures to the client
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
