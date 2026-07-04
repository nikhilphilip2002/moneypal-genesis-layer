from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

from pipeline_common import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_CONFIG_DIR,
    DEFAULT_RAW_ROOT,
    DEFAULT_STRUCTURED_ROOT,
    Institution,
    load_institutions,
    raw_folder,
    select_institutions,
)


SECTION_NAMES = [
    "Institution profile",
    "Products",
    "MSME focus",
    "Public financial highlights",
    "Geographic presence",
    "AI-generated SWOT",
    "Strategic observations",
    "Links to source documents",
]

NOISE_PATTERNS = (
    "skip to content", "powered by", "copyright", "all rights reserved",
    "quick links", "facebook", "twitter", "instagram", "youtube",
    "privacy policy", "terms and conditions", "sitemap", "sharearticle",
)

CATEGORY_KEYWORDS = {
    "Institution profile": [
        "about", "profile", "history", "established", "registered", "incorporated",
        "head office", "chairman", "managing director", "mission", "vision", "objective",
    ],
    "Products": [
        "loan", "advance", "deposit", "saving", "current account", "fixed deposit",
        "recurring deposit", "scheme", "working capital", "term loan", "cash credit",
        "overdraft", "gold loan", "jewel loan", "business loan", "home loan",
    ],
    "MSME focus": [
        "msme", "micro", "small", "medium", "enterprise", "entrepreneur",
        "business loan", "small business", "industry", "industrial", "machinery",
        "working capital", "udyam", "sme", "mse",
    ],
    "Public financial highlights": [
        "financial", "annual report", "balance sheet", "profit", "loss", "deposit",
        "advance", "npa", "capital", "reserve", "asset", "liability", "crore",
        "turnover", "performance", "statistics",
    ],
    "Geographic presence": [
        "branch", "branches", "office", "head office", "regional", "district",
        "address", "location", "network", "ifsc", "contact",
    ],
}

CATEGORY_FILENAME_HINTS = {
    "Institution profile": ["about", "profile", "history", "objective", "management"],
    "Products": ["loan", "deposit", "scheme", "products", "services"],
    "MSME focus": ["msme", "business", "industrial", "enterprise", "working_capital"],
    "Public financial highlights": ["financial", "annual", "report", "statistics", "performance"],
    "Geographic presence": ["branch", "branches", "contact", "location", "office"],
}


def clean_line(line: str) -> str:
    try:
        line = line.encode("cp1252").decode("utf-8")
    except UnicodeError:
        pass

    line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
    line = re.sub(r"\[\]\([^)]+\)", "", line)
    line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
    line = re.sub(r"<[^>]+>", "", line)
    line = re.sub(r"^[#*\-\d\.\s|]+", "", line)
    line = line.replace("**", "")
    return re.sub(r"\s+", " ", line).strip()


def is_noise(line: str) -> bool:
    lower = line.lower()
    if lower.startswith("url:"):
        return True
    if lower.startswith("http://") or lower.startswith("https://"):
        return True
    return len(lower) < 4 or any(pattern in lower for pattern in NOISE_PATTERNS)


