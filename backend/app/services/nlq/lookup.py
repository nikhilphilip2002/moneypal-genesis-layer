"""Deterministic customer and account lookups for the Workbench.

These questions are record retrieval, not metrics.  The planner only extracts a small,
closed intent; this module owns the SQL and the displayed fields so a borrower name or
identifier can never turn into an open-ended generated query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from sqlglot import exp

from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.contracts import ChartSpec, ClarifyPlan, LookupPlan
from app.services.nlq.executor import execute_raw
from app.services.nlq.normalization import normalize_apostrophes
from app.services.nlq.pipeline import run_sql
from app.services.nlq.text_to_sql import SqlAttempt, _normalized_borrower_sql
from app.services.nlq.validator import validate


_HISTORY_WORD = r"(?:histor(?:y|ies)|histoy|histry|hisotry|hitory)"
_REPAYMENT_CUE = re.compile(
    rf"\b(?:repayment|payment)\s+{_HISTORY_WORD}\b|"
    r"\b(?:(?:re)?payments|collection\s+history|payment\s+records?)\b",
    re.I,
)
_CUSTOMER_ID = re.compile(
    r"\b(?:customer|borrower|client)\s*(?:id|number|no\.?|#)\s*"
    r"(?:is|was|=|:|-)?\s*(?P<value>[0-9][0-9,]*(?:\.0+)?)\b",
    re.I,
)
_ACCOUNT_ID = re.compile(
    r"\b(?:loan\s+)?account\s*(?:number|no\.?|#)\s*"
    r"(?:is|was|=|:|-)?\s*(?P<value>[a-z0-9][a-z0-9,._/-]*)\b",
    re.I,
)
_NAME_AFTER_HISTORY = re.compile(
    rf"\b(?:repayment|payment)\s+{_HISTORY_WORD}\s+(?:of|for)\s+"
    r"(?P<name>[\w .'-]{2,100})\s*[?!.]*$",
    re.I,
)
_BARE_REPAYMENT_WORD = r"(?:(?:re)?payments|collection\s+history|payment\s+records?)"
_NAME_BEFORE_BARE_REPAYMENT = re.compile(
    r"^(?:(?:what\s+(?:is|are)|show(?:\s+me)?|give\s+me|list)\s+(?:the\s+)?)?"
    rf"(?P<name>[\w .'-]{{2,100}}?)\s*(?:'s)?\s+{_BARE_REPAYMENT_WORD}\s*[?!.]*$",
    re.I,
)
_NAME_AFTER_BARE_REPAYMENT = re.compile(
    rf"\b{_BARE_REPAYMENT_WORD}\s+(?:of|for|by)\s+"
    r"(?P<name>[\w .'-]{2,100})\s*[?!.]*$",
    re.I,
)
_NAME_BEFORE_HISTORY = re.compile(
    r"^(?:what\s+is|show(?:\s+me)?|give\s+me)?\s*"
    r"(?P<name>[\w .'-]{2,100}?)\s*(?:'s\s+)?"
    rf"(?:repayment|payment)\s+{_HISTORY_WORD}\s*[?!.]*$",
    re.I,
)
_ACCOUNT_ID_BARE = re.compile(
    r"\b(?:loan\s+)?account\s*(?:is|was|=|:|-)?\s*(?P<value>\d{6,})\b", re.I,
)
"""«loan account 1000400001520» — the keyword "number" is usually left out. A long digit
run after the word account can only be the account, so no detail cue is needed; a short
one is not accepted, because "account 5" is more likely a count than an identifier."""
_BRANCH_CODE_REF = re.compile(r"\bbranch(?:\s*(?:code|no\.?|number))?\s*\d{1,6}\b", re.I)
_PRODUCT_CODE_BARE = re.compile(r"\bproduct\s+(?P<value>\d{1,6})\b", re.I)
_GENDER_ACCOUNT_SAMPLE = re.compile(
    r"\b(?:male|men)\b.*\b(?:female|women)\b|"
    r"\b(?:female|women)\b.*\b(?:male|men)\b",
    re.I,
)
_LOAN_DETAIL_CUE = re.compile(
    r"\b(?:loan\s+amount|sanction(?:ed)?|disburs(?:ed|e?ment)|loan\s+date|date)\b",
    re.I,
)
_SANCTION_AMOUNT_CUE = re.compile(
    r"\b(?:loan|sanction(?:ed)?)\s+amount\b|\bhow\s+much\s+(?:was\s+)?(?:the\s+)?loan\b",
    re.I,
)
_SANCTION_DATE_CUE = re.compile(r"\b(?:sanction|loan)\s+date\b", re.I)
_DISBURSEMENT_AMOUNT_CUE = re.compile(
    r"\bdisburs(?:ed|e?ment)\s+amount\b|\bamount\s+disburs(?:ed|e?ment)\b",
    re.I,
)
_DISBURSEMENT_DATE_CUE = re.compile(
    r"\b(?:first\s+)?disburs(?:ed|e?ment)\s+date\b|"
    r"\bdate\s+(?:of\s+)?(?:the\s+)?disburs(?:ed|e?ment)\b",
    re.I,
)
_CUSTOMER_DETAIL_CUE = re.compile(
    r"\b(?:details?|profiles?|information|info|infor\w*)\b|"
    r"\b(?:show|give|get|find)\s+(?:me\s+)?(?:the\s+)?(?:customer|borrower|client)\b",
    re.I,
)
_NAMED_LOAN_DETAIL = re.compile(
    r"\b(?:customer|borrower|client)\s+(?!id\b|number\b|no\.?\b|#)"
    r"(?P<name>[\w .'-]{2,100})\s*[?!.]*$",
    re.I,
)
_NAME_AFTER_LOAN_DETAILS = re.compile(
    r"\b(?:loans?(?:\s+accounts?)?|accounts?)\s+"
    r"(?:details?|information|info|records?|profile)\s+(?:of|for)\s+"
    r"(?P<name>[\w .'-]{2,100})\s*[?!.]*$",
    re.I,
)
_NAME_BEFORE_LOAN_DETAILS = re.compile(
    r"^(?:what\s+(?:is|are)|show(?:\s+me)?|give\s+me|get|find)?\s*"
    r"(?P<name>[\w .'-]{2,100}?)\s*(?:'s\s+)?"
    r"(?:loans?(?:\s+accounts?)?|accounts?)\s+"
    r"(?:details?|information|info|records?|profile)\s*[?!.]*$",
    re.I,
)
_NAME_BEFORE_CUSTOMER_DETAILS = re.compile(
    r"^(?:what\s+(?:is|are)|show(?:\s+me)?|give\s+me|get|find)?\s*"
    r"(?P<name>[\w .'-]{2,100}?)\s*(?:'s)?\s+"
    r"(?:customer\s+)?(?:details?|profile|information|info)\s*[?!.]*$",
    re.I,
)
"""The possessive is optional: people type "<name> information" as often as "<name>'s
information". `_is_person_name` is what keeps "customer information" from being read as a
borrower called "customer"."""
_NAME_THEN_REQUEST = re.compile(
    r"^(?P<name>[\w .'-]{2,100}?)\s+(?:please\s+)?"
    r"(?:give|show|get|find|tell|fetch)\s+(?:me\s+)?(?:his|her|their|its|the)?\s*"
    r"(?:customer\s+|loan\s+|account\s+)?"
    r"(?:details?|profile|information|info|records?)\s*[?!.]*$",
    re.I,
)
"""«MAHABOOB PASHA give me his details» — the subject is stated first and the request
follows it, which none of the verb-first patterns can see."""
_NAME_AFTER_CUSTOMER_DETAILS = re.compile(
    r"\b(?:customer|borrower|client)\s+"
    r"(?:details?|profile|information|info)\s+(?:of|for)\s+"
    r"(?P<name>[\w .'-]{2,100})\s*[?!.]*$",
    re.I,
)
_NAME_AFTER_DETAILS = re.compile(
    r"\b(?:details?|profile|information|info|records?)\s+(?:of|for|about)\s+"
    r"(?P<name>[\w .'-]{2,100})\s*[?!.]*$",
    re.I,
)
"""«give me the details of <name>» — the same request as the customer-prefixed form, which
people only bother typing when the system has already misunderstood them once."""
_NAME_IDENTITY = re.compile(
    r"^(?:who\s+is|tell\s+me\s+about|what\s+do\s+(?:we|you)\s+know\s+about)\s+"
    r"(?P<name>[\w .'-]{2,100})\s*[?!.]*$",
    re.I,
)
_NAME_ACCOUNTS = re.compile(
    r"^(?:(?:show|list|give|get|find)\s+(?:me\s+)?)?(?P<name>[\w .'-]{2,100}?)\s*(?:'s)?\s+"
    r"(?:loan\s+)?accounts?\s*[?!.]*$|"
    r"\bhow\s+many\s+loans?\s+(?:does|do|has|have)\s+"
    r"(?P<name2>[\w .'-]{2,100}?)\s+(?:have|got|taken)\s*[?!.]*$",
    re.I,
)
_CUSTOMER_FIELD_CUE = re.compile(
    r"\b(?:address|occupation|profession|agency|home\s+branch)\b", re.I
)
_NAME_BEFORE_CUSTOMER_FIELD = re.compile(
    r"^(?:(?:what\s+is|show(?:\s+me)?|give\s+me|get|find)\s+(?:the\s+)?)?"
    r"(?P<name>[\w .'-]{2,100}?)\s*(?:'s)?\s+"
    r"(?:address|occupation|profession|agency|home\s+branch)\s*[?!.]*$",
    re.I,
)
_BRANCH_DIRECTORY_CUE = re.compile(
    r"\b(?:what|which)\s+(?:are|is)\s+(?:the\s+)?branches\b|"
    r"\bbranches?\s+(?:are|is)\s+there\b|"
    r"\b(?:list|show)\s+(?:me\s+)?(?:all\s+)?branches\b|"
    r"\bavailable\s+branches\b",
    re.I,
)
_AGENT_CODE = re.compile(r"\b(?P<value>(?:agnt|agent)[-_ ]?\d+)\b", re.I)
_AGENT_DETAIL_CUE = re.compile(
    r"\b(?:details?|profiles?|names?|information|info|infor\w*|show|get|give|about|who)\b",
    re.I,
)
_ARTICLE_PREFIX = re.compile(r"^(?:the|a|an)\s+", re.I)
"""«show me the <name> repayment history» — the article belongs to the sentence, not to the
borrower. Left attached it becomes part of the normalised name and matches nobody."""
_AGENT_DIRECTORY_CUE = re.compile(
    r"^(?:(?:list|show|give|get)\s+(?:me\s+)?)?(?:all\s+|the\s+)?agents?"
    r"(?:\s+(?:list|directory))?\s*[?!.]*$|"
    r"^(?:what|which)\s+agents?\s+(?:are|is)\s+there\s*[?!.]*$|"
    r"^(?:show|list|give|get)\s+(?:me\s+)?(?:the\s+)?agent\s+(?:directory|list)"
    r"\s*[?!.]*$",
    re.I,
)
_AGENT_COUNT_CUE = re.compile(
    r"\b(?:(?:how\s+many|number\s+of|count\s+of|total)\s+(?:active\s+)?agents?|"
    r"agents?\s+count)\b",
    re.I,
)
_AGENT_ACCOUNT_CUE = re.compile(
    r"\b(?:loan\s+)?accounts?\s*(?:numbers?|nos?\.?)\b|"
    r"\b(?:show|list|give|get)\b[^?]{0,80}\b(?:loan\s+)?accounts?\b|"
    r"\b(?:loan\s+)?accounts?\s+(?:linked|associated|mapped|tagged|handled|"
    r"under|of|for|with)\b|"
    r"\b(?:linked|associated|mapped|tagged)\s+(?:loan\s+)?accounts?\b",
    re.I,
)
_PRODUCT_CODE = re.compile(
    r"\bproduct\s*(?:code|id|number|no\.?)\s*(?:is|was|=|:|-)?\s*"
    r"(?P<value>[a-z0-9][a-z0-9._/-]*)\b",
    re.I,
)
_PRODUCT_DETAIL_CUE = re.compile(
    r"\b(?:name|details?|information|info|which|what|identify|called)\b",
    re.I,
)
_NAME_BEFORE_LOAN_FIELD = re.compile(
    r"^(?:(?:what\s+is|show(?:\s+me)?|give\s+me|get|find)\s+(?:the\s+)?)?"
    r"(?P<name>[a-z][\w .'-]{1,100}?)\s*(?:'s\s+)?"
    r"(?:loan\s+amount|sanction(?:ed)?\s+amount|sanction\s+date|loan\s+date|"
    r"disburs(?:ed|e?ment)\s+(?:amount|date))\s*[?!.]*$",
    re.I,
)
_NAME_AFTER_LOAN_FIELD = re.compile(
    r"\b(?:loan\s+amount|sanction(?:ed)?\s+amount|sanction\s+date|loan\s+date|"
    r"disburs(?:ed|e?ment)\s+(?:amount|date))\s+(?:of|for)\s+"
    r"(?:(?:customer|borrower|client)\s+)?(?P<name>[a-z][\w .'-]{1,100})\s*[?!.]*$",
    re.I,
)
_BORROWER_NAME_CUE = re.compile(r"\bnames?\b", re.I)
_AGENT_BORROWER_CUE = re.compile(r"\b(?:borrowers?|customers?|clients?)\b", re.I)
_COUNT_CUE = re.compile(r"\b(?:how\s+many|count|number\s+of|total\s+number)\b", re.I)

_NON_NAME_WORDS = frozenset({
    "split", "between", "and", "or", "versus", "vs", "by", "per", "each", "total",
    "count", "sum", "average", "mean", "open", "closed", "active", "inactive", "top",
    "bottom", "highest", "lowest", "most", "least", "overdue", "outstanding", "arrears",
    "disbursed", "disbursement", "sanctioned", "sanction", "list", "show", "compare",
    "trend", "breakdown", "share", "ratio", "growth", "npa", "par", "dpd", "bucket",
    "portfolio", "gold", "microfinance", "msme", "retail", "male", "female", "gender",
    "many", "much", "which", "where", "when", "why",
})
"""One of these anywhere in a captured name means the phrase is a question about the book.
"Show the loan-count split between open and closed accounts" ends in the word the account
patterns anchor on, and without this reads as a borrower named "loan-count split between
open and closed"."""

