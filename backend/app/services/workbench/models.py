"""Shared Workbench access to the repository's single configured LLM client."""

from __future__ import annotations

from app.services.nlq.llm import get_llm_client
from app.services.nlq.llm.client import OpenAICompatibleClient

def client() -> OpenAICompatibleClient:
    """Return the repository's sole configured model client."""
    return get_llm_client()
