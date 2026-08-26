"""Conservative spelling normalisation for lending questions.

The model is expected to understand ordinary variation, but two operational typos have a
disproportionate effect on routing:

* ``intrest`` misses the governed interest-rate/interest-paid vocabulary; and
* ``disbursment`` misses the governed disbursement vocabulary; and
* common transpositions of ``history`` miss repayment-history retrieval; and
* ``schema`` is frequently typed when the user means a loan *scheme*, which sends the
  workbench to the database-structure source instead of the loan book.

Only unambiguous corrections happen here.  In particular, ``schema`` remains untouched
when the question contains structural words such as table, column, relationship or join.
The original question is still retained in conversation history and audit records; this
normalised form is only what routing and planning read.
"""

from __future__ import annotations

import re

_APOSTROPHE = re.compile(r"[‘’ʼ´`]")
"""A possessive typed on a phone keyboard arrives as a curly quote, and one typed next to
the backtick key arrives as a backtick. Both mean "'s", and a grammar that only knows the
ASCII apostrophe silently loses the borrower name in front of it."""

_INTEREST_TYPO = re.compile(r"\bint(?:r|er)?est\b|\bintrest\b", re.IGNORECASE)
_DISBURSEMENT_TYPO = re.compile(r"\bdisbursment\b", re.IGNORECASE)
_HISTORY_TYPO = re.compile(r"\b(?:histoy|histry|hisotry|hitory)\b", re.IGNORECASE)
_SCHEMA_WORD = re.compile(r"\bschema\b", re.IGNORECASE)
_STRUCTURE_WORDS = re.compile(
    r"\b(?:database|table|tables|column|columns|relationship|relationships|join|joins|"
    r"erd|diagram|structure|definition|ddl|foreign\s+key|primary\s+key)\b",
    re.IGNORECASE,
)
_LENDING_SCHEME_CONTEXT = re.compile(
    r"\b(?:loan|lending|product|interest|rate|amount|paid|payment|repayment|collected|"
    r"collection|disburs(?:e|ed|ement)|sanction(?:ed)?|outstanding|borrower|account)\b",
    re.IGNORECASE,
)


def normalize_apostrophes(text: str) -> str:
    """Fold curly, modifier and backtick apostrophes onto the ASCII one."""
    return _APOSTROPHE.sub("'", str(text or ""))


def normalize_lending_question(question: str) -> str:
    """Return a planner-friendly spelling without changing business meaning."""
    text = normalize_apostrophes(" ".join(str(question or "").split()))
    text = _INTEREST_TYPO.sub("interest", text)
    text = _DISBURSEMENT_TYPO.sub("disbursement", text)
    text = _HISTORY_TYPO.sub("history", text)

    if (
        _SCHEMA_WORD.search(text)
        and _LENDING_SCHEME_CONTEXT.search(text)
        and not _STRUCTURE_WORDS.search(text)
    ):
        text = _SCHEMA_WORD.sub("scheme", text)
    return text


__all__ = ["normalize_apostrophes", "normalize_lending_question"]