_NAME_FILLER_WORDS = frozenset({
    "a", "an", "the", "all", "any", "every", "each", "both", "some", "his", "her",
    "their", "its", "my", "our", "this", "that", "these", "those", "please", "me",
})
"""Words that can only be scaffolding at the edge of a captured name."""

_GENERIC_NAME_WORDS = frozenset({
    "a", "an", "the", "this", "that", "his", "her", "their", "its", "my", "our",
    "customer", "customers", "borrower", "borrowers", "client", "clients",
    "agent", "agents", "branch", "branches", "loan", "loans", "account", "accounts",
    "product", "products", "scheme", "schemes", "bank", "book", "portfolio", "record",
    "records", "detail", "details", "profile", "information", "info",
})

_REFINEMENT_FIELD = (
    r"(?:(?:their|the|its|his|her|full|borrower|customer|agent|linked)\s+)*"
    r"(?:names?|phone(?:\s+numbers?)?|mobile(?:\s+numbers?)?|contact(?:\s+numbers?)?|"
    r"email(?:\s+address(?:es)?)?|designations?|branch\s+codes?|"
    r"(?:loan\s+)?account\s+numbers?|customer\s+ids?|"
    r"sanction(?:ed)?\s+amounts?|sanction\s+dates?|loan\s+amounts?|"
    r"disburs(?:ed|e?ment)\s+(?:amounts?|dates?))"
)
_RECORD_REFINEMENT = re.compile(
    r"^(?:(?:ok|and|also|plus|now)\s+)?"
    r"(?:(?:can\s+you\s+)?(?:please\s+)?(?:show|list|give|get|display|add|include)"
    r"\s+(?:me\s+)?)?"
    r"(?:along\s+with|together\s+with|with|and|also|plus|including|include)\s+"
    rf"{_REFINEMENT_FIELD}(?:\s*(?:,|and)\s*{_REFINEMENT_FIELD})*"
    r"(?:\s+(?:as\s+well|too|also|please))?\s*[?!.]*$",
    re.I,
)
"""«along with names» — a refinement that only widens the previous record request.

The connector is required: a bare "sanction date" is a question in its own right and must
be planned as one, while "and the names" cannot be anything but an addition to what was
just asked. Folding still only happens when the previous turn was itself a record lookup,
so no metric question can inherit a selector this way."""