def read_docs(source_dir: Path) -> list[dict]:
    docs = []

    if not source_dir.exists():
        return docs

    for path in sorted(source_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        url_match = re.search(r"^URL:\s*(.+)$", text, flags=re.MULTILINE)
        url = url_match.group(1).strip() if url_match else ""
        lines = [clean_line(line) for line in text.splitlines()]
        lines = [line for line in lines if not is_noise(line)]
        docs.append({"path": path, "url": url, "text": "\n".join(lines), "lines": lines})

    return docs


def score_doc(doc: dict, category: str) -> int:
    haystack = f"{doc['path'].name}\n{doc['text']}".lower()
    score = 0

    for keyword in CATEGORY_KEYWORDS[category]:
        score += haystack.count(keyword.lower()) * (4 if " " in keyword else 1)

    filename = doc["path"].name.lower()
    if any(hint in filename for hint in CATEGORY_FILENAME_HINTS.get(category, [])):
        score += 100

    return score


def ranked_docs(docs: list[dict], category: str, limit: int = 8) -> list[dict]:
    scored = sorted(((score_doc(doc, category), doc) for doc in docs), key=lambda item: item[0], reverse=True)
    return [doc for score, doc in scored if score > 0][:limit]


def extract_lines(docs: list[dict], category: str, max_lines: int = 12) -> list[str]:
    selected = []
    seen = set()
    keywords = CATEGORY_KEYWORDS[category]

    for doc in docs:
        for line in doc["lines"]:
            lower = line.lower()
            if not any(keyword.lower() in lower for keyword in keywords):
                continue
            if not 20 <= len(line) <= 260:
                continue
            if lower in seen:
                continue
            selected.append(line)
            seen.add(lower)
            if len(selected) >= max_lines:
                return selected

    return selected


def extract_products(docs: list[dict], max_items: int = 30) -> list[str]:
    selected = []
    seen = set()

    for doc in docs:
        for line in doc["lines"]:
            lower = line.lower()
            if not any(keyword.lower() in lower for keyword in CATEGORY_KEYWORDS["Products"]):
                continue
            if not 5 <= len(line) <= 120:
                continue
            if lower in seen:
                continue
            selected.append(line.strip(" :.-"))
            seen.add(lower)
            if len(selected) >= max_items:
                return selected

    return selected


def extract_links(docs: list[dict], used_docs: list[dict], max_links: int = 30) -> list[str]:
    ordered_docs = used_docs + docs
    links = []
    seen = set()

    for doc in ordered_docs:
        url = doc.get("url", "")
        if not url or url in seen:
            continue
        label = doc["path"].stem.replace("_", " ").replace("-", " ").title()
        links.append(f"- {label}: {url}")
        seen.add(url)
        if len(links) >= max_links:
            break

    return links


def as_bullets(lines: list[str], fallback: str) -> str:
    if not lines:
        return f"- {fallback}"
    return "\n".join(f"- {line}" for line in lines)


def generate_swot(institution: Institution, extracted: dict[str, list[str]]) -> str:
    combined = "\n".join("\n".join(values) for values in extracted.values()).lower()
    has_msme = any(term in combined for term in ["msme", "small business", "enterprise", "udyam", "working capital"])
    has_digital = any(term in combined for term in ["upi", "mobile", "neft", "rtgs", "imps", "atm", "digital"])
    has_rural = any(term in combined for term in ["co-operative", "cooperative", "agriculture", "district", "branch"])

    strengths = [
        "Established official web presence with crawlable institutional information.",
        "Visible product or service information for customer-facing analysis.",
    ]
    if has_msme:
        strengths.append("MSME or small-business relevance appears in the extracted source material.")
    if has_digital:
        strengths.append("Digital/payment channels improve customer access and service convenience.")
    if has_rural:
        strengths.append("Local, branch, co-operative, or rural presence supports relationship-led distribution.")

    weaknesses = [
        "Public information may be fragmented across pages and should be manually validated before high-stakes use.",
        "Financial figures may require annual reports or statutory documents beyond ordinary web pages.",
    ]
    if not has_msme:
        weaknesses.append("MSME positioning is not explicit in the extracted crawl text.")

    opportunities = [
        "Package MSME products with clearer eligibility, documentation, repayment, and application journeys.",
        "Use local presence and digital rails to grow working-capital, equipment, and enterprise finance relationships.",
    ]
    if institution.slug == "sidbi_msme_ecosystem_benchmark":
        opportunities.append("Use this profile as a benchmark for MSME ecosystem language and product taxonomy.")

    threats = [
        "Competition from banks, NBFCs, fintech lenders, and digital-first MSME platforms.",
        "Credit quality and borrower stress can rise with local economic or sector downturns.",
    ]

    return (
        "### Strengths\n"
        + "\n".join(f"- {item}" for item in strengths)
        + "\n\n### Weaknesses\n"
        + "\n".join(f"- {item}" for item in weaknesses)
        + "\n\n### Opportunities\n"
        + "\n".join(f"- {item}" for item in opportunities)
        + "\n\n### Threats\n"
        + "\n".join(f"- {item}" for item in threats)
    )


def strategic_observations(institution: Institution, extracted: dict[str, list[str]]) -> list[str]:
    observations = [
        "This is an automated first-pass extraction from official crawled pages; verify factual claims before publishing.",
        "Prioritize source pages about products, financials, branches, and MSME/business lending during manual review.",
        "Refresh the raw crawl when new annual reports, product pages, or branch lists are published.",
    ]

    if extracted.get("MSME focus"):
        observations.append("MSME-related positioning can be compared across institutions for product-gap analysis.")

    if institution.slug == "sidbi_msme_ecosystem_benchmark":
        observations.append("SIDBI should be treated as the MSME ecosystem benchmark rather than a direct local-bank peer.")

    return observations


def build_profile(institution: Institution, docs: list[dict]) -> str:
    grouped = {category: ranked_docs(docs, category) for category in CATEGORY_KEYWORDS}
    used_docs = []
    extracted = defaultdict(list)

    extracted["Institution profile"] = extract_lines(grouped["Institution profile"], "Institution profile")
    extracted["Products"] = extract_products(grouped["Products"])
    extracted["MSME focus"] = extract_lines(grouped["MSME focus"], "MSME focus")
    extracted["Public financial highlights"] = extract_lines(grouped["Public financial highlights"], "Public financial highlights")
    extracted["Geographic presence"] = extract_lines(grouped["Geographic presence"], "Geographic presence")

    for category_docs in grouped.values():
        used_docs.extend(category_docs)

    links = extract_links(docs, used_docs)

    if not docs:
        return (
            f"# {institution.name}\n\n"
            f"Configured start URL: {institution.start_url}\n\n"
            "## Institution profile\n\n- No raw Markdown files were found for this institution.\n\n"
            "## Products\n\n- No raw Markdown files were found for this institution.\n\n"
            "## MSME focus\n\n- No raw Markdown files were found for this institution.\n\n"
            "## Public financial highlights\n\n- No raw Markdown files were found for this institution.\n\n"
            "## Geographic presence\n\n- No raw Markdown files were found for this institution.\n\n"
            "## AI-generated SWOT\n\n"
            "### Strengths\n- Not generated because no source content was available.\n\n"
            "### Weaknesses\n- No crawlable source content was available for automated analysis.\n\n"
            "### Opportunities\n- Rerun the crawl after confirming the official URL is reachable.\n\n"
            "### Threats\n- Research accuracy is limited until source material is available.\n\n"
            "## Strategic observations\n\n- Add or crawl source documents, then rerun structured extraction.\n\n"
            "## Links to source documents\n\n"
            f"- Configured start URL: {institution.start_url}\n"
        )

    return (
        f"# {institution.name}\n\n"
        f"Configured start URL: {institution.start_url}\n\n"
        "## Institution profile\n\n"
        + as_bullets(extracted["Institution profile"], "Not found in the crawled Markdown.")
        + "\n\n## Products\n\n"
        + as_bullets(extracted["Products"], "Not found in the crawled Markdown.")
        + "\n\n## MSME focus\n\n"
        + as_bullets(extracted["MSME focus"], "No explicit MSME focus found in the crawled Markdown.")
        + "\n\n## Public financial highlights\n\n"
        + as_bullets(extracted["Public financial highlights"], "Not found in the crawled Markdown.")
        + "\n\n## Geographic presence\n\n"
        + as_bullets(extracted["Geographic presence"], "Not found in the crawled Markdown.")
        + "\n\n## AI-generated SWOT\n\n"
        + generate_swot(institution, extracted)
        + "\n\n## Strategic observations\n\n"
        + "\n".join(f"- {item}" for item in strategic_observations(institution, extracted))
        + "\n\n## Links to source documents\n\n"
        + ("\n".join(links) if links else "- No source URLs found in raw Markdown.")
        + "\n"
    )


def extract_institution(institution: Institution, raw_root: Path, structured_root: Path) -> Path:
    source_dir = raw_folder(raw_root, institution)
    docs = read_docs(source_dir)
    profile = build_profile(institution, docs)

    structured_root.mkdir(parents=True, exist_ok=True)
    output_path = structured_root / f"{institution.slug}.md"
    output_path.write_text(profile, encoding="utf-8")
    return output_path


def run(args: argparse.Namespace) -> None:
    config_path = Path(args.config)
    raw_root = Path(args.raw_root)
    structured_root = Path(args.structured_root)
    institutions = select_institutions(load_institutions(config_path), args.only)

    for institution in institutions:
        output_path = extract_institution(institution, raw_root, structured_root)
        print(f"[{institution.slug}] Structured output: {output_path}")

    print("\n==============================")
    print("Structured extraction finished")
    print(f"Institutions processed: {len(institutions)}")
    print(f"Structured output folder: {structured_root.resolve()}")
    print("==============================")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rule-based structured extraction from institution raw Markdown.")
    default_config = DEFAULT_CONFIG_DIR if DEFAULT_CONFIG_DIR.exists() else DEFAULT_CONFIG_PATH
    parser.add_argument("--config", default=str(default_config), help="Path to institutions JSON config or config folder.")
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT), help="Folder containing per-institution raw Markdown.")
    parser.add_argument("--structured-root", default=str(DEFAULT_STRUCTURED_ROOT), help="Folder for structured outputs.")
    parser.add_argument("--only", nargs="*", default=[], help="Optional institution slug(s) to extract.")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
