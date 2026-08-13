"""Prompts, versioned.

`PROMPT_VERSION` is recorded on every audit row so eval scores stay attributable — a jump
in accuracy has to be traceable to the change that caused it.

The system prefix is a fixed string, byte-identical on every call, so llama.cpp reuses its
KV cache and time-to-first-token drops. Anything question-specific goes in a later message,
never spliced into the prefix.

Refusal exemplars carry as much weight here as the positive ones. A planner that answers
"will defaults rise next quarter?" with a confident number is worse than one that declines,
and the negative examples are what hold that line.
"""

from __future__ import annotations

from app.services.nlq.catalog import Catalog, get_catalog

PROMPT_VERSION = "planner-v2"

SYSTEM_PROMPT = """\
You translate questions about an Indian co-operative bank's lending book into structured \
queries. You never compute numbers, never state figures, and never write prose about \
results — a deterministic engine does that from the database.

DOMAIN
- Indian financial year: 1 April to 31 March, labelled by the ending year (FY26 = Apr 2025 \
to Mar 2026). Q1 is Apr-Jun.
- Money is in rupees, read as lakh (1e5) and crore (1e7).
- Sanctioned is what was approved; disbursed is what was actually released. They differ.
- DPD is days past due. PAR 30 is the share of principal outstanding on accounts more than \
30 days late. NPA is over 90 DPD.
- Products: 1 = Gold Loans, 13 = Microfinance / Retail EMI, 16 = Business & MSME.

RULES
- Use only metrics and dimensions from the catalog given below. Never invent one.
- Never invent a column, table or filter value.
- A question for one named borrower or account that cannot be expressed with catalog \
dimensions belongs on the "sql" route; do not refuse it merely because it contains a name.
- Choose ONE route and fill only that route's fields.
- Prefer refusing or clarifying over guessing. A wrong number is far more damaging than a \
question.

ROUTES
- "queryspec": the question maps onto catalog metrics and dimensions. Emit `spec` and \
`confidence`.
- "sql": the question is about data in the warehouse that the catalog's metrics do not \
cover. Emit `intent` and `tables`.
- "clarify": genuinely ambiguous. Emit `question` and up to 3 concrete `suggestions`. \
Use this when no metric is named ("show me the numbers"), when a term maps to two \
different metrics, or when "last year" could mean the financial or calendar year.
- "refuse": emit `reason`, and a short `message` only for a judgement about the question \
itself (predictive, advice, unsafe). Never describe what the warehouse does or does not \
contain, and never suggest alternative questions — the application supplies both from the \
catalog.
    - "predictive": any forecast, projection, or "will/likely to" question.
    - "advice": any "should we", recommendation, or strategy question.
    - "not_in_data": competitor data, macroeconomic data, or a breakdown the warehouse \
cannot support (for example GL balances by product — no such link exists).
    - "out_of_scope": not about this lending book at all.
    - "unsafe": any request to modify, delete or export data.

SHAPE
- Set `as_share` true only when the question asks for a mix, share, split or composition \
("what is our product mix", "what share of the book is gold", "break the portfolio down \
by asset class"). "Disbursement by branch" is a comparison, not a share — leave it false. \
It selects a part-to-whole chart and changes no numbers.

PERIODS
- When the user says "last 30 days", "last 90 days", or "last 12 months", emit the
corresponding relative period token. Never calculate or guess concrete dates for a relative
phrase.
- Default to "all_time" only when the question is explicitly about the whole book.
- "this year" in a banking context means the financial year: use "fy_to_date".
- Bare "last year" is ambiguous — clarify rather than picking one.
- A *named* financial year (FY24, FY26, "financial year 2025-26") is not a relative \
period. Emit explicit `start` and `end` dates: FY26 is 2025-04-01 to 2026-03-31, FY25 is \
2024-04-01 to 2025-03-31. Never map a named year onto "this_fy" or "fy_to_date" — those \
follow today's date and will silently answer about a different year.
"""


def catalog_block(catalog: Catalog | None = None) -> str:
    """The full metric and dimension list, compactly.

    Sent whole rather than retrieved. At roughly 1,400 tokens it fits the 4k budget with
    room to spare, and retrieval that drops the one metric the user meant costs a correct
    answer to save tokens there is no shortage of.
    """
    cat = catalog or get_catalog()
    lines = ["METRICS (id | what it measures | unit | grain)"]
    for metric in cat.metrics.values():
        synonyms = ", ".join(metric.synonyms[:6])
        lines.append(
            f"- {metric.id} | {metric.label}: {metric.formula} | {metric.unit} | "
            f"{metric.grain} | aka: {synonyms}"
        )

    lines.append("")
    lines.append("DIMENSIONS (id | group or filter by)")
    for dim in cat.dimensions.values():
        synonyms = ", ".join(dim.synonyms[:5])
        kind = "time" if dim.is_time else "category"
        lines.append(f"- {dim.id} | {dim.label} ({kind}) | aka: {synonyms}")

    lines.append("")
    lines.append("FILTER VALUES")
    for block in cat.enums.values():
        if block.dimension == "scheme":
            lines.append("- scheme: 4-digit codes; 16xx are MSME, 13xx microfinance, 10xx gold")
            continue
        pairs = ", ".join(f"{code}={value.label}" for code, value in list(block.values.items())[:20])
        lines.append(f"- {block.dimension}: {pairs}")

    lines.append("")
    lines.append("CANNOT BE ANSWERED")
    lines.append("- GL balances broken down by product, scheme or loan branch (no link exists)")
    lines.append("- GL figures by month or quarter (the ledger has annual grain only)")
    lines.append("- Anything about competitors, market share, or macroeconomic indicators")
    lines.append("- Any forecast, projection or recommendation")
    return "\n".join(lines)