@dataclass(slots=True)
class LookupResult:
    chart: ChartSpec | None = None
    clarification: ClarifyPlan | None = None
    no_match: bool = False


def completions(term: str, kind: str = "all", catalog: Catalog | None = None) -> list[dict]:
    """Return bounded Gold-directory completions for the chat composer."""
    cat = catalog or get_catalog()
    text = " ".join(str(term or "").split()).strip()
    if len(text) < 2 or kind not in {"all", "borrower", "customer", "account", "agent"}:
        return []

    results: list[dict] = []
    if kind in {"all", "borrower", "customer", "account"}:
        normalized = re.sub(r"[^a-z0-9]", "", text.lower()).replace("th", "t")
        normalized = re.sub(r"(.)\1+", r"\1", normalized)
        name_literal = _literal(normalized)
        id_literal = _literal(_plain_identifier(text).lower())
        stored_name = (
            "REGEXP_REPLACE(REGEXP_REPLACE(REPLACE(LOWER(TRIM(customer_name)), "
            "'th', 't'), '[^a-z0-9]', '', 'g'), '(.)\\1+', '\\1', 'g')"
        )
        sql = (
            "SELECT TRIM(REGEXP_REPLACE(customer_name, '\\s+', ' ', 'g')) AS borrower_name, "
            "customer_id::text AS customer_id, MIN(loan_account_number::text) AS account_number "
            "FROM gold.loan_account_master WHERE sanction_date <= CURRENT_DATE AND ("
            f"{stored_name} LIKE {name_literal} || '%' OR "
            f"LOWER(customer_id::text) LIKE {id_literal} || '%' OR "
            f"LOWER(loan_account_number::text) LIKE {id_literal} || '%') "
            "GROUP BY TRIM(REGEXP_REPLACE(customer_name, '\\s+', ' ', 'g')), customer_id "
            "ORDER BY borrower_name, customer_id LIMIT 8"
        )
        attempt = _validated_attempt(
            sql, catalog=cat, explanation="Chat entity completions from governed borrowers.",
            units={"borrower_name": "text", "customer_id": "text", "account_number": "text"},
            pii_columns={"customer_name"},
        )
        for row in execute_raw(attempt.sql).rows:
            customer_id = _plain_identifier(str(row.get("customer_id", "")))
            account = _plain_identifier(str(row.get("account_number", "")))
            name = str(row.get("borrower_name", "")).strip()
            if kind == "customer":
                value, result_kind = customer_id, "customer"
            elif kind == "account":
                value, result_kind = account, "account"
            else:
                value, result_kind = name, "borrower"
            results.append({
                "kind": result_kind,
                "value": value,
                "label": name or f"Customer {customer_id}",
                "detail": f"Customer {customer_id} · Account ending {account[-4:]}",
            })

    if kind in {"all", "agent"}:
        literal = _literal(text.lower())
        sql = (
            "SELECT agent_code, agent_name, designation FROM gold.agent_master "
            f"WHERE LOWER(agent_code) LIKE {literal} || '%' "
            f"OR LOWER(agent_name) LIKE '%' || {literal} || '%' "
            "ORDER BY agent_code LIMIT 8"
        )
        attempt = _validated_attempt(
            sql, catalog=cat, explanation="Chat entity completions from the governed agent directory.",
            units={"agent_code": "text", "agent_name": "text", "designation": "text"},
            pii_columns={"agent_name"},
        )
        for row in execute_raw(attempt.sql).rows:
            code = str(row.get("agent_code", "")).strip()
            name = str(row.get("agent_name", "")).strip()
            designation = str(row.get("designation", "") or "Agent").strip()
            results.append({
                "kind": "agent", "value": code, "label": name or code,
                "detail": f"{code} · {designation}",
            })
    return results[:8]


def _plain_identifier(value: str) -> str:
    text = str(value).strip().replace(",", "")
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def _is_person_name(value: str) -> bool:
    """Whether a captured phrase can be a borrower rather than governed vocabulary.

    The name patterns are deliberately loose so real names survive; this is what stops
    "customer information" from being planned as a lookup for a borrower called "customer".
    """
    tokens = [token for token in re.split(r"[^a-z0-9]+", value.lower()) if token]
    if not tokens or len(tokens) > 6:
        return False
    if any(token in _NON_NAME_WORDS for token in tokens):
        return False
    return any(token not in _GENERIC_NAME_WORDS for token in tokens)


