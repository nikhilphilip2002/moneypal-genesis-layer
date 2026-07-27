# Genesis Intelligence Console — Client Presentation Walkthrough

A screen-by-screen guide to the Moneypal × GICC **Genesis Intelligence Console**: what every page, card, and tab represents, and the story to tell while presenting it.

---

## 1. Login — One Console, Four Roles

The login page carries joint **Moneypal × GICC** branding and positions the product as *"A joint onboarding environment for Moneypal Digital Services and GICC."*

The key message: **everyone signs in through the same door, but each person sees only the workspace built for their job.** After sign-in, the console reads the user's role and lands them directly on their home page.

| # | Role | Who they are | Purpose | Pages they see | Lands on |
|---|------|--------------|---------|----------------|----------|
| 1 | **Moneypal Administrator** (`admin`) | Moneypal's platform operator | Runs the platform: system health, client onboarding, intelligence registries | Dashboard, Macro, Competitive, Regulatory, Admin | Executive Dashboard |
| 2 | **GICC Administrator** (`gicc_admin`) | GICC's internal owner of the tool | Reviews and quality-controls the AI intelligence before leadership relies on it | Dashboard, Competitive, Regulatory, Review | Executive Dashboard |
| 3 | **GICC Policy Maker** (`gicc_policy`) | Drafts lending & compliance policy | Turns regulatory + competitive evidence into policy briefs | Regulatory, Competitive, Policy Workspace | Regulatory Intelligence |
| 4 | **GICC Director** (`gicc_director`) | Board / executive leadership | Consumes a single decision-ready summary — no operational noise | Executive Dashboard only | Executive Dashboard |

Talking point: role-based access is enforced on every page — if a Policy Maker types the dashboard URL, they are redirected to their own workspace.

---

## 2. Executive Dashboard (`/`) — "What GICC leadership should know today"

The home page for Directors, GICC Admins, and Moneypal Admins. Every insight on it is traced back to its source document. Laid out top to bottom:

### Ask Genesis (search bar)
Sits at the top of the dashboard. Two modes in one box:
- **Ask** — type a natural-language question ("What are the digital lending disclosure requirements for GICC?") and Genesis answers in plain language, grounded in the ingested RBI documents, with citations.
- **Search** — returns the raw source excerpts themselves, so users can see *exactly* which document passages the AI is reading. This is the "explainability" proof point.

### Row 1 — AI Briefings
- **AI Executive Brief** (large card, ⅔ width): the hero element. A daily AI-written executive briefing synthesising macro, competitive, and regulatory intelligence. Carries a **confidence badge** and a refresh button to regenerate on demand.
- **Regulatory Alerts** (⅓ width): a prioritized list of RBI alerts. Each row shows the title plus a **High / Medium / Low severity badge**; clicking expands it in place to show the summary, the **required action**, a direct **link to the RBI source document**, and an AI note.

### Row 2 — Strategic Insights
- **Economic Snapshot**: current Indian macro-economic picture (growth, rates, credit conditions), distilled into a briefing card.
- **Karnataka Lending Landscape**: how GICC's competitive environment in Karnataka MSME lending looks right now.

### Row 3 — Activity & Follow-ups
- **Recently Updated Intelligence**: a feed of the latest refreshed briefings across the three modules (Macro / Competitive / Regulatory), each with a "3h ago"-style timestamp and a deep link to the relevant page.
- **Action Items**: concrete to-dos derived from the intelligence (e.g. a compliance step from a new RBI direction), each with a **High / Medium priority badge** and a link to the page where it can be acted on.

---

## 3. Macro-economic Intelligence (`/macro`)

*"India's macro economy and Karnataka's MSME lending landscape, distilled for GICC leadership."*

- **AI Executive Brief** (full width): a macro-focused executive briefing.
- Three side-by-side intelligence cards:
  1. **Economic Snapshot** — national indicators relevant to a lender (growth, inflation, rate environment).
  2. **Karnataka Economy** — state-level view, since GICC operates in Karnataka.
  3. **MSME Lending Trends** — credit flow and demand trends in GICC's core segment.

Purpose in the story: this is the *context layer* — before looking at competitors or regulation, leadership sees the economic weather they're lending into.

---

## 4. Competitive Intelligence (`/competitive`)

*"Profiles and AI-generated SWOT analysis of Karnataka's MSME lending institutions."*

- **Search + filter bar**: search institutions by name; filter by institution type (Co-operative Bank, NBFC, Small Finance Bank, …).
- **Institution grid**: one card per competitor showing name, type, headquarters, and an **"MSME focus"** badge where relevant.
- **Click a card → slide-out brief** with two sections:
  1. **Institution Profile** — an AI-generated briefing on that competitor (products, positioning, recent moves), source-cited.
  2. **SWOT Analysis** — an automated Strengths / Weaknesses / Opportunities / Threats card for that institution.

