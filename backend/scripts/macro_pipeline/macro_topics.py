"""Macro-economic topic catalog — what the pipeline classifies every chunk into.

Each topic declares the keyword/synonym set used to *classify* content and the
unit patterns tied to its stats. This is the rule-based core of the structured
macro extraction; the actual regex figure extraction lives in structured.py.
"""
from __future__ import annotations

import re
from functools import lru_cache


class Topic:
    __slots__ = ("id", "label", "keywords", "units", "figure_labels")

    def __init__(self, id: str, label: str, keywords: list[str], units: list[str], figure_labels: list[str]):
        self.id = id
        self.label = label
        self.keywords = [k.lower() for k in keywords]
        # Units/patterns whose number belongs to this topic (checked in structured.py).
        self.units = [u.lower() for u in units]
        # Human labels used to annotate extracted figures belonging to this topic.
        self.figure_labels = figure_labels


# Topics cover the macro intelligence brief: Economic Survey, MSME trends, GDP,
# inflation, employment, credit growth, Karnataka economy, interest rates,
# marketplaces, plus agriculture/industry/services and government initiatives.
TOPICS: list[Topic] = [
    Topic(
        id="economic_survey",
        label="Economic Survey / Union Budget",
        keywords=[
            "economic survey", "economic survey of india", "union budget", "budget speech",
            "budget document", "fiscal deficit", "revenue expenditure", "capital expenditure",
            "capex", "finance minister", "budget allocation", "glance", "fiscal",
        ],
        units=["% of gdp", "% gdp", "crore", "lakh crore"],
        figure_labels=["Budget/Fiscal figure"],
    ),
    Topic(
        id="gdp_growth",
        label="GDP / Output growth",
        keywords=[
            "gdp", "gross domestic product", "real gdp", "nominal gdp", "growth rate",
            "economic growth", "output growth", "economy grew", "gdp growth", "gdp expansion",
            "gross value added", "gva", "economic activity", "growth momentum",
        ],
        units=["%", "pp", "bps"],
        figure_labels=["U/GDP growth"],
    ),
    Topic(
        id="inflation_cpi",
        label="Inflation / Price level",
        keywords=[
            "inflation", "consumer price index", "cpi", "wholesale price index", "wpi",
            "core inflation", "inflation rate", "price level", "retail inflation",
            "food inflation", "producer prices", "inflationary", "price stability",
        ],
        units=["%", "pp", "bps"],
        figure_labels=["U/Inflation"],
    ),
    Topic(
        id="employment",
        label="Employment / Labour",
        keywords=[
            "employment", "unemployment", "unemployment rate", "labour force", "workforce",
            "jobs", "job creation", "formal employment", "plfs", "labour force participation",
            "worker", "workers", "informal workers", "gig economy", "manpower",
        ],
        units=["%", "mn", "million", "lakh"],
        figure_labels=["Employment figure"],
    ),
    Topic(
        id="msme_trends",
        label="MSME / SME trends",
        keywords=[
            "msme", "micro small medium", "sme", "udyam", "msme sector", "small business",
            "enterprise", "msme credit", "msme lending", "msme pulse", "micro enterprise",
            "small industry", "mid-size", "startup",
        ],
        units=["%", "crore", "lakh crore", "mn", "lakh"],
        figure_labels=["MSME figure"],
    ),
    Topic(
        id="credit_growth",
        label="Credit & Banking",
        keywords=[
            "credit growth", "bank credit", "loan growth", "credit offtake", "non-food credit",
            "deposit growth", "advances", "credit outstanding", "lending", "disbursement",
            "npa", "non-performing", "asset quality", "capital adequacy", "provision",
            "financial inclusion", "bank lending", "credit gap",
        ],
        units=["%", "crore", "lakh crore", "pp"],
        figure_labels=["U/Credit figure"],
    ),
    Topic(
        id="karnataka_economy",
        label="Karnataka economy",
        keywords=[
            "karnataka", "bengaluru", "bangalore", "state gsdp", "gsdp", "state economy",
            "karnataka economic", "karnataka budget", "state domestic product",
            "karnataka msme", "co operative", "cooperative bank", "gicc",
        ],
        units=["%", "crore", "lakh crore"],
        figure_labels=["Karnataka figure"],
    ),
    Topic(
        id="interest_rates",
        label="Interest rates & monetary policy",
        keywords=[
            "repo rate", "reverse repo", "policy rate", "policy repo", "interest rate",
            "rate cut", "rate hike", "monetary policy", "reserve bank", "rbi", "mclr",
            "marginal cost of lending", "base rate", "lending rate", "deposit rate",
            "bond yield", "g-sec", "government security", "yield", "risk premium",
            "cost of funds", "borrowing rate", "interest",
        ],
        units=["%", "bps", "basis points", "pp"],
        figure_labels=["Interest/Policy rate"],
    ),
    Topic(
        id="marketplaces",
        label="Markets & capital markets",
        keywords=[
            "stock market", "sensex", "nifty", "capital market", "market cap",
            "commodity", "commodity prices", "gold price", "crude", "petroleum",
            "wheat", "rice", "prices", "marketplace", "exchange", "equity", "fpi", "fii",
            "mutual fund", "money market", "treasury", "foreign exchange", "forex",
            "rupee", "dollar", "gold",
        ],
        units=["%", "crop", "per kg", "inr", "$", "usd", "bps"],
        figure_labels=["Market figure"],
    ),
    Topic(
        id="government_initiatives",
        label="Government initiatives & schemes",
        keywords=[
            "scheme", "initiative", "mission", "programme", "program", "policy",
            "make in india", "production linked incentive", "pli", "national mission",
            "self reliance", "atmanirbhar", "digital india", "infrastructure",
            "statistics india", "sample survey", "ministry",
        ],
        units=["%", "crore", "lakh crore"],
        figure_labels=["Scheme/Initiative figure"],
    ),
    Topic(
        id="sectors",
        label="Sectors — agriculture, industry, services",
        keywords=[
            "agriculture", "agricultural", "farm", "crop", "monsoon", "industry",
            "industrial", "manufacturing", "factory", "services sector", "sector",
            "mining", "construction", "trade", "hospitality", "tourism",
        ],
        units=["%", "crore", "pp"],
        figure_labels=["Sector figure"],
    ),
]