def _name_tokens(name: str) -> list[str]:
    """Distinct normalised name parts, in the same spelling the stored name is reduced to."""
    tokens: list[str] = []
    for raw in str(name or "").split():
        token = re.sub(r"[^a-z0-9]", "", raw.lower()).replace("th", "t")
        token = re.sub(r"(.)\1+", r"\1", token)
        if len(token) >= 3 and token not in tokens:
            tokens.append(token)
    return tokens


def _agent_code(value: str) -> str:
    """Governed agent codes are zero-padded to two digits — "agent 4" is AGNT04."""
    return "AGNT" + re.sub(r"\D", "", value).zfill(2)


def _clean_name(value: str) -> str:
    """Strip sentence scaffolding an extraction pattern carried into the captured name.

    The name group is deliberately permissive so real names survive punctuation and
    initials, which means it also absorbs whatever filler sits between the name and the
    noun the pattern anchored on — "SHEELA all accounts details" captures "SHEELA all".
    Generic words can only be scaffolding at either end; a name made of nothing else is
    rejected later by `_is_person_name`.
    """
    tokens = " ".join(str(value or "").split()).strip(" .?!,").split()
    while tokens and tokens[0].lower().strip(".,'") in _NAME_FILLER_WORDS:
        tokens.pop(0)
    while tokens and tokens[-1].lower().strip(".,'") in _NAME_FILLER_WORDS:
        tokens.pop()
    return " ".join(tokens)


def _requested_loan_fields(text: str) -> list[str]:
    """Extract requested loan facts without binding to a particular phrasing or value."""
    fields: list[str] = []
    if _SANCTION_AMOUNT_CUE.search(text):
        fields.append("sanction_amount")
    if _SANCTION_DATE_CUE.search(text):
        fields.append("sanction_date")
    if _DISBURSEMENT_AMOUNT_CUE.search(text):
        fields.append("disbursed_amount")
    if _DISBURSEMENT_DATE_CUE.search(text):
        fields.append("first_disbursement_date")
    # In an amount-and-date question, an otherwise unqualified "date" is the loan's
    # sanction date. A disbursement-date cue above remains unambiguous.
    if (
        "sanction_amount" in fields
        and not any(field.endswith("date") for field in fields)
        and re.search(r"\bdate\b", text, re.I)
    ):
        fields.append("sanction_date")
    return fields


def _requested_agent_fields(text: str) -> list[str]:
    cues = (
        (r"\b(?:mobile|phone)(?:\s+number)?\b", "mobile"),
        (r"\bemail(?:\s+address)?\b", "email"),
        (r"\bnames?\b", "agent_name"),
        (r"\b(?:agent\s+)?types?\b", "agent_type"),
        (r"\bdesignation\b", "designation"),
        (r"\bbranch(?:\s+code)?\b", "branch_code"),
        (r"\brole(?:\s+code)?\b", "role_code"),
        (r"\bjoin(?:ed|ing)?(?:\s+(?:on|date))?\b", "joined_on"),
        (r"\blinked\s+(?:customers?|borrowers?)\b", "linked_customer_count"),
        (r"\blinked\s+(?:loans?|accounts?)\b|\b(?:loans?|accounts?)\s+count\b|\bcount\s+of\s+(?:loans?|accounts?)\b", "linked_loan_count"),
    )
    return [field for pattern, field in cues if re.search(pattern, text, re.I)]