Key talking point: the competitor list is **config-driven** — the Moneypal Admin can add a new institution from the Admin page and it appears here with no software change.

---

## 5. Regulatory Intelligence (`/regulatory`)

*"RBI regulations applicable to NBFCs below ₹500 crore, translated into business actions for GICC."*

- A vertical list of **regulation category rows** (e.g. Digital Lending, KYC/AML, Fair Practices). Each collapsed row shows:
  - the regulation name,
  - who it applies to and its effective date,
  - a **High / Medium / Low priority badge**,
  - a direct **"RBI source"** link to the official circular.
- **Expanding a row** reveals the full AI briefing for that category: what the regulation says, what it means for GICC specifically, and what actions it implies.

Purpose in the story: compliance teams don't read 80-page circulars — the console translates them into GICC-specific business actions, while keeping the official source one click away.

---

## 6. Policy Workspace (`/policy`) — GICC Policy Maker's home

*"Formulate policy from evidence."* A two-panel workbench:

**Left — evidence selection:**
- **Regulatory inputs**: checkbox list of regulation categories to ground the policy in.
- **Competitive inputs**: checkbox list of competitor institutions to benchmark against.
- **Policy focus**: a free-text question, e.g. *"Should GICC introduce collateral-free digital MSME loans under ₹10 lakh?"*

**Right — generated brief:**
- Pressing **"Generate policy brief"** produces a grounded, source-cited draft policy brief in the same executive-brief format (title, summary, sources, AI note, confidence).
- A **"Copy brief"** button exports it to the clipboard for use in board papers or policy documents.

Purpose in the story: this is where intelligence becomes *output* — evidence in, defensible policy draft out, with citations attached.

---

## 7. Intelligence Review (`/review`) — GICC Administrator's workspace

Human oversight of the AI. A list of every AI-generated briefing across the modules, each with a status badge:

- **Pending review** (amber) — not yet checked by a human.
- **Reviewed** (green) — verified as accurate.
- **Flagged for attention** (red) — a concern was raised.

Expanding an item lets the reviewer set the status and attach a **reviewer note** (accuracy concerns, follow-ups, source questions) with a save action.

Purpose in the story: the AI never operates unsupervised — GICC's own administrator signs off on the intelligence leadership consumes. This is the governance/trust slide.

---

## 8. Platform Administration (`/admin`) — Moneypal Administrator only

Three tabs:

### Tab 1 — Platform
- **Users & roles**: table of all provisioned users with their role and email — demonstrates the four-role access model live.
- **System health**: live status of the stack — vector store (Qdrant) connectivity, the LLM model in use, the embeddings model, and counts of institution/regulation configs. Green/red dots show at a glance that everything is up.

### Tab 2 — Client Onboarding
- The **GICC client card** with its onboarding status, and the three-phase **Genesis journey**:
  1. **Institutional Intelligence** *(current phase — this product)*: macro, competitive and regulatory intelligence via the Aroha RAG framework.
  2. **Prosper & Tally Migration** *(upcoming)*: migrating operational data into Canonical Business Objects.
  3. **NEST Platform** *(upcoming)*: aggregate block creation, BI, RIM and DNBS reporting.

  This tab is the roadmap slide — it shows the client where this console sits in the larger Moneypal engagement.

### Tab 3 — Intelligence Management
- **Institution registry** and **Regulation registry** tables, each showing whether the entry's documents are **indexed** (with vector counts) or **not ingested** yet.
- **"Add institution"** and **"Add regulation"** dialogs: filling a short form writes a config file — no code change — after which the entry's PDFs are ingested and it lights up across the whole console.

Purpose in the story: proves the platform is **config-driven and scalable** — onboarding a new competitor or regulation is minutes of admin work, not a development cycle.

---

## 9. Elements That Appear Everywhere (worth pointing out once)

- **Source citations**: every AI card names the source document and links to the original (usually an official RBI URL). Nothing is unattributed.
- **Confidence badge**: briefs display the AI's confidence level, setting honest expectations.
- **AI note**: a short caveat/context line on generated content.
- **Refresh**: any briefing can be regenerated on demand; otherwise responses are served from a smart cache so pages load instantly and stay consistent.
- **Loading & error states**: every widget degrades gracefully with skeleton loaders and a retry button — no blank screens during the demo.
- **Responsive + PWA**: the console adapts to mobile with its own tab bar, and can be installed as an app.
- **Light/dark theme** toggle.

---

## Suggested Demo Order

1. **Login** — introduce the four roles (one slide).
2. Sign in as **Director** — show the Executive Dashboard end-to-end, including Ask Genesis.
3. Sign in as **Policy Maker** — Regulatory → Competitive → generate a live policy brief.
4. Sign in as **GICC Admin** — show the Review workspace (governance).
5. Sign in as **Moneypal Admin** — Admin tabs: health, the Genesis journey roadmap, and add an institution live to prove config-driven scaling.
