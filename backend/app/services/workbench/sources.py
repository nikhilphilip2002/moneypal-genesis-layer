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

from app.core.config import settings


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
        # Open-access rollout policy: every Workbench role, including anonymous sessions,
        # may perform governed read-only record lookups. Authentication/role restrictions
        # can be restored by setting an explicit role set here with PII masking enabled.
        roles=None,
        describes=(
            "The bank's own lending warehouse: disbursement and sanctions, repayments and "
            "repayment history, outstanding balances, delinquency and DPD, collections and "
            "collection efficiency, PAR and NPA ratios, the general ledger — sliced by "
            "borrower, customer ID, loan account, agent code/name, gender, branch, product, "
            "scheme, asset class and time. Any question about *our* numbers, individual records, "
            "repayment events, portfolio, transaction records, or performance. It also "
            "includes the governed general ledger, share capital/equity balances, and "
            "product-code directory."
        ),
        example_intents=(
            "disbursement by branch last quarter",
            "what is our PAR 30 right now",
            "collection efficiency by product this year",
            "repayment history for a named borrower",
            "loan details for customer ID 128",
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
            "regulatory capital and equity requirements, and what recent changes require."
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
    "web": Source(
        id="web",
        label="Live web",
        sensitive=False,
        roles=None,
        describes=(
            "Current public information from the internet, especially newly published "
            "economic releases, government announcements, news, market developments and "
            "facts that require a live lookup. It prioritizes official Indian sources "
            "such as RBI, MoSPI, India Budget, DEA, PIB, Commerce and data.gov.in, then "
            "international primary sources. It must never receive private bank records."
        ),
        example_intents=(
            "search the web for the latest RBI repo-rate announcement",
            "what is the latest published CPI inflation figure",
            "recent Government of India MSME policy announcement",
        ),
    ),
}

ROUTE_VALUES = ("dispatch", "refuse")
EXTERNAL_CONNECTOR_SOURCES = frozenset({"macro", "competitive", "regulatory", "web"})


def visible_sources(
    role: str, allowed_source_ids: tuple[str, ...] | list[str] | set[str] | None = None,
) -> list[Source]:
    allowed = set(allowed_source_ids) if allowed_source_ids is not None else None
    return [
        s for s in SOURCES.values()
        if s.visible_to(role)
        and (allowed is None or s.id in allowed)
        and (
            settings.workbench_external_connectors_enabled
            or s.id not in EXTERNAL_CONNECTOR_SOURCES
        )
        and (s.id != "web" or settings.exa_mcp_enabled)
    ]


def route_schema(
    role: str, allowed_source_ids: tuple[str, ...] | list[str] | set[str] | None = None,
) -> dict[str, Any]:
    """Grammar-JSON schema for the router call.

    `sources` is constrained to the ids this role may see, so — exactly like the NLQ
    planner constrained to catalog metrics — the model physically cannot route to a source
    that does not exist or that the user is not allowed to reach.
    """
    ids = [s.id for s in visible_sources(role, allowed_source_ids)]
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
            "source_intents": {
                "type": "object",
                "additionalProperties": False,
                "properties": {source_id: {"type": "string"} for source_id in ids},
            },
            "reason": {"type": "string"},
            "message": {"type": "string"},
        },
        "required": ["route"],
    }


def router_system_prompt(
    role: str, allowed_source_ids: tuple[str, ...] | list[str] | set[str] | None = None,
) -> str:
    """Fixed, cacheable prefix describing every visible source."""
    compact = {
        "db": "governed bank loan book values, records, metrics and breakdowns",
        "schema": "authorized abstracted loan-book views and relationships",
        "knowledge": "stable governed banking definitions; no current facts",
        "macro": "indexed public macroeconomic and sector evidence",
        "competitive": "indexed peer lender, product and market evidence",
        "regulatory": "indexed RBI and banking-regulation evidence",
        "web": "fresh public internet evidence; never private bank data",
    }
    lines = [
        "Select source ids for a bank intelligence question; do not answer it.",
        "Allowed sources:",
    ]
    for source in visible_sources(role, allowed_source_ids):
        lines.append(f"- {source.id}: {compact[source.id]}")
    lines += [
        "Pick every needed source; comparisons may need db plus one external source.",
        "Use web only for explicit online search or material freshness.",
        "Never send names, account/customer ids, repayment history, or private facts to web.",
        "Use knowledge for definitions and db for our values/records.",
        "Return dispatch with sources/intent (and focused source_intents for hybrids), or "
        "refuse only when no allowed source can contribute. Preserve exact names and filters.",
    ]
    return "\n".join(lines)


ROUTER_FEW_SHOTS: list[tuple[str, str]] = [
    (
        "Show repayment history for borrower Anitha K",
        '{"route":"dispatch","sources":["db"],'
        '"intent":"repayment history for borrower Anitha K"}',
    ),
    (
        "What are the loan amount and date for customer ID 42?",
        '{"route":"dispatch","sources":["db"],'
        '"intent":"loan amount and date for customer ID 42"}',
    ),
    (
        "Search the web for the latest RBI repo rate announcement",
        '{"route":"dispatch","sources":["web"],'
        '"intent":"latest RBI repo rate announcement"}',
    ),
    (
        "Compare our loan growth with the latest RBI bank credit growth",
        '{"route":"dispatch","sources":["db","web"],"intent":"compare loan growth",'
        '"source_intents":{"db":"our loan growth",'
        '"web":"latest published RBI bank credit growth"}}',
    ),
    (
        "Give me details for agent AGNT12",
        '{"route":"dispatch","sources":["db"],'
        '"intent":"governed directory details for agent AGNT12"}',
    ),
    (
        "What branches are there?",
        '{"route":"dispatch","sources":["db"],'
        '"intent":"list the current governed branch directory"}',
    ),
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
        'MSME sector credit trends","source_intents":{"db":"show the size and growth of our MSME '
        'portfolio","macro":"what is the wider Indian MSME credit growth trend"}}',
    ),
    (
        "Delete the loan records for branch 4",
        '{"route":"refuse","reason":"unsafe","message":"I can read and analyse the book, '
        'but I cannot modify or delete data."}',
    ),
]