def detect(question: str) -> LookupPlan | None:
    """Recognise selector + requested record family without matching whole questions."""
    text = normalize_apostrophes(" ".join(str(question or "").split()))

    branch_code = _BRANCH_CODE_REF.search(text)
    if branch_code and _CUSTOMER_DETAIL_CUE.search(text):
        return LookupPlan(
            selector="branch", value=re.sub(r"\D", "", branch_code.group()),
            detail="branch_directory",
            reasoning="governed directory row for the requested branch code",
        )
    if _BRANCH_DIRECTORY_CUE.search(text):
        return LookupPlan(
            selector="branch", value="all", detail="branch_directory",
            reasoning="current governed branch directory",
        )

    if _AGENT_DIRECTORY_CUE.search(text) and not _AGENT_CODE.search(text):
        return LookupPlan(
            selector="agent_code", value="all", detail="agent_directory",
            reasoning="current governed agent directory",
        )

    if _AGENT_COUNT_CUE.search(text):
        return LookupPlan(
            selector="agent_code", value="all", detail="agent_count",
            reasoning="count of agents in the current governed agent directory",
        )

    if (
        _GENDER_ACCOUNT_SAMPLE.search(text)
        and re.search(r"\baccount(?:\s+(?:number|no\.?))?s?\b", text, re.I)
    ):
        return LookupPlan(
            selector="gender", value="male,female", detail="account_sample",
            reasoning="one deterministic loan-account sample for each requested gender",
        )

    customer = _CUSTOMER_ID.search(text)
    account = _ACCOUNT_ID.search(text) or _ACCOUNT_ID_BARE.search(text)
    agent = _AGENT_CODE.search(text)
    product = _PRODUCT_CODE.search(text) or _PRODUCT_CODE_BARE.search(text)
    # An explicit "product code 13" is already a request for that product; only the bare
    # "product 13" form needs a cue to tell a lookup from a filter on a metric question.
    if product and (_PRODUCT_DETAIL_CUE.search(text) or _PRODUCT_CODE.search(text)):
        return LookupPlan(
            selector="product_code", value=_plain_identifier(product.group("value")),
            detail="product_details", reasoning="governed product-directory lookup",
        )
    # "borrowers under AGNT45" asks for the same linked records as "AGNT45 account
    # numbers", named by borrower instead of by account. A count question is not this —
    # that is a directory field and falls through to the agent-details branch below.
    agent_borrowers = bool(
        agent and _AGENT_BORROWER_CUE.search(text) and not _COUNT_CUE.search(text)
    )
    if agent and (_AGENT_ACCOUNT_CUE.search(text) or agent_borrowers):
        requested = (
            ["borrower_name"]
            if _BORROWER_NAME_CUE.search(text) or agent_borrowers
            else []
        )
        return LookupPlan(
            selector="agent_code",
            value=_agent_code(agent.group("value")),
            detail="agent_accounts", requested_fields=requested,
            reasoning="loan accounts linked to the governed agent code",
        )
    if agent:
        # Naming a directory field is itself the request: "agent 45 phone number" asks for
        # the same record as "show me the agent 45 phone number". Without this, a terse
        # phrasing carries no verb, matches no cue, and is routed to the concepts source,
        # which then explains that it cannot see phone numbers it was never shown.
        agent_fields = _requested_agent_fields(text)
        if agent_fields or _AGENT_DETAIL_CUE.search(text) or _AGENT_CODE.fullmatch(text.strip()):
            return LookupPlan(
                selector="agent_code",
                value=_agent_code(agent.group("value")),
                detail="agent_details", requested_fields=agent_fields,
                reasoning="governed agent-directory details",
            )
    if _REPAYMENT_CUE.search(text):
        if customer:
            selector, value = "customer_id", _plain_identifier(customer.group("value"))
        elif account:
            selector, value = "loan_account", _plain_identifier(account.group("value"))
        else:
            match = (
                _NAME_AFTER_HISTORY.search(text)
                or _NAME_BEFORE_HISTORY.search(text)
                or _NAME_AFTER_BARE_REPAYMENT.search(text)
                or _NAME_BEFORE_BARE_REPAYMENT.search(text)
            )
            if not match or not _is_person_name(_clean_name(match.group("name"))):
                return None
            selector, value = "borrower_name", _clean_name(match.group("name"))
        return LookupPlan(
            selector=selector, value=value, detail="repayment_history",
            reasoning="governed borrower repayment-event history",
        )

    if customer and _LOAN_DETAIL_CUE.search(text):
        return LookupPlan(
            selector="customer_id", value=_plain_identifier(customer.group("value")),
            detail="loan_details", requested_fields=_requested_loan_fields(text),
            reasoning="governed loan-account origination and disbursement details",
        )
    if account and _LOAN_DETAIL_CUE.search(text):
        return LookupPlan(
            selector="loan_account", value=_plain_identifier(account.group("value")),
            detail="loan_details", requested_fields=_requested_loan_fields(text),
            reasoning="governed loan-account origination and disbursement details",
        )
    if account and _CUSTOMER_DETAIL_CUE.search(text):
        return LookupPlan(
            selector="loan_account", value=_plain_identifier(account.group("value")),
            detail="loan_details", requested_fields=_requested_loan_fields(text),
            reasoning="governed record for the named loan account",
        )
    if customer and _CUSTOMER_DETAIL_CUE.search(text):
        return LookupPlan(
            selector="customer_id", value=_plain_identifier(customer.group("value")),
            detail="customer_summary",
            reasoning="governed customer and linked-loan summary",
        )
    # Every pattern below captures a free-text name. A question that already names a
    # governed identifier is never one of them — without this guard "branch 1002 details"
    # and "account number 100... details" are planned as borrowers with those names.
    if customer or account or agent or product or _BRANCH_CODE_REF.search(text):
        return None

    named_field = _NAME_BEFORE_CUSTOMER_FIELD.search(text)
    if named_field and _is_person_name(_clean_name(named_field.group("name"))):
        return LookupPlan(
            selector="borrower_name", value=_clean_name(named_field.group("name")),
            detail="customer_summary",
            reasoning="governed customer profile holding the requested field",
        )

    named_accounts = _NAME_ACCOUNTS.search(text)
    if named_accounts:
        captured = named_accounts.group("name") or named_accounts.group("name2") or ""
        if _is_person_name(_clean_name(captured)):
            return LookupPlan(
                selector="borrower_name", value=_clean_name(captured),
                detail="loan_details",
                reasoning="governed loan accounts held by the named borrower",
            )

    named_details = (
        _NAME_AFTER_LOAN_DETAILS.search(text) or _NAME_BEFORE_LOAN_DETAILS.search(text)
    )
    if named_details and _is_person_name(_clean_name(named_details.group('name'))):
        return LookupPlan(
            selector="borrower_name", value=_clean_name(named_details.group("name")),
            detail="loan_details",
            reasoning="governed borrower loan origination and disbursement details",
        )
    named_customer = (
        _NAME_IDENTITY.search(text)
        or _NAME_THEN_REQUEST.search(text)
        or _NAME_BEFORE_CUSTOMER_DETAILS.search(text)
        or _NAME_AFTER_CUSTOMER_DETAILS.search(text)
        or _NAME_AFTER_DETAILS.search(text)
    )
    if named_customer and _is_person_name(_clean_name(named_customer.group("name"))):
        return LookupPlan(
            selector="borrower_name", value=_clean_name(named_customer.group("name")),
            detail="customer_summary",
            reasoning="governed customer and linked-loan summary",
        )
    named_loan_field = _NAME_BEFORE_LOAN_FIELD.search(text) or _NAME_AFTER_LOAN_FIELD.search(text)
    if named_loan_field and _is_person_name(_clean_name(named_loan_field.group('name'))):
        return LookupPlan(
            selector="borrower_name", value=_clean_name(named_loan_field.group("name")),
            detail="loan_details", requested_fields=_requested_loan_fields(text),
            reasoning="requested governed loan field for the named borrower",
        )
    if _LOAN_DETAIL_CUE.search(text):
        named = _NAMED_LOAN_DETAIL.search(text)
        if named and _is_person_name(_clean_name(named.group("name"))):
            return LookupPlan(
                selector="borrower_name", value=_clean_name(named.group("name")),
                detail="loan_details", requested_fields=_requested_loan_fields(text),
                reasoning="governed borrower loan origination and disbursement details",
            )
    return None


_ANAPHORIC_AGENT = re.compile(
    r"\b(?:the\s+)?(?:above|same|that|this|previous|said)\s+agent\b", re.I
)
"""«accounts and names of borrowers linked to the above agent» — the code was named a turn
ago, and the record grammar has no way to see it from this question alone."""


def resolve_followup(question: str, history_messages: list[dict[str, str]] | None) -> str:
    """Complete a bare record refinement from the question it refines.

    "along with names" is not a question the record grammar — or the source router — can
    read on its own, and handing the fragment to a model instead produces an invented
    reason why the names cannot be shown. Folded onto the previous question it becomes the
    same governed lookup with one more field, which is exactly what was asked.
    """
    text = normalize_apostrophes(" ".join(str(question or "").split()))
    if not text:
        return question
    refinement = bool(_RECORD_REFINEMENT.fullmatch(text))
    anaphor = _ANAPHORIC_AGENT.search(text)
    if not refinement and anaphor is None:
        return question
    previous = next(
        (
            str(message.get("content", "")).strip()
            for message in reversed(history_messages or [])
            if message.get("role") == "user" and str(message.get("content", "")).strip()
        ),
        "",
    )
    if not previous:
        return question
    if anaphor is not None:
        code = _AGENT_CODE.search(normalize_apostrophes(previous))
        if code is None:
            return question
        return text[: anaphor.start()] + _agent_code(code.group("value")) + text[anaphor.end():]
    if detect(previous) is None:
        return question
    return f"{previous} {text}"


def _literal(value: str) -> str:
    return exp.Literal.string(value).sql(dialect="postgres")


def _validated_attempt(
    sql: str,
    *,
    catalog: Catalog,
    explanation: str,
    units: dict[str, str],
    pii_columns: set[str] | None = None,
) -> SqlAttempt:
    checked = validate(
        sql,
        catalog=catalog,
        allow_pii=bool(pii_columns),
        allowed_pii_columns=pii_columns,
    )
    return SqlAttempt(
        sql=checked.sql,
        tables=checked.tables,
        explanation=explanation,
        validated=True,
        attempts=0,
        model="deterministic",
        provider="catalog",
        pii_columns=checked.pii_columns,
        column_units=units,
        reviewed=True,
    )


def _borrower_candidate_sql(where: str, display_name: str) -> str:
    return (
        f"SELECT {display_name} AS borrower_name, customer_id::text AS customer_id, "
        "MIN(loan_account_number::text) AS account_number "
        "FROM gold.loan_account_master "
        f"WHERE {where} AND sanction_date <= CURRENT_DATE "
        f"GROUP BY {display_name}, customer_id ORDER BY {display_name}, customer_id LIMIT 20"
    )