FEW_SHOTS: list[tuple[str, str]] = [
    (
        "What was our disbursement by branch last quarter?",
        '{"route":"queryspec","confidence":0.95,"reasoning":"metric+dimension+period all explicit",'
        '"spec":{"metrics":["disbursement_total"],"dimensions":["branch"],'
        '"period":{"relative":"last_quarter"}}}',
    ),
    (
        "How many loans did we sanction each month in FY26?",
        # Explicit dates, not "last_fy": FY26 is only the previous fiscal year while today
        # happens to fall in FY27, and a few-shot that encodes today's calendar teaches the
        # model to answer about the wrong year every April.
        '{"route":"queryspec","confidence":0.93,"reasoning":"count over a monthly time axis",'
        '"spec":{"metrics":["loan_count"],"dimensions":["month"],'
        '"period":{"grain":"month","start":"2025-04-01","end":"2026-03-31"}}}',
    ),
    (
        "What is our product mix by outstanding?",
        '{"route":"queryspec","confidence":0.94,"reasoning":"composition, not comparison",'
        '"spec":{"metrics":["principal_outstanding"],"dimensions":["product"],'
        '"period":{"relative":"today"},"as_share":true}}',
    ),
    (
        "What is our PAR 30 right now?",
        '{"route":"queryspec","confidence":0.97,"reasoning":"point-in-time ratio, no breakdown",'
        '"spec":{"metrics":["par_30"],"period":{"relative":"today"}}}',
    ),
    (
        "How much have we disbursed in gold loans?",
        '{"route":"queryspec","confidence":0.9,"reasoning":"gold loans is product code 1",'
        '"spec":{"metrics":["disbursement_total"],'
        '"filters":[{"field":"product","op":"eq","value":"1"}],'
        '"period":{"relative":"all_time"}}}',
    ),
    (
        "What principal amount was paid by Sheelavati?",
        '{"route":"sql","intent":"cumulative principal repaid by borrower Sheelavati",'
        '"tables":["silver.loan_account_master"],"confidence":0.94,'
        '"reasoning":"named-borrower filter requires validated SQL"}',
    ),
    (
        "Compare this quarter's collections with last quarter",
        '{"route":"queryspec","confidence":0.92,"reasoning":"period comparison drives variance",'
        '"spec":{"metrics":["amount_collected"],"period":{"relative":"this_quarter"},'
        '"compare_to":{"relative":"last_quarter"}}}',
    ),
    (
        "Which branches have the worst collection efficiency?",
        '{"route":"queryspec","confidence":0.9,"reasoning":"ranking, ascending is worst-first",'
        '"spec":{"metrics":["collection_efficiency"],"dimensions":["branch"],'
        '"period":{"relative":"fy_to_date"},'
        '"order_by":{"field":"collection_efficiency","direction":"asc"}}}',
    ),
    (
        "Will defaults rise next quarter?",
        '{"route":"refuse","reason":"predictive","message":"I report what the loan book shows '
        'and do not forecast."}',
    ),
    (
        "Should we lend more to the MSME segment?",
        '{"route":"refuse","reason":"advice","message":"I do not make lending recommendations."}',
    ),
    (
        # No `message` here: the application writes it. Left to itself the model explains
        # the gap by describing a warehouse it cannot see, and gets it wrong.
        "Show me the GL balance by product",
        '{"route":"refuse","reason":"not_in_data"}',
    ),
    (
        "How did we do last year?",
        '{"route":"clarify","question":"Which measure did you mean, and does \\"last year\\" mean '
        'FY25 (Apr 2024-Mar 2025) or calendar 2025?","suggestions":['
        '"Disbursement in FY25","Collection efficiency in FY25",'
        '"Loans sanctioned in calendar 2025"]}',
    ),
    (
        "Show me the numbers by branch",
        '{"route":"clarify","question":"Which measure would you like broken down by branch?",'
        '"suggestions":["Disbursement by branch","Outstanding by branch",'
        '"Collection efficiency by branch"]}',
    ),
]


def build_messages(
    question: str,
    *,
    catalog: Catalog | None = None,
    repair_error: str | None = None,
    previous_attempt: str | None = None,
) -> list[dict[str, str]]:
    """Assemble the planner call.

    The system message is the fixed prefix (cacheable); the catalog block follows it
    unchanged for a given catalog version, so it also stays cache-warm across questions.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": catalog_block(catalog)},
    ]
    for user_text, assistant_json in FEW_SHOTS:
        messages.append({"role": "user", "content": user_text})
        messages.append({"role": "assistant", "content": assistant_json})

    messages.append({"role": "user", "content": question})

    if repair_error and previous_attempt:
        # One repair round-trip: the model sees its own output and the specific reason it
        # was rejected. Open-ended "try again" produces the same mistake.
        messages.append({"role": "assistant", "content": previous_attempt})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"That plan was rejected: {repair_error}\n"
                    "Emit a corrected plan using only catalog metrics and dimensions. "
                    "If it cannot be corrected, refuse or clarify instead."
                ),
            }
        )
    return messages


REWRITE_SYSTEM_PROMPT = """\
You rewrite a follow-up question into a complete, standalone one using the conversation so \
far. Change nothing else: keep the user's measure, period and filters unless they say \
otherwise. If the question already stands alone, return it unchanged with is_followup false.

Example:
  previous: "disbursement total for Q1 FY26"
  question: "and by branch?"
  -> {"question":"disbursement total for Q1 FY26 by branch","is_followup":true}
"""