TOPIC_BY_ID: dict[str, Topic] = {t.id: t for t in TOPICS}


@lru_cache(maxsize=1)
def _keyword_patterns() -> list[tuple[str, tuple[tuple[re.Pattern, int], ...]]]:
    """Compile each topic's keywords into whole-word patterns, once.

    Substring matching is wrong here and quietly so: short acronyms hide inside ordinary
    English words — "sme" in "as-sme-nt", "rbi" in "fo-rbi-d", "gva" in "Bhagva" — and
    every such hit misfiles a chunk under a topic it has nothing to do with. Whole-word
    matching costs one compile and removes the entire class.
    """
    compiled: list[tuple[str, tuple[tuple[re.Pattern, int], ...]]] = []
    for topic in TOPICS:
        patterns = tuple(
            # Phrase keywords (with spaces) are more discriminative than single words.
            (re.compile(rf"\b{re.escape(keyword)}\b"), 4 if " " in keyword else 1)
            for keyword in topic.keywords
        )
        compiled.append((topic.id, patterns))
    return compiled


def classify_topics(text: str) -> list[str]:
    """Return the topic ids whose keywords appear in ``text``, strongest first."""
    # Punctuation becomes space so "MSME-credit" still matches "msme"; runs of space are
    # collapsed so multi-word keywords match across line breaks and column padding.
    lower = " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())
    scores: dict[str, int] = {}
    for topic_id, patterns in _keyword_patterns():
        score = sum(weight for pattern, weight in patterns if pattern.search(lower))
        if score:
            scores[topic_id] = score
    # The 'sectors' topic uses very generic words like 'industry'; keep it but demote.
    if "sectors" in scores:
        scores["sectors"] = max(0, scores["sectors"] - 3)
    return [tid for tid, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]


def topic_label(topic_id: str) -> str:
    return TOPIC_BY_ID.get(topic_id, Topic(topic_id, topic_id, [], [], [])).label