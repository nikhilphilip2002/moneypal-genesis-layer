"""Conservative spelling normalisation for lending questions.

The model is expected to understand ordinary variation, but two operational typos have a
disproportionate effect on routing:

* ``intrest`` misses the governed interest-rate/interest-paid vocabulary; and
* ``schema`` is frequently typed when the user means a loan *scheme*, which sends the
  workbench to the database-structure source instead of the loan book.

Only unambiguous corrections happen here.  In particular, ``schema`` remains untouched
when the question contains structural words such as table, column, relationship or join.
The original question is still retained in conversation history and audit records; this
normalised form is only what routing and planning read.
"""

from __future__ import annotations

import re

_INTEREST_TYPO = re.compile(r"\bint(?:r|er)?est\b|\bintrest\b", re.IGNORECASE)
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


def normalize_lending_question(question: str) -> str:
    """Return a planner-friendly spelling without changing business meaning."""
    text = " ".join(str(question or "").split())
    text = _INTEREST_TYPO.sub("interest", text)

    if (
        _SCHEMA_WORD.search(text)
        and _LENDING_SCHEME_CONTEXT.search(text)
        and not _STRUCTURE_WORDS.search(text)
    ):
        text = _SCHEMA_WORD.sub("scheme", text)
    return text


__all__ = ["normalize_lending_question"]
