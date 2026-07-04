from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler

from pipeline_common import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_CONFIG_DIR,
    DEFAULT_RAW_ROOT,
    SKIP_EXTENSIONS,
    Institution,
    load_institutions,
    normalize_url,
    raw_folder,
    safe_filename,
    same_domain,
    select_institutions,
)


def should_crawl(url: str, start_url: str) -> bool:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return False

    if not same_domain(url, start_url):
        return False

    if parsed.path.lower().endswith(SKIP_EXTENSIONS):
        return False

    return True


async def crawl_institution(
    institution: Institution,
    crawler: AsyncWebCrawler,
    raw_root: Path,
    default_max_pages: int,
) -> int:
    output_dir = raw_folder(raw_root, institution)
    output_dir.mkdir(parents=True, exist_ok=True)

    visited: set[str] = set()
    max_pages = institution.max_pages or default_max_pages

    async def crawl(url: str) -> None:
        url = normalize_url(url)

        if url in visited:
            return

        if len(visited) >= max_pages:
            return

        if not should_crawl(url, institution.start_url):
            return

        visited.add(url)
        print(f"[{institution.slug}] Crawling {len(visited)}/{max_pages}: {url}")

        try:
            result = await crawler.arun(url=url)
        except Exception as exc:
            print(f"[{institution.slug}] ERROR: {url} -> {exc}")
            return

        if not result.success:
            print(f"[{institution.slug}] Failed: {url}")
            return

        title = result.metadata.get("title", "Untitled")
        file_path = output_dir / safe_filename(url)
        file_path.write_text(f"# {title}\n\nURL: {url}\n\n{result.markdown}", encoding="utf-8")
        print(f"[{institution.slug}] Saved: {file_path.name}")

        for link in result.links.get("internal", []):
            href = link.get("href")
            if href:
                await crawl(urljoin(url, href))

    await crawl(institution.start_url)
    print(f"[{institution.slug}] Finished. Pages crawled: {len(visited)}")
    return len(visited)


async def run(args: argparse.Namespace) -> None:
    config_path = Path(args.config)
    raw_root = Path(args.raw_root)
    institutions = select_institutions(load_institutions(config_path), args.only)

    raw_root.mkdir(parents=True, exist_ok=True)

    async with AsyncWebCrawler() as crawler:
        for institution in institutions:
            await crawl_institution(institution, crawler, raw_root, args.max_pages)

    print("\n==============================")
    print("Crawling finished")
    print(f"Institutions processed: {len(institutions)}")
    print(f"Raw output folder: {raw_root.resolve()}")
    print("==============================")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Config-driven multi-institution Crawl4AI crawler.")
    default_config = DEFAULT_CONFIG_DIR if DEFAULT_CONFIG_DIR.exists() else DEFAULT_CONFIG_PATH
    parser.add_argument("--config", default=str(default_config), help="Path to institutions JSON config or config folder.")
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT), help="Folder for per-institution raw Markdown.")
    parser.add_argument("--max-pages", type=int, default=100, help="Default max pages per institution.")
    parser.add_argument("--only", nargs="*", default=[], help="Optional institution slug(s) to crawl.")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
