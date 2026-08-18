"""Macro Intelligence ingestion pipeline.

Weekly refresh of the macro Qdrant collection:

    collect -> fingerprint -> extract -> structure -> embed -> upsert -> purge stale

Embeddings, chunking and the Qdrant client come from ``genesis_core.rag`` so the
points this writes are byte-compatible with what ``app.services.macro`` reads.
Configuration is entirely environment-driven via ``app.core.config.settings``.
"""