def _candidate_customers(name: str, catalog: Catalog) -> list[dict]:
    literal, stored_name, display_name = _normalized_borrower_sql(name)

    def fetch(where: str) -> list[dict]:
        attempt = _validated_attempt(
            _borrower_candidate_sql(where, display_name), catalog=catalog,
            explanation="Borrower candidates from the governed loan master.",
            units={"borrower_name": "text", "customer_id": "text", "account_number": "text"},
            pii_columns={"customer_name"},
        )
        return execute_raw(attempt.sql).rows

    rows = fetch(f"{stored_name} LIKE {literal} || '%'")
    if rows:
        return rows

    # The prefix match reads the name as one run of letters, so a repeated or reordered
    # part ("MAHABOOB PASHA PASHA") misses a record that holds every part of it. Fall back
    # to requiring each distinct part somewhere in the stored name — still every part, so
    # this widens the spelling accepted without widening who can match.
    tokens = _name_tokens(name)
    if len(tokens) < 2:
        return []
    return fetch(
        " AND ".join(f"{stored_name} LIKE '%' || {_literal(token)} || '%'" for token in tokens)
    )


def _where(plan: LookupPlan) -> str:
    value = _literal(_plain_identifier(plan.value).lower())
    if plan.selector == "loan_account":
        return f"LOWER(loan_account_number::text) = {value}"
    return (
        "LOWER(REGEXP_REPLACE(customer_id::text, '\\.0+$', '')) = " + value
    )


def _loan_details(plan: LookupPlan, catalog: Catalog) -> SqlAttempt:
    available = {
        "sanction_amount": "inr",
        "sanction_date": "date",
        "disbursed_amount": "inr",
        "first_disbursement_date": "date",
    }
    requested = list(dict.fromkeys(plan.requested_fields)) or list(available)
    selected = ", ".join(requested)
    sql = (
        "SELECT customer_id::text AS customer_id, "
        f"loan_account_number::text AS loan_account_number, {selected} "
        "FROM gold.loan_account_master WHERE " + _where(plan) +
        " AND sanction_date <= CURRENT_DATE ORDER BY sanction_date DESC, "
        "loan_account_number LIMIT 500"
    )
    return _validated_attempt(
        sql, catalog=catalog,
        explanation="Requested governed fields for each matched loan account.",
        units={
            "customer_id": "text", "loan_account_number": "text",
            **{field: available[field] for field in requested},
        },
    )


def _shape_loan_details(chart: ChartSpec, plan: LookupPlan) -> None:
    """Keep only requested facts in the UI while retaining account context when needed."""
    from app.services.nlq.narrator import format_value

    labels = {
        "sanction_amount": "Sanction amount",
        "sanction_date": "Sanction date",
        "disbursed_amount": "Disbursed amount",
        "first_disbursement_date": "First disbursement date",
    }
    requested = list(dict.fromkeys(plan.requested_fields))
    chart.title = "Requested loan details"
    chart.chart_type = "table"
    chart.x = None
    chart.series_by = None
    chart.series = []
    if not requested:
        chart.summary = f"Returned {len(chart.rows):,} matched loan account(s)."
        return

    visible = (["loan_account_number"] if len(chart.rows) > 1 else []) + requested
    for row in chart.rows:
        for field in list(row):
            if field not in visible:
                row.pop(field, None)
    chart.columns = [column for column in chart.columns if column.name in visible]

    if len(chart.rows) == 1:
        row = chart.rows[0]
        facts = [
            f"{labels[field]} is {format_value(row.get(field), chart_column_unit(chart, field))}"
            for field in requested
        ]
        chart.summary = "; ".join(facts) + "."
    else:
        named = ", ".join(labels[field].lower() for field in requested)
        chart.summary = f"Returned {len(chart.rows):,} matched loan accounts with {named}."


def chart_column_unit(chart: ChartSpec, field: str) -> str:
    column = next((column for column in chart.columns if column.name == field), None)
    return column.unit if column is not None else "number"


def _customer_summary(plan: LookupPlan, catalog: Catalog) -> SqlAttempt:
    """Return the intentionally narrow customer profile requested by the UI."""
    value = _literal(_plain_identifier(plan.value).lower())
    sql = (
        "SELECT customer.customer_id::text AS customer_id, "
        "customer.full_name AS customer_name, "
        "loan.loan_account_number::text AS loan_account_number, "
        "loan.sanction_amount, loan.sanction_date, "
        "CONCAT_WS(', ', NULLIF(TRIM(customer.address_line1), ''), "
        "NULLIF(TRIM(customer.address_line2), ''), "
        "NULLIF(TRIM(customer.additional_address), '')) AS address, "
        "COALESCE(NULLIF(TRIM(customer.occupation_name), ''), "
        "NULLIF(TRIM(customer.occupation_type), ''), "
        "NULLIF(TRIM(customer.occupation_nature), '')) AS occupation, "
        "customer.home_branch_code, customer.agency_code, customer.agency_name "
        "FROM gold.customer_master AS customer "
        "LEFT JOIN gold.loan_account_master AS loan "
        "ON customer.entity_num = loan.entity_num "
        "AND customer.customer_id = loan.customer_id "
        "AND loan.sanction_date <= CURRENT_DATE "
        "WHERE LOWER(REGEXP_REPLACE(customer.customer_id::text, '\\.0+$', '')) = "
        + value +
        " ORDER BY loan.sanction_date DESC, loan.loan_account_number LIMIT 500"
    )
    return _validated_attempt(
        sql, catalog=catalog,
        explanation="Requested customer profile fields and linked sanctioned loan accounts.",
        units={
            "customer_id": "text", "customer_name": "text",
            "loan_account_number": "text", "sanction_amount": "inr",
            "sanction_date": "date", "address": "text", "occupation": "text",
            "home_branch_code": "text", "agency_code": "text", "agency_name": "text",
        },
        pii_columns={
            "full_name", "address_line1", "address_line2", "additional_address",
            "agency_name",
        },
    )
def _repayment_history(plan: LookupPlan, catalog: Catalog) -> SqlAttempt:
    sql = (
        "SELECT loan_account_number::text AS loan_account_number, repayment_date, "
        "principal_due, interest_due, total_due, principal_paid, interest_paid, total_paid, "
        "collection_shortfall, collection_efficiency, "
        "SUM(total_due) OVER () AS history_total_due, "
        "SUM(total_paid) OVER () AS history_total_paid, "
        "SUM(collection_shortfall) OVER () AS history_total_shortfall "
        "FROM gold.loan_repayment_events WHERE " + _where(plan) +
        " AND repayment_date <= CURRENT_DATE ORDER BY repayment_date DESC, "
        "repayment_sequence DESC LIMIT 500"
    )
    return _validated_attempt(
        sql, catalog=catalog,
        explanation="Repayment events newest first, with totals across all matched events.",
        units={
            "loan_account_number": "text", "repayment_date": "date",
            "principal_due": "inr", "interest_due": "inr", "total_due": "inr",
            "principal_paid": "inr", "interest_paid": "inr", "total_paid": "inr",
            "collection_shortfall": "inr", "collection_efficiency": "percent",
            "history_total_due": "inr", "history_total_paid": "inr",
            "history_total_shortfall": "inr",
        },
    )


