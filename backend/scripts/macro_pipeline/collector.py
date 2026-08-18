"""Stage 1 — Collector: crawl the macro sources and download PDF / CSV / XLSX / TXT.

A bounded same-domain BFS from each URL in ``sources.txt``. Anything linking to a
download extension is fetched into ``settings.macro_data_dir/<slug>/``.

Politeness matters here — these are government portals we want to keep being able
to read: robots.txt is honoured, requests are spaced by ``MACRO_REQUEST_DELAY_S``,
the User-Agent identifies the crawler honestly, and conditional GETs (ETag /
Last-Modified) mean an unchanged weekly refresh costs a handful of 304s instead of
re-downloading tens of megabytes.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from app.core.config import settings

log = logging.getLogger("macro.collector")

USER_AGENT = "MoneypalGenesisBot/1.0 (macro intelligence ingest; +contact via repo owner)"

# File kinds the collector treats as macro intelligence data.
DOWNLOAD_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls", ".txt"}
SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp", ".webp", ".zip", ".rar",
    ".doc", ".docx", ".ppt", ".pptx", ".xml", ".js", ".css", ".woff", ".woff2",
}
# URL path segments that mark a listing page worth descending into on a big portal.
DISCOVERY_PATH_HINTS = (
    "statistics", "press-release", "publication", "data", "download",
    "reports", "economic-survey", "annual-report", "dashboard", "releases",
)


@dataclass
class DownloadRecord:
    url: str
    path: Path
    sha256: str
    size: int
    content_type: str
    etag: str = ""
    last_modified: str = ""
    unchanged: bool = False   # server answered 304, or bytes matched the previous run


@dataclass
class CollectResult:
    source_slug: str
    source_url: str
    pages_seen: int = 0
    downloaded: list[DownloadRecord] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        """True when the source yielded nothing and errored — used by the purge rail."""
        return bool(self.errors) and not self.downloaded


def load_sources() -> list[dict]:
    """One URL per non-empty line of sources.txt -> source descriptors with slugs."""
    seen: dict[str, int] = {}

    def slug_for(host: str) -> str:
        base = "".join(c if c.isalnum() else "_" for c in host.lower().removeprefix("www."))
        base = base.strip("_") or "source"
        index = seen.get(base, 0) + 1
        seen[base] = index
        return f"{base}_{index}" if index > 1 else base

    sources: list[dict] = []
    for line in settings.macro_sources_file.read_text(encoding="utf-8").splitlines():
        url = line.split("#", 1)[0].strip()
        if not url:
            continue
        host = urllib.parse.urlparse(url).netloc or url
        sources.append({"url": url, "host": host, "slug": slug_for(host)})
    return sources


# --- session / politeness ---------------------------------------------------------
_SESSION: requests.Session | None = None
_ROBOTS: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_last_request_at = 0.0


def get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/pdf,text/csv,*/*",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
    return _SESSION


def _throttle() -> None:
    global _last_request_at
    wait = settings.macro_request_delay_s - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _robots_allows(url: str) -> bool:
    if not settings.macro_respect_robots:
        return True
    parsed = urllib.parse.urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in _ROBOTS:
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        try:
            parser.read()
        except Exception:
            # No reachable robots.txt is not permission to ignore one that appears
            # later, but it must not stall the run either — treat as permissive.
            parser = None
        _ROBOTS[origin] = parser
    parser = _ROBOTS[origin]
    return True if parser is None else parser.can_fetch(USER_AGENT, url)


# --- URL helpers ------------------------------------------------------------------
def _same_domain(url: str, base_url: str) -> bool:
    a = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    b = urllib.parse.urlparse(base_url).netloc.lower().removeprefix("www.")
    return bool(a) and (a == b or a.endswith("." + b) or b.endswith("." + a))


def _suffix(url: str) -> str:
    return Path(urllib.parse.urlparse(url).path.lower()).suffix


def _safe_filename(url: str) -> str:
    """Filesystem-safe name; hash-prefixed when the source name is generic."""
    parsed = urllib.parse.urlparse(url)
    name = re.sub(r"[\\/*?:\"<>|]", "_", Path(urllib.parse.unquote(parsed.path)).name or "")
    name = name.strip(" ._") or "document.txt"
    if Path(name).suffix.lower() not in DOWNLOAD_EXTENSIONS:
        name = f"{Path(name).stem if '.' in name else name}.txt"
    if re.fullmatch(r"(index|report|download|document|news|pub|lr)[.\w]*", name, re.I):
        name = f"{hashlib.sha1(url.encode()).hexdigest()[:10]}__{name}"
    return name


# --- HTTP -------------------------------------------------------------------------
def _fetch(url: str, stream: bool = False, headers: dict | None = None) -> requests.Response:
    _throttle()
    response = get_session().get(
        url,
        timeout=settings.macro_request_timeout_s,
        stream=stream,
        allow_redirects=True,
        headers=headers or {},
    )
    if response.status_code != 304:
        response.raise_for_status()
    return response


def _download(url: str, output_dir: Path, previous: dict | None) -> DownloadRecord:
    """Fetch one file, using a conditional GET when we have validators from last run."""
    conditional: dict[str, str] = {}
    if previous:
        if previous.get("etag"):
            conditional["If-None-Match"] = previous["etag"]
        if previous.get("last_modified"):
            conditional["If-Modified-Since"] = previous["last_modified"]

    response = _fetch(url, stream=True, headers=conditional)
    content_type = response.headers.get("content-type", "").split(";")[0].lower()

    if response.status_code == 304 and previous:
        response.close()
        log.info("[collector] unchanged (304): %s", Path(previous["path"]).name)
        return DownloadRecord(
            url=url,
            path=Path(previous["path"]),
            sha256=previous["sha256"],
            size=previous.get("size", 0),
            content_type=previous.get("content_type", content_type),
            etag=previous.get("etag", ""),
            last_modified=previous.get("last_modified", ""),
            unchanged=True,
        )

    # Some portals answer a direct file URL with a login page or an HTML error.
    if content_type in {"text/html", "application/xhtml+xml"}:
        response.close()
        raise PermissionError(f"expected a file, got HTML (auth wall?): {response.url}")

    declared = int(response.headers.get("content-length") or 0)
    cap = settings.macro_max_download_mb * 1024 * 1024
    if declared > cap:
        response.close()
        raise ValueError(f"exceeds {settings.macro_max_download_mb} MB cap ({declared} bytes)")

    # Stream with a running cap so a chunked response without content-length cannot
    # blow up memory on a mislabelled endpoint.
    buffer = bytearray()
    for block in response.iter_content(chunk_size=1 << 16):
        buffer.extend(block)
        if len(buffer) > cap:
            response.close()
            raise ValueError(f"exceeds {settings.macro_max_download_mb} MB cap while streaming")
    raw = bytes(buffer)

    path = output_dir / _safe_filename(response.url or url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    return DownloadRecord(
        url=response.url or url,
        path=path,
        sha256=digest,
        size=len(raw),
        content_type=content_type,
        etag=response.headers.get("etag", ""),
        last_modified=response.headers.get("last-modified", ""),
        unchanged=bool(previous and previous.get("sha256") == digest),
    )


# --- Crawl ------------------------------------------------------------------------
def _crawl_site(source: dict, seen_urls: set[str], known: dict[str, dict]) -> CollectResult:
    """BFS one source. ``known`` maps download URL -> previous-run state entry."""
    result = CollectResult(source_slug=source["slug"], source_url=source["url"])
    output_dir = settings.macro_data_dir / source["slug"]
    output_dir.mkdir(parents=True, exist_ok=True)

    queue: list[tuple[str, int]] = [(source["url"], 0)]
    pages_seen = 0

    def try_download(target: str) -> None:
        if target in seen_urls or len(result.downloaded) >= settings.macro_max_files_per_site:
            return
        seen_urls.add(target)
        if not _robots_allows(target):
            result.blocked.append(target)
            log.info("[%s] robots.txt disallows %s", source["slug"], target)
            return
        try:
            record = _download(target, output_dir, known.get(target))
            result.downloaded.append(record)
            if not record.unchanged:
                log.info("[%s] downloaded %s (%d bytes)", source["slug"], record.path.name, record.size)
        except PermissionError as exc:
            result.blocked.append(target)
            log.warning("[%s] blocked: %s (%s)", source["slug"], target, exc)
        except Exception as exc:
            result.errors.append(f"{target} -> {type(exc).__name__}: {exc}")
            log.warning("[%s] failed %s: %s", source["slug"], target, exc)

    while queue and pages_seen < settings.macro_max_pages_per_site:
        url, depth = queue.pop(0)
        if url in seen_urls or not _same_domain(url, source["url"]) or _suffix(url) in SKIP_EXTENSIONS:
            continue

        if _suffix(url) in DOWNLOAD_EXTENSIONS:
            pages_seen += 1
            try_download(url)
            continue

        if not _robots_allows(url):
            seen_urls.add(url)
            continue
        try:
            response = _fetch(url)
        except Exception as exc:
            seen_urls.add(url)
            result.errors.append(f"{url} -> {type(exc).__name__}: {exc}")
            log.warning("[%s] page error %s: %s", source["slug"], url, exc)
            continue

        seen_urls.add(url)
        if "text/html" not in response.headers.get("content-type", "").lower():
            continue
        pages_seen += 1

        for anchor in BeautifulSoup(response.text, "lxml").find_all("a", href=True):
            href = anchor["href"].strip()
            if href.startswith(("mailto:", "javascript:", "tel:", "#")):
                continue
            child = urllib.parse.urldefrag(urllib.parse.urljoin(url, href)).url
            if _suffix(child) in DOWNLOAD_EXTENSIONS:
                try_download(child)
            elif depth < settings.macro_max_depth and (
                _is_discovery_page(child) or depth == 0
            ):
                queue.append((child, depth + 1))

    result.pages_seen = pages_seen
    return result


def _is_discovery_page(url: str) -> bool:
    path = urllib.parse.urlparse(url).path.lower()
    return any(hint in path for hint in DISCOVERY_PATH_HINTS)


def collect(known: dict[str, dict] | None = None) -> list[CollectResult]:
    """Crawl every configured source. ``known`` carries last run's HTTP validators."""
    known = known or {}
    seen_urls: set[str] = set()
    results: list[CollectResult] = []
    for source in load_sources():
        log.info("Collecting %s <- %s", source["slug"], source["url"])
        started = time.monotonic()
        try:
            result = _crawl_site(source, seen_urls, known)
        except Exception as exc:
            log.exception("collector failed for %s", source["url"])
            result = CollectResult(source["slug"], source["url"], errors=[str(exc)])
        results.append(result)
        log.info(
            "[%s] %d pages, %d files (%d unchanged), %d blocked, %d errors in %.1fs",
            source["slug"],
            result.pages_seen,
            len(result.downloaded),
            sum(1 for r in result.downloaded if r.unchanged),
            len(result.blocked),
            len(result.errors),
            time.monotonic() - started,
        )
    return results
