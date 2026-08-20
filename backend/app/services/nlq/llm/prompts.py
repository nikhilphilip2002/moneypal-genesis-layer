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

import functools

import yaml

from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.catalog.loader import ACTIVE_DEFS_DIR

PROMPT_VERSION = "planner-v3"

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
- Use `filters` for row-level dimension conditions and `having` for conditions on an \
aggregated metric (for example borrowers whose total outstanding equals zero).
- A question for one named borrower or account that cannot be expressed with catalog \
dimensions belongs on the "sql" route; do not refuse it merely because it contains a name.
- A request to list or export specific catalog columns without asking for a metric belongs \
on the "sql" route. Never invent `loan_count` or another default metric merely to force a \
column-list request into queryspec.
- Questions naming a borrower, customer, agent or account are permitted during the current \
open-access rollout. Route them to queryspec or sql; never refuse them because they contain \
personal or staff-level detail.
- Choose ONE route and fill only that route's fields.
- Prefer refusing or clarifying over guessing. A wrong number is far more damaging than a \
question.

ROUTES
- "queryspec": the question maps onto catalog metrics and dimensions. Emit `spec` and \
`confidence`.
- "analysis": the question is broad — it asks how something is *doing* overall, or for a \
review, an overview, or several indicators at once, rather than for one number. Emit \
`analysis_id` (one of the ANALYSES below), plus `period` and `filters` only if the user \
named them. Prefer this over `queryspec` whenever a listed analysis covers the question: \
one metric cannot answer "how healthy is the book".
- "worklist": the question asks who to act on rather than what a number is — a list of \
accounts to call, chase, visit or review. Emit `worklist_id` (one of the WORKLISTS below), \
plus `filters` and `limit` only if the user named them. "Which branches have the worst \
arrears" is a queryspec; "give me today's collection list for Aluva" is a worklist.
- "briefing": the question is "what do I need to know?", "how are things this morning", \
"what needs my attention", "anything I should be worried about" — an open request for a \
read rather than for a number. Emit `persona_id`: the desk the question is being asked \
from (DESKS below), defaulting to `ceo` when the question names none.
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
    - "advice": any "should we", recommendation, or strategy question. Exception: "what \
should we do about these accounts" is a `worklist` — the recommended action there is the \
bank's own ratified collections policy, retrieved, not composed.
    - "not_in_data": competitor data, macroeconomic data, or a breakdown the warehouse \
cannot support (for example GL balances by product — no such link exists).
    - "out_of_scope": not about this lending book at all.
    - "unsafe": a request to modify or delete data. Read-only lists and exports are allowed.

SHAPE
- Set `as_share` true only when the question asks for a mix, share, split or composition \
("what is our product mix", "what share of the book is gold", "break the portfolio down \
by asset class"). "Disbursement by branch" is a comparison, not a share — leave it false. \
It selects a part-to-whole chart and changes no numbers.
- The application renders charts itself. Words such as donut, bar, line, graph, or chart are \
presentation requests, never a reason to refuse or claim that a graph cannot be displayed. \
For a donut request, reuse the requested metric and dimension and set `as_share` true.
- Keep amount metrics distinct from ratios: "overdue-principal share by asset classification" \
means `overdue_principal` grouped by `asset_class` with `as_share=true`; it is not PAR 30.
- Set `explain` true when the question asks WHY a measure moved rather than what it is \
("why are collections down", "what is driving the rise in PAR", "why did disbursement fall"). \
It requires `compare_to` and at least one dimension to attribute the change across — pick \
the dimension the question names, or `branch` when it names none. Asking why is not a \
forecast and not a recommendation, so it is never a refusal. "What is our PAR" is not an \
explanation; leave `explain` false.

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
    lines.append("ANALYSES (id | what it covers)")
    for definition in cat.analyses.values():
        summary = " ".join(definition.description.split())
        lines.append(f"- {definition.id} | {definition.title}. {summary}")
        if definition.synonyms:
            lines.append(f"    e.g. {'; '.join(definition.synonyms[:5])}")

    lines.append("")
    lines.append("WORKLISTS (id | who is on it)")
    for preset in cat.worklists.presets.values():
        summary = " ".join(preset.description.split())
        lines.append(f"- {preset.id} | {preset.title}. {summary}")
        if preset.synonyms:
            lines.append(f"    e.g. {'; '.join(preset.synonyms[:5])}")
    lines.append(
        "  A worklist filter can only name: "
        + ", ".join(sorted(_worklist_filterable()))
    )

    lines.append("")
    lines.append("CANNOT BE ANSWERED")
    lines.append("- GL balances broken down by product, scheme or loan branch (no link exists)")
    lines.append("- Anything about competitors, market share, or macroeconomic indicators")
    lines.append("- Any forecast, projection or recommendation")
    return "\n".join(lines)


_GOLD_YAML_FILES = (
    "tables.yaml",
    "columns.yaml",
    "metrics.yaml",
    "dimensions.yaml",
    "joins.yaml",
    "enums.yaml",
)


