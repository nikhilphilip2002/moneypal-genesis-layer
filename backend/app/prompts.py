"""Prompt text. Refine these — the sharper the prompt, the better the brief."""

# --- Macro (Team A) --------------------------------------------------------
SNAPSHOT = (
    "Give a concise economic snapshot for a financial institution director. Cover: "
    "India's GDP growth (current FY), CPI inflation, RBI policy stance, overall and "
    "MSME credit growth, and the employment situation. 3 short paragraphs. "
    "Cite the document and data point for every number."
)

KARNATAKA = (
    "Write an executive briefing on Karnataka's economy for a co-operative bank "
    "expanding MSME lending. Cover: GSDP and growth, key sectors (IT, manufacturing, "
    "agriculture, services), MSME unit count and employment, financial inclusion, and "
    "active state/central MSME lending schemes. Focus on the lending opportunity: "
    "market size, who is underserved. Max 4 paragraphs."
)

MSME = (
    "Provide a strategic analysis of MSME lending trends for a Karnataka co-operative "
    "bank growing its MSME book. Cover: total MSME credit outstanding and growth, NPA "
    "levels, formal vs informal credit split, digital lending penetration, and the key "
    "barriers (collateral, thin credit files, documentation). Make it actionable."
)

BRIEFING = (
    "You are the Chief Intelligence Officer of Moneypal writing today's executive "
    "briefing for GICC's Director. Structure it exactly as: HEADLINE (one sentence on "
    "the most important development); MACRO CONTEXT (2 paragraphs); KARNATAKA FOCUS "
    "(1 paragraph on the local MSME lending opportunity); RISK WATCH (3 bullets); "
    "OPPORTUNITY (1 paragraph, what GICC should do). Be decisive and specific; use "
    "numbers; cite sources throughout."
)

# --- Competitive (Team B) --------------------------------------------------
LANDSCAPE = (
    "Give an executive overview of the Karnataka MSME lending landscape. Cover: "
    "major players and positioning; typical products and rate ranges; the most "
    "contested customer segments; market gaps / underserved areas; and the strategic "
    "implication for a co-operative bank (GICC). Be specific, not generic."
)
