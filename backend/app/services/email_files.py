"""Original mail attachments — safe resolution and preview metadata.

The ingestion service writes the real binaries (PDF, image, DOCX) next to its Qdrant
collection and serves them on its own ``/files`` mount, which lives on the ingestion host
and is therefore unreachable from anyone opening the Genesis console on another machine.
This module lets Genesis stream the same bytes through its own origin, so a citation can
open a preview without the browser ever leaving the app.

Every path here arrives from a Qdrant payload, which means it is untrusted input. The
resolver confines it to ``EMAIL_FILES_DIR``: absolute paths, drive letters, UNC prefixes
and ``..`` segments are all rejected, and the resolved path is re-checked against the root
so a symlink cannot be used to step outside it.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Browsers render these inline. Everything else is offered as a download, because sending
# an unknown binary to an <iframe> or <img> achieves nothing but a broken box.
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
}
PDF_TYPES = {".pdf": "application/pdf"}

# Kinds the console knows how to render. "text" is shown inline, "image" and "pdf" are
# embedded, and anything else falls back to a download link.
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
PDF_EXT = {".pdf"}
TEXT_EXT = {".txt", ".md", ".csv", ".tsv", ".json", ".log", ".xml", ".yml", ".yaml", ".eml"}


def files_root() -> Path:
    return Path(settings.email_files_dir).resolve()


def content_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in IMAGE_TYPES:
        return IMAGE_TYPES[suffix]
    if suffix in PDF_TYPES:
        return PDF_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def kind(filename: str) -> str:
    """How the console should present this file: image, pdf, text or binary."""
    suffix = Path(filename).suffix.lower()
    if suffix in IMAGE_EXT:
        return "image"
    if suffix in PDF_EXT:
        return "pdf"
    if suffix in TEXT_EXT:
        return "text"
    return "binary"


def resolve(relative_path: str) -> Path | None:
    """Return the on-disk path for a payload-supplied relative path, or None if unsafe.

    None covers every rejection reason: a traversal attempt, a path outside the root, a
    missing file, or a directory. Callers treat None as "no preview available" rather than
    surfacing a 403, so a malformed payload cannot turn into an error page.
    """
    if not relative_path or not relative_path.strip():
        return None

    candidate = relative_path.strip().replace("\\", "/")

    # Absolute paths, drive letters and UNC prefixes are all attempts to leave the root.
    if candidate.startswith("/") or candidate.startswith("//") or ":" in candidate:
        return None
    if any(part == ".." for part in candidate.split("/")):
        return None

    root = files_root()
    if not root.is_dir():
        logger.warning("attachment root missing: %s", root)
        return None

    try:
        target = (root / candidate).resolve()
    except (OSError, RuntimeError):
        return None

    # Re-check after resolution: this is what catches a symlink pointing outside the root.
    if not target.is_relative_to(root):
        return None
    if not target.is_file():
        return None
    return target


def describe(relative_path: str, filename: str | None = None) -> dict[str, Any] | None:
    """Preview metadata for one attachment, or None when the file cannot be served."""
    if not relative_path:
        return None
    resolved = resolve(relative_path)
    if resolved is None:
        return None
    name = filename or resolved.name
    suffix = resolved.suffix.lower()
    return {
        "filename": name,
        # Relative so the console keeps working if EMAIL_FILES_DIR moves; the route
        # re-resolves it and re-applies the same confinement check.
        "path": relative_path,
        "url": f"/email/attachment?path={_quote(relative_path)}",
        "download_url": f"/email/attachment?path={_quote(relative_path)}&download=1",
        "content_type": content_type(name),
        "kind": kind(name),
        "size": resolved.stat().st_size,
        "inline": suffix in IMAGE_EXT or suffix in PDF_EXT or suffix in TEXT_EXT,
    }


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