def _gender_sample(catalog: Catalog) -> SqlAttempt:
    sql = (
        "SELECT gender, loan_account_number FROM ("
        "SELECT CASE WHEN LOWER(TRIM(customer.gender)) IN ('m', 'male') THEN 'Male' "
        "ELSE 'Female' END AS gender, loan.loan_account_number::text AS loan_account_number, "
        "ROW_NUMBER() OVER (PARTITION BY CASE WHEN LOWER(TRIM(customer.gender)) "
        "IN ('m', 'male') THEN 'Male' ELSE 'Female' END "
        "ORDER BY loan.loan_account_number) AS sample_rank "
        "FROM gold.customer_master AS customer JOIN gold.loan_account_master AS loan "
        "ON customer.entity_num = loan.entity_num AND customer.customer_id = loan.customer_id "
        "WHERE LOWER(TRIM(customer.gender)) IN ('m', 'male', 'f', 'female') "
        "AND loan.sanction_date <= CURRENT_DATE) AS ranked "
        "WHERE sample_rank = 1 ORDER BY gender LIMIT 2"
    )
    return _validated_attempt(
        sql, catalog=catalog,
        explanation="One stable loan-account sample for each recorded male/female gender.",
        units={"gender": "text", "loan_account_number": "text"},
    )


def _agent_details(plan: LookupPlan, catalog: Catalog) -> SqlAttempt:
    value = _literal(plan.value.lower())
    available = {
        "agent_name": "text", "agent_type": "text", "designation": "text",
        "mobile": "text", "email": "text", "branch_code": "text", "role_code": "text",
        "joined_on": "date", "linked_customer_count": "count", "linked_loan_count": "count",
    }
    requested = list(dict.fromkeys(plan.requested_fields))
    selected = requested or [
        "agent_name", "agent_type", "designation", "branch_code", "role_code",
        "joined_on", "linked_customer_count", "linked_loan_count",
    ]
    sql = (
        "SELECT agent_code, " + ", ".join(selected) + " "
        "FROM gold.agent_master WHERE LOWER(agent_code) = " + value +
        " ORDER BY agent_code LIMIT 20"
    )
    pii = {field for field in selected if field in {"agent_name", "mobile", "email"}}
    return _validated_attempt(
        sql, catalog=catalog,
        explanation="Current governed directory details for the requested agent code.",
        units={"agent_code": "text", **{field: available[field] for field in selected}},
        pii_columns=pii or None,
    )


def _shape_customer_summary(chart: ChartSpec) -> None:
    """A profile is a record, not a ranking.

    Left unshaped this family kept the generated-SQL narration, which reads the sanction
    column as a measure and reports the "highest" of one row, and appends a caveat about
    unreviewed SQL that does not apply to an application-owned query.
    """
    from app.services.nlq.narrator import format_value

    chart.chart_type = "table"
    chart.x = None
    chart.series_by = None
    chart.series = []
    first = chart.rows[0]
    name = str(first.get("customer_name", "")).strip()
    customer_id = str(first.get("customer_id", "")).strip()
    chart.title = name or f"Customer {customer_id}"
    accounts = len({
        str(row.get("loan_account_number", "")) for row in chart.rows
        if str(row.get("loan_account_number", "") or "").strip()
    })
    sanctioned = sum(
        value for row in chart.rows
        if isinstance(value := row.get("sanction_amount"), (int, float))
    )
    if not accounts:
        chart.summary = f"{chart.title} is customer {customer_id} with no sanctioned loan accounts."
        return
    chart.summary = (
        f"{chart.title} is customer {customer_id} with {accounts:,} sanctioned loan "
        f"account(s) totalling {format_value(sanctioned, 'inr')}."
    )


def _shape_agent_details(chart: ChartSpec, plan: LookupPlan) -> None:
    requested = list(dict.fromkeys(plan.requested_fields))
    chart.title = plan.value
    chart.chart_type = "table"
    chart.x = None
    chart.series_by = None
    chart.series = []
    if not requested:
        chart.summary = f"Returned the current governed directory profile for {plan.value}."
        return

    labels = {
        "agent_name": "Agent name", "agent_type": "Agent type", "designation": "Designation",
        "mobile": "Phone number", "email": "Email", "branch_code": "Branch code",
        "role_code": "Role code", "joined_on": "Joined on",
        "linked_customer_count": "Linked customer count",
        "linked_loan_count": "Linked loan count",
    }
    visible = ["agent_code", *requested]
    for row in chart.rows:
        for field in list(row):
            if field not in visible:
                row.pop(field, None)
    chart.columns = [column for column in chart.columns if column.name in visible]
    row = chart.rows[0]
    facts = []
    for field in requested:
        value = row.get(field)
        if value is None or not str(value).strip():
            facts.append(f"{labels[field]} is unavailable in the governed agent directory")
        else:
            facts.append(f"{labels[field]} is {value}")
    chart.summary = "; ".join(facts) + "."


def _agent_count(catalog: Catalog) -> SqlAttempt:
    return _validated_attempt(
        "SELECT COUNT(agent_code) AS agent_count FROM gold.agent_master LIMIT 1",
        catalog=catalog,
        explanation="Count of agents in the current governed agent directory.",
        units={"agent_count": "count"},
    )


def _agent_accounts(plan: LookupPlan, catalog: Catalog) -> SqlAttempt:
    value = _literal(plan.value.lower())
    include_name = "borrower_name" in plan.requested_fields
    name_projection = ", loan.customer_name AS borrower_name" if include_name else ""
    join = (
        " JOIN gold.loan_account_master AS loan "
        "ON reporting.entity_num = loan.entity_num "
        "AND reporting.loan_account_number = loan.loan_account_number"
        if include_name else ""
    )
    sql = (
        "SELECT reporting.loan_account_number::text AS loan_account_number" + name_projection + ", "
        "COUNT(reporting.loan_account_number) OVER () AS total_linked_account_count "
        "FROM gold.loan_reporting_attributes AS reporting" + join +
        " WHERE LOWER(reporting.agent_code) = " + value +
        " ORDER BY reporting.loan_account_number LIMIT 500"
    )
    return _validated_attempt(
        sql, catalog=catalog,
        explanation="Loan account numbers linked to the requested governed agent code.",
        units={
            "loan_account_number": "text", "total_linked_account_count": "count",
            **({"borrower_name": "text"} if include_name else {}),
        },
        pii_columns={"customer_name"} if include_name else None,
    )


def _agent_directory(catalog: Catalog) -> SqlAttempt:
    sql = (
        "SELECT agent_code, agent_name, agent_type, designation, branch_code, "
        "linked_customer_count, linked_loan_count FROM gold.agent_master "
        "ORDER BY agent_code LIMIT 500"
    )
    return _validated_attempt(
        sql, catalog=catalog, explanation="Current governed agent directory.",
        units={
            "agent_code": "text", "agent_name": "text", "agent_type": "text",
            "designation": "text", "branch_code": "text",
            "linked_customer_count": "count", "linked_loan_count": "count",
        },
        pii_columns={"agent_name"},
    )


