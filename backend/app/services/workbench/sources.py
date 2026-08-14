"""The source catalog — what the orchestrator can route to, described declaratively.

This is the workbench analogue of the NLQ metric catalog. The router never sees a list of
questions; it sees a list of *sources* and a plain-language description of what each one
holds. Adding a source, or refining its `describes` string, generalises routing to new
phrasings automatically — the same reason the NLQ planner routes from metric descriptions
rather than a lookup table.

`example_intents` are illustrative only. They exist to anchor the router's sense of each
source's scope, not to be matched literally, and the router is told exactly that.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    label: str
    describes: str
    sensitive: bool
    """True when answering pulls private loan-book data — governs whether a synthesis over
    it may ever leave the machine (see models.for_step)."""
    roles: frozenset[str] | None = None  # None = every role
    example_intents: tuple[str, ...] = ()

    def visible_to(self, role: str) -> bool:
        return self.roles is None or role in self.roles


# Phase 1 ships db + macro. competitive, regulatory and schema land in Phase 2 by adding
# entries here — no router or graph change required.
SOURCES: dict[str, Source] = {
    "db": Source(
        id="db",
        label="Loan book",
        sensitive=True,
        # Loan-book analytics mirror who may reach the /ask (NLQ) route: the two GICC
        # business roles and platform admin. gicc_policy works with regulatory text, not
        # the portfolio, so in the workbench it sees only the public macro source.
        roles=frozenset({"admin", "gicc_admin", "gicc_director"}),
        describes=(
            "The bank's own lending warehouse: disbursement and sanctions, repayments and "
            "repayment history, outstanding balances, delinquency and DPD, collections and "
            "collection efficiency, PAR and NPA ratios, the general ledger — sliced by "
            "borrower, branch, product, scheme, asset class and time. Any question about *our* "
            "numbers, portfolio, transaction records, or performance."
        ),
        example_intents=(
            "disbursement by branch last quarter",
            "what is our PAR 30 right now",
            "collection efficiency by product this year",
        ),
    ),
    "macro": Source(
        id="macro",
        label="Macro & economy",
        sensitive=False,
        describes=(
            "Published macroeconomic and sector intelligence: India and Karnataka growth, "
            "inflation, RBI policy and rates, bank credit conditions, MSME sector trends "
            "and credit gaps. External context, never the bank's own figures."
        ),
        example_intents=(
            "what is the RBI policy rate stance",
            "how is MSME credit growth trending",
            "Karnataka MSME lending opportunity",
        ),
    ),
    "competitive": Source(
        id="competitive",
        label="Competitive",
        sensitive=False,
        # Mirrors /competitive access: the two GICC business/policy roles and platform
        # admin. gicc_director's console is the portfolio, not the competitor set.
        roles=frozenset({"admin", "gicc_admin", "gicc_policy"}),
        describes=(
            "The competitive landscape for Karnataka MSME lending: rival lenders and their "
            "positioning, loan products and rates, contested borrower segments and white "
            "space. External market structure, not the bank's own book."
        ),
        example_intents=(
            "who competes for Karnataka MSME borrowers",
            "how do rival lenders price MSME loans",
            "where is the white space in MSME lending",
        ),
    ),
    "regulatory": Source(
        id="regulatory",
        label="Regulatory",
        sensitive=False,
        roles=frozenset({"admin", "gicc_admin", "gicc_policy"}),
        describes=(
            "RBI and co-operative-banking regulation that applies to the bank: circulars, "
            "prudential norms, priority-sector and MSME rules, DNBS reporting obligations, "
            "and what recent changes require."
        ),
        example_intents=(
            "what does the latest RBI MSME circular require",
            "priority sector lending norms for co-operative banks",
            "DNBS-02 reporting obligations",
        ),
    ),
    "knowledge": Source(
        id="knowledge",
        label="Banking concepts",
        sensitive=False,
        describes=(
            "Stable educational explanations of lending and banking concepts: what a term "
            "means, how a metric is calculated, its unit, and how nearby concepts differ. "
            "Use for descriptive questions that do not ask for the bank's records, a current "
            "external fact, regulation, forecast or recommendation."
        ),
        example_intents=(
            "what does interest rate mean",
            "explain the difference between sanctioned and disbursed amount",
            "how is PAR 30 calculated",
        ),
    ),
    "schema": Source(
        id="schema",
        label="Schema",
        sensitive=True,
        # The schema describes the loan-book warehouse, so it follows the loan book's
        # access, not the public sources'.
        roles=frozenset({"admin", "gicc_admin", "gicc_director"}),
        describes=(
            "The structure and ER diagrams of the loan-book database itself: table definitions, "
            "relationships, and join keys. Answers 'how is the data organised' or 'show table structures', "
            "never individual transaction records or figures."
        ),
        example_intents=(
            "show the schema for loan accounts and repayments",
            "how do customers link to loan accounts",
            "what tables hold disbursement data",
        ),
    ),
}

ROUTE_VALUES = ("dispatch", "refuse")


def visible_sources(role: str) -> list[Source]:
    return [s for s in SOURCES.values() if s.visible_to(role)]


def route_schema(role: str) -> dict[str, Any]:
    """Grammar-JSON schema for the router call.

    `sources` is constrained to the ids this role may see, so — exactly like the NLQ
    planner constrained to catalog metrics — the model physically cannot route to a source
    that does not exist or that the user is not allowed to reach.
    """
    ids = [s.id for s in visible_sources(role)]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "route": {"type": "string", "enum": list(ROUTE_VALUES)},
            "sources": {
                "type": "array",
                "items": {"type": "string", "enum": ids},
                "minItems": 0,
                "maxItems": len(ids),
            },
            "intent": {"type": "string"},
            "reason": {"type": "string"},
            "message": {"type": "string"},
        },
        "required": ["route"],
    }


def router_system_prompt(role: str) -> str:
    """Fixed, cacheable prefix describing every visible source."""
    lines = [
        "You are the router for a bank intelligence workbench. You decide which knowledge "
        "source(s) a question should be answered from. You never answer the question "
        "yourself and never state a figure — downstream engines do that.",
        "",
        "SOURCES (id | what it holds):",
    ]
    for source in visible_sources(role):
        lines.append(f"- {source.id} | {source.describes}")
        if source.example_intents:
            examples = "; ".join(source.example_intents)
            lines.append(f"    e.g. {examples}")
    lines += [
        "",
        "The examples are illustrative, not a list to match literally. Route by meaning.",
        "",
        "RULES",
        "- Pick every source needed. A question comparing our book to the market needs "
        "both `db` and `macro`; most questions need exactly one.",
        "- A stable definition or explanation goes to `knowledge`. A request for our values, "
        "records, rates, counts or breakdowns goes to `db`, even if it uses the same term.",
        '- route="dispatch" with the chosen `sources` and a one-line `intent` restating '
        "the question, whenever any source can contribute.",
        '- route="refuse" only when no source applies at all (small talk, or a request to '
        "modify or delete data). Read-only lists and exports are allowed. Give a short "
        "`reason` and `message`. Do not refuse merely "
        "because a question is hard — dispatch it and let the source handle the detail.",
        "- Never invent a source id. Use only the ids listed above.",
    ]
    return "\n".join(lines)


ROUTER_FEW_SHOTS: list[tuple[str, str]] = [
    (
        "top 25 borrowers",
        '{"route":"dispatch","sources":["db"],'
        '"intent":"top 25 borrowers by current principal outstanding"}',
    ),
    (
        "What was our disbursement by branch last quarter?",
        '{"route":"dispatch","sources":["db"],"intent":"disbursement by branch last quarter"}',
    ),
    (
        "How many loans did we sanction each month in FY26?",
        '{"route":"dispatch","sources":["db"],"intent":"monthly sanctioned loan counts for FY26"}',
    ),
    (
        "What is the RBI repo rate stance right now?",
        '{"route":"dispatch","sources":["macro"],"intent":"current RBI policy rate stance"}',
    ),
    (
        "What does an interest rate mean on a loan?",
        '{"route":"dispatch","sources":["knowledge"],'
        '"intent":"explain what a loan interest rate means"}',
    ),
    (
        "What interest rates are present in our loan book?",
        '{"route":"dispatch","sources":["db"],'
        '"intent":"list distinct interest rates in the loan book"}',
    ),
    (
        "How does our MSME book compare with the wider MSME credit market?",
        '{"route":"dispatch","sources":["db","macro"],"intent":"our MSME portfolio versus '
        'MSME sector credit trends"}',
    ),
    (
        "Delete the loan records for branch 4",
        '{"route":"refuse","reason":"unsafe","message":"I can read and analyse the book, '
        'but I cannot modify or delete data."}',
    ),
]
