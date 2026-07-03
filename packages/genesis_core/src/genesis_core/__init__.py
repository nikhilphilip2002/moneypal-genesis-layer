"""genesis_core — shared contract, settings and Direct RAG engine.

Imported by every service:

    from genesis_core import rag, make_response, IntelligenceResponse, settings
"""
from . import rag
from .config import settings
from .schema import IntelligenceResponse, SourceRef, make_response

__all__ = [
    "rag",
    "settings",
    "IntelligenceResponse",
    "SourceRef",
    "make_response",
]
