from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "institutions.json"
DEFAULT_CONFIG_DIR = BASE_DIR / "institutions"
DEFAULT_RAW_ROOT = BASE_DIR / "data"
DEFAULT_STRUCTURED_ROOT = BASE_DIR / "output_structured"

SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp", ".webp",
    ".css", ".js", ".pdf", ".zip", ".rar", ".doc", ".docx",
    ".xls", ".xlsx", ".ppt", ".pptx", ".ico", ".xml",
)


@dataclass(frozen=True)
class Institution:
    name: str
    start_url: str
    slug: str
    category: str = "financial_institution"
    collection: str | None = None
    legacy_slug: str | None = None
    description: str = ""
    max_pages: int | None = None


def slugify(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def _institution_from_row(row: dict) -> Institution:
    name = row["name"].strip()
    start_url = row["start_url"].strip()
    slug = row.get("id") or row.get("slug") or slugify(name)
    slug = slugify(slug)
    collection = row.get("collection") or row.get("qdrant_collection") or f"comp_{slug}"

    return Institution(
        name=name,
        start_url=start_url,
        slug=slug,
        category=row.get("category", "financial_institution"),
        collection=collection,
        legacy_slug=slugify(row["legacy_slug"]) if row.get("legacy_slug") else None,
        description=row.get("description", ""),
        max_pages=row.get("max_pages"),
    )


def load_institutions(config_path: Path | None = None) -> list[Institution]:
    config_path = config_path or DEFAULT_CONFIG_DIR

    if config_path.is_dir():
        institutions = []
        for path in sorted(config_path.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            institutions.append(_institution_from_row(payload))
        return institutions

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    rows = payload.get("institutions", payload)
    return [_institution_from_row(row) for row in rows]


def select_institutions(institutions: list[Institution], only: list[str]) -> list[Institution]:
    if not only:
        return institutions

    wanted = {slugify(item) for item in only}
    selected = [inst for inst in institutions if inst.slug in wanted]
    found = {inst.slug for inst in selected}
    missing = sorted(wanted - found)

    if missing:
        raise ValueError(f"Unknown institution slug(s): {', '.join(missing)}")

    return selected


def normalize_url(url: str) -> str:
    return url.split("#", 1)[0].split("?", 1)[0].rstrip("/") or url


def same_domain(url: str, start_url: str) -> bool:
    parsed = urlparse(url)
    start = urlparse(start_url)
    return parsed.netloc.lower().removeprefix("www.") == start.netloc.lower().removeprefix("www.")


def safe_filename(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    filename = "index" if not path else path.replace("/", "_")
    filename = filename.replace(".html", "").replace(".aspx", "")
    filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
    filename = filename[:150].strip("._") or "index"
    return f"{filename}.md"


def raw_folder(raw_root: Path, institution: Institution) -> Path:
    return raw_root / institution.slug