@functools.lru_cache(maxsize=4)
def _gold_yaml_for_version(version: str) -> str:
    """The active Gold catalog in a context-safe YAML projection.

    `columns.yaml` is deliberately compacted to table -> column names. Sending its full
    labels and repeated table names adds roughly 47 KB and exceeds the 32K context of the
    production Qwen model once instructions, examples and the output grammar are added.
    The projection still includes every governed column; text-to-SQL adds detailed labels,
    units and PII metadata for the question's retrieved tables separately.
    """
    sections = [
        "ACTIVE GOLD SEMANTIC CATALOG (authoritative YAML)",
        "Use every definition below when deciding answerability and constructing a plan. "
        "Only these Gold sources are available.",
    ]
    for name in _GOLD_YAML_FILES:
        path = ACTIVE_DEFS_DIR / name
        if name == "columns.yaml":
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            grouped: dict[str, dict[str, list[str]]] = {}
            for entry in raw:
                table = entry["table"]
                bucket = "pii" if entry.get("sensitivity") == "pii" else "columns"
                grouped.setdefault(table, {"columns": [], "pii": []})[bucket].append(
                    entry["column"]
                )
            lines = [
                "# Complete compact projection; PII columns are listed separately.",
            ]
            for table, columns in grouped.items():
                lines.append(f"- table: {table}")
                lines.append("  columns: [" + ", ".join(columns["columns"]) + "]")
                if columns["pii"]:
                    lines.append("  pii: [" + ", ".join(columns["pii"]) + "]")
            content = "\n".join(lines)
        else:
            content = path.read_text(encoding="utf-8")
        sections.extend((f"\n### {name}", "```yaml", content, "```"))

    # The presets, compactly. The route descriptions above say "one of the ANALYSES below"
    # and "one of the WORKLISTS below", and until these were appended there was no list
    # below — the schema enum stopped the model naming a preset that does not exist, but it
    # had no descriptions to choose between, so `portfolio_health` and `collections_focus`
    # were indistinguishable to it. The full YAML is not sent: a worklist's rule predicates
    # are SQL the model has no use for and would only crowd the context.
    catalog = get_catalog()
    sections.append("\n### ANALYSES (id | what it covers)")
    for definition in catalog.analyses.values():
        summary = " ".join(definition.description.split())
        sections.append(f"- {definition.id} | {definition.title}. {summary}")
        if definition.synonyms:
            sections.append(f"    e.g. {'; '.join(definition.synonyms[:5])}")

    sections.append("\n### WORKLISTS (id | who is on it)")
    for preset in catalog.worklists.presets.values():
        summary = " ".join(preset.description.split())
        sections.append(f"- {preset.id} | {preset.title}. {summary}")
        if preset.synonyms:
            sections.append(f"    e.g. {'; '.join(preset.synonyms[:5])}")
    sections.append(
        "  A worklist filter can only name: " + ", ".join(sorted(_worklist_filterable()))
    )

    sections.append("\n### DESKS (id | who is asking)")
    for persona in catalog.personas.values():
        sections.append(f"- {persona.id} | {persona.label}. {persona.description}")
        if persona.synonyms:
            sections.append(f"    e.g. {'; '.join(persona.synonyms[:5])}")

    return "\n".join(sections)


def gold_yaml_block(catalog: Catalog | None = None) -> str:
    cat = catalog or get_catalog()
    return _gold_yaml_for_version(cat.version)


FEW_SHOTS: list[tuple[str, str]] = [
    (
        "What was our total disbursement in July 2026?",
        '{"route":"queryspec","confidence":0.99,"reasoning":"explicit calendar month",'
        '"spec":{"metrics":["disbursement_total"],'
        '"period":{"start":"2026-07-01","end":"2026-07-31"}}}',
    ),
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
        "Show the overdue-principal share by asset classification today.",
        '{"route":"queryspec","confidence":0.98,"reasoning":"additive overdue amount as composition",'
        '"spec":{"metrics":["overdue_principal"],"dimensions":["asset_class"],'
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
        '"tables":["gold.loan_account_master"],"confidence":0.94,'
        '"reasoning":"named-borrower filter requires validated SQL"}',
    ),
    (
        "List branch name, IFSC code, branch status, opened date and closed date.",
        '{"route":"sql","intent":"list requested branch master attributes",'
        '"tables":["gold.branch_master"],"confidence":0.97,'
        '"reasoning":"specific columns requested without an aggregate metric"}',
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
    history_messages: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Assemble the planner call.

    The system message is the fixed prefix (cacheable); the complete Gold YAML follows it
    unchanged for a given catalog version, so it also stays cache-warm across questions.
    """
    # Qwen's llama.cpp chat template keeps only the first consecutive system message.
    # Gold comes first so planner and text-to-SQL share the same long KV-cache prefix;
    # their task-specific instructions follow inside that one system message.
    messages = [{
        "role": "system",
        "content": (
            gold_yaml_block(catalog)
            + "\n\nPLANNER TASK INSTRUCTIONS\n"
            + SYSTEM_PROMPT
        ),
    }]
    for user_text, assistant_json in FEW_SHOTS:
        messages.append({"role": "user", "content": user_text})
        messages.append({"role": "assistant", "content": assistant_json})

    messages.extend(history_messages or [])
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


def _worklist_filterable() -> list[str]:
    """The slices a worklist can honour. Imported lazily so the prompt module stays
    importable without the worklist service."""
    from app.services.worklists.rules import FILTERABLE

    return list(FILTERABLE)
