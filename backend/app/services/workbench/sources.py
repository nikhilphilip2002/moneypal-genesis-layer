"""Declarative source metadata used for authorization and the Workbench UI.

The native tool registry supplies model-facing capability descriptions. This catalog names
the underlying evidence sources, role visibility, sensitivity, and display examples; it does
not choose behavior from question text.
"""

from __future__ import annotations

from dataclasses import dataclass
from app.core.config import settings


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    label: str
    describes: str
    sensitive: bool
    """True when answering pulls private loan-book data — governs whether a synthesis over
    it may ever leave the deployment's trusted network."""
    roles: frozenset[str] | None = None  # None = every role
    example_intents: tuple[str, ...] = ()

    def visible_to(self, role: str) -> bool:
        return self.roles is None or role in self.roles


# Source availability is entirely policy-driven; adding metadata here does not add a tool.
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