def _branch_directory(plan: LookupPlan, catalog: Catalog) -> SqlAttempt:
    where = (
        ""
        if plan.value == "all"
        else " WHERE LOWER(branch_code::text) = " + _literal(plan.value.lower())
    )
    sql = (
        "SELECT branch_code, branch_name, branch_category_name, branch_size, "
        "branch_status, opened_on FROM gold.branch_master" + where +
        " ORDER BY branch_name, branch_code LIMIT 500"
    )
    return _validated_attempt(
        sql, catalog=catalog, explanation="Current governed branch directory.",
        units={
            "branch_code": "text", "branch_name": "text",
            "branch_category_name": "text", "branch_size": "text",
            "branch_status": "text", "opened_on": "date",
        },
    )


def _product_details(plan: LookupPlan, catalog: Catalog) -> SqlAttempt:
    value = _literal(_plain_identifier(plan.value).lower())
    sql = (
        "SELECT DISTINCT product_code::text AS product_code, product_name "
        "FROM gold.product_master WHERE LOWER(product_code::text) = " + value +
        " ORDER BY product_name, product_code LIMIT 100"
    )
    return _validated_attempt(
        sql, catalog=catalog,
        explanation="Current governed product name for the requested product code.",
        units={"product_code": "text", "product_name": "text"},
    )


def run(plan: LookupPlan, *, role: str | None, catalog: Catalog | None = None) -> LookupResult:
    cat = catalog or get_catalog()
    effective = plan
    if plan.selector == "borrower_name":
        candidates = _candidate_customers(plan.value, cat)
        if not candidates:
            return LookupResult(no_match=True)
        identities = {str(row.get("customer_id", "")): row for row in candidates}
        if len(identities) != 1:
            suggestions = []
            for customer_id, row in list(identities.items())[:3]:
                name = str(row.get("borrower_name", ""))
                account = _plain_identifier(str(row.get("account_number", "")))
                suffix = account[-4:] if account else "unknown"
                if plan.detail == "repayment_history":
                    prefix = "Show repayment history for"
                elif plan.detail == "customer_summary":
                    prefix = "Show customer details for"
                else:
                    prefix = "Show loans for"
                suggestions.append(
                    f"{prefix} customer ID {customer_id} ({name}, account ending {suffix})"
                )
            return LookupResult(clarification=ClarifyPlan(
                question="Several borrowers match that name. Choose the intended customer:",
                suggestions=suggestions,
            ))
        customer_id = next(iter(identities))
        effective = plan.model_copy(update={"selector": "customer_id", "value": customer_id})

    if effective.detail == "customer_summary":
        attempt = _customer_summary(effective, cat)
    elif effective.detail == "loan_details":
        attempt = _loan_details(effective, cat)
    elif effective.detail == "repayment_history":
        attempt = _repayment_history(effective, cat)
    elif effective.detail == "agent_details":
        attempt = _agent_details(effective, cat)
    elif effective.detail == "agent_count":
        attempt = _agent_count(cat)
    elif effective.detail == "agent_directory":
        attempt = _agent_directory(cat)
    elif effective.detail == "agent_accounts":
        attempt = _agent_accounts(effective, cat)
    elif effective.detail == "branch_directory":
        attempt = _branch_directory(effective, cat)
    elif effective.detail == "product_details":
        attempt = _product_details(effective, cat)
    else:
        attempt = _gender_sample(cat)

    chart = run_sql(attempt, question=plan.reasoning, role=role, catalog=cat)
    if not chart.rows:
        return LookupResult(no_match=True)
    chart.subtitle = "Governed read-only record lookup"
    if effective.detail == "customer_summary":
        _shape_customer_summary(chart)
    elif effective.detail == "loan_details":
        _shape_loan_details(chart, effective)
    elif effective.detail == "agent_details":
        _shape_agent_details(chart, effective)
    elif effective.detail == "product_details":
        chart.title = "Product details"
        names = list(dict.fromkeys(
            str(row.get("product_name", "")).strip()
            for row in chart.rows if str(row.get("product_name", "")).strip()
        ))
        if len(names) == 1:
            chart.summary = f"Product code {effective.value} is {names[0]}."
        else:
            chart.summary = (
                f"Returned {len(chart.rows):,} governed product-name record(s) for "
                f"product code {effective.value}."
            )
    elif effective.detail in {"agent_directory", "branch_directory"}:
        chart.chart_type = "table"
        chart.x = None
        chart.series_by = None
        chart.series = []
        noun = "agent" if effective.detail == "agent_directory" else "branch"
        if effective.value != "all":
            chart.title = f"Branch {effective.value}"
            name = str(chart.rows[0].get("branch_name", "")).strip()
            chart.summary = (
                f"Branch {effective.value} is {name}." if name
                else f"Returned the governed directory row for branch {effective.value}."
            )
        else:
            chart.title = f"{noun.title()} directory"
            # The row cap is real: say "of" only when the cap was actually reached, so a
            # complete directory is never reported as a partial one.
            capped = " (row limit reached)" if len(chart.rows) >= 500 else ""
            chart.summary = (
                f"Returned {len(chart.rows):,} {noun}(s) from the governed directory{capped}."
            )
    elif effective.detail == "agent_accounts":
        total = int(chart.rows[0].get("total_linked_account_count") or len(chart.rows))
        for row in chart.rows:
            row.pop("total_linked_account_count", None)
        chart.columns = [
            column for column in chart.columns if column.name != "total_linked_account_count"
        ]
        chart.series = [
            series for series in chart.series if series.field != "total_linked_account_count"
        ]
        chart.chart_type = "table"
        chart.x = None
        chart.series_by = None
        chart.title = f"Loan accounts linked to {effective.value}"
        suffix = " with borrower names" if "borrower_name" in effective.requested_fields else ""
        chart.summary = (
            f"Showing {len(chart.rows):,} of {total:,} linked loan account(s){suffix}."
        )
    elif effective.detail == "repayment_history":
        first = chart.rows[0]
        totals = {
            "history_total_due": first.get("history_total_due"),
            "history_total_paid": first.get("history_total_paid"),
            "history_total_shortfall": first.get("history_total_shortfall"),
        }
        for row in chart.rows:
            for field in totals:
                row.pop(field, None)
        chart.columns = [column for column in chart.columns if column.name not in totals]
        chart.series = [series for series in chart.series if series.field not in totals]
        from app.services.nlq.narrator import format_value
        chart.summary = (
            f"{chart.lineage.row_count:,} repayment event(s) returned. Total due was "
            f"{format_value(totals['history_total_due'], 'inr')}; total paid was "
            f"{format_value(totals['history_total_paid'], 'inr')}; total shortfall was "
            f"{format_value(totals['history_total_shortfall'], 'inr')}."
        )
    return LookupResult(chart=chart)


__all__ = ["LookupResult", "completions", "detect", "resolve_followup", "run"]
