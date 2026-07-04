"""Prompt text + retrieval queries.

Every widget has two parts:
  *_QUERIES — short data-seeking phrases embedded for vector search. These must
              read like the page we want back (numbers, scheme names), never
              like instructions.
  the prompt — instructions handed to the LLM together with retrieved context.

Output sections are written to answer the client blueprint directly:
who should we lend to, how much, what could go wrong, what opportunities exist.
"""

# --- Macro (Team A) --------------------------------------------------------

SNAPSHOT_QUERIES = [
    "India GDP growth rate current fiscal year projection",
    "CPI inflation rate RBI monetary policy repo rate stance",
    "bank credit growth micro small medium enterprises year-on-year",
    "gross non-performing assets NPA scheduled commercial banks asset quality",
    "employment formalisation labour workforce trend India",
]

SNAPSHOT = (
    "Write the India Economic Snapshot for GICC's leadership.\n"
    "Format exactly:\n"
    "GROWTH & INFLATION: GDP growth (current FY) and CPI inflation, with the RBI "
    "policy stance, each figure cited.\n"
    "CREDIT CONDITIONS: overall and MSME bank credit growth, banking asset quality "
    "(GNPA/NNPA), and what this means for a small co-operative lender.\n"
    "EMPLOYMENT & DEMAND: employment/formalisation trend and what it signals for "
    "borrower cash flows.\n"
    "SO WHAT FOR GICC: 2 sentences — the single most important implication for "
    "GICC's lending book this quarter.\n"
    "Maximum ~150 words. Every number cited (document, p.X)."
)

KARNATAKA_QUERIES = [
    "Karnataka gross state domestic product GSDP growth rate",
    "Karnataka MSME units registered employment districts",
    "MSME credit guarantee scheme PMEGP CGTMSE state government",
    "priority sector lending co-operative banks rural credit Karnataka",
    "MSME cluster development manufacturing services Karnataka Bengaluru",
]

KARNATAKA = (
    "Write the Karnataka Economic Landscape brief for GICC, a Karnataka co-operative "
    "bank growing MSME lending.\n"
    "Format exactly:\n"
    "STATE ECONOMY: GSDP, growth and dominant sectors, cited.\n"
    "MSME BASE: unit count, employment and where they cluster — this is WHO GICC "
    "can lend to.\n"
    "CREDIT GAP: where formal credit is thin (segments/geographies) — this is the "
    "OPPORTUNITY.\n"
    "SCHEME SUPPORT: active central/state schemes GICC can lend under, named and cited.\n"
    "Maximum ~160 words. If a Karnataka-specific figure is not in context, say so "
    "briefly rather than silently substituting an all-India number."
)

MSME_QUERIES = [
    "MSME credit outstanding growth bank lending trend",
    "MSME NPA delinquency delayed payments stress",
    "MSME formal informal credit gap unregistered enterprises finance",
    "digital lending fintech MSME loan disbursement technology",
    "MSME collateral free lending credit guarantee documentation barriers",
]

MSME = (
    "Write the MSME Lending Trends brief for GICC's credit committee.\n"
    "Format exactly:\n"
    "MARKET: MSME credit outstanding/growth and the sector's GDP and export share, cited.\n"
    "RISK SIGNALS: NPA/stress indicators and payment-delay dynamics — WHAT COULD GO "
    "WRONG for GICC's book, cited where sourced.\n"
    "UNDERSERVED DEMAND: the formal-vs-informal credit gap and digital-lending "
    "penetration — WHO IS NOT BEING SERVED.\n"
    "MOVES FOR GICC: exactly 3 numbered, concrete recommendations sized for a bank "
    "under Rs 500 crore (product, process, partnership).\n"
    "Maximum ~170 words. Never fabricate a number; a missing figure gets one clause."
)

BRIEFING_QUERIES = [
    "MSME credit growth outstanding bank lending India",
    "GDP growth inflation economic outlook India current year",
    "RBI policy rate stance banking asset quality NPA",
    "Karnataka MSME industry employment lending",
    "credit guarantee scheme MSME government support announcement",
]

BRIEFING = (
    "Write today's AI Executive Brief for GICC's Director.\n"
    "Format exactly:\n"
    "HEADLINE: one sentence — the single most decision-relevant development for a "
    "Karnataka MSME lender in the context. It must concern credit, growth, risk or "
    "regulation; never administrative or ceremonial content.\n"
    "MACRO CONTEXT: one short paragraph — growth, inflation, credit conditions, cited.\n"
    "KARNATAKA FOCUS: one short paragraph — the local MSME lending opportunity, cited.\n"
    "RISK WATCH: exactly 3 bullets — concrete risks to GICC's lending book, cited "
    "where sourced.\n"
    "OPPORTUNITY: one short paragraph — the specific move GICC should evaluate now.\n"
    "Maximum ~200 words. Decisive, numbers-first, no filler."
)

# --- Competitive (Team B) --------------------------------------------------

PROFILE_QUERIES = [
    "loan products interest rates ticket size MSME lending",
    "assets under management loan book portfolio financial results",
    "branches geographic presence districts customers served",
    "non-performing assets asset quality capital adequacy",
]

LANDSCAPE_QUERIES = [
    "MSME loan products interest rates lenders Karnataka",
    "co-operative bank rural credit membership deposits",
    "small business lending competition NBFC microfinance",
    "loan ticket size collateral security requirements",
]

LANDSCAPE = (
    "Write the Karnataka MSME Lending Landscape brief for GICC.\n"
    "Format exactly:\n"
    "PLAYERS & POSITIONING: who competes for Karnataka MSME borrowers and how they "
    "differ (rates, speed, reach), grounded in context.\n"
    "CONTESTED SEGMENTS: which borrower segments everyone is chasing.\n"
    "WHITE SPACE: underserved segments/geographies a sub-Rs 500 crore co-operative "
    "can win.\n"
    "GICC PLAY: 2-3 sentences on positioning.\n"
    "Maximum ~160 words. Specific institutions and figures only when in context."
)

SWOT_RULES = (
    "3-4 points per quadrant, each one line. Format:\n"
    "STRENGTHS:\n- ...\nWEAKNESSES:\n- ...\nOPPORTUNITIES:\n- ...\nTHREATS:\n- ...\n"
    "STRATEGIC OBSERVATION: 2-3 sentences on what GICC should do about this competitor."
)
