# Team C — Module 3: Regulatory Intelligence
**Port: 8000 (/regulatory) | Qdrant: one collection per regulation category | Duration: 24 Hours**

---

## Your Mission

Build the intelligence engine that answers: **"What RBI regulations apply to GICC and what do they need to do about each one?"**

You are building an executive compliance intelligence tool — not a legal database. Every output should be something a GICC Director or Policy Maker can read and use to make a decision or assign an action. Directors do not read regulation text. They need someone to translate it for them. That is your job.

---

## Your 3 API Endpoints

| Endpoint | Purpose | Used Where |
|----------|---------|------------|
| `GET /regulatory/categories` | List all regulation categories | Regulatory page accordion |
| `GET /regulatory/{category_id}` | Full regulation detail | Expanded accordion item |
| `GET /regulatory/alerts` | Active regulatory alerts | Dashboard widget |

---

## Shared Response Format (You Must Follow This)

Every endpoint returns exactly this structure. Copy the schema file from the Integration Lead before starting.

- **title** — name of the intelligence item
- **summary** — AI-generated executive summary (3–4 paragraphs max)
- **key_points** — 3 to 5 bullet points
- **source** — document name + URL back to original source
- **ai_note** — one sentence distinguishing AI interpretation from sourced fact
- **last_updated** — today's date
- **confidence** — high / medium / low

---

---

## HOUR 0–2: Setup (With All Teams)

- Install all Python packages: fastapi, uvicorn, qdrant-client, sentence-transformers, groq, python-dotenv, pypdf
- Download bge-m3 model — run the download script the Integration Lead provides. This is 570MB, do it now
- Set up `.env` file with `GROQ_API_KEY` and Qdrant host/port
- Confirm FastAPI starts and returns 200 on `/health`
- Pull the shared schema from the repo

---

## HOUR 2–4: Build the Regulation Config System

Same principle as Team B's institution config — every regulation category is defined by a JSON file. Adding a new regulation category means dropping a JSON file, not changing Python code.

---

### JSON Structure for Each Regulation Category

Each file must contain these fields:

- **id** — URL-safe slug (e.g. `digital_lending`, `master_directions`, `kyc_aml`)
- **display_name** — Human-readable name shown in the UI
- **category** — Same as id, for grouping
- **rbi_url** — Direct URL to the RBI page for this regulation
- **source_doc** — Filename of the PDF in your `data/` folder
- **qdrant_collection** — Name of the Qdrant collection (e.g. `reg_digital_lending`)
- **applicability** — Who this applies to (one sentence)
- **effective_date** — When this regulation came into effect (YYYY-MM-DD format)
- **priority** — high / medium / low (how urgently does GICC need to act)

---

### The 9 Regulation Categories — Create a JSON for Each

**1. NBFC Master Directions**
- display_name: "NBFC Master Directions"
- id: `master_directions`
- rbi_url: URL provided in the buildathon brief (rbi.org.in/scripts/BS_ViewMasterDirections.aspx?did=411)
- applicability: All NBFCs registered with RBI including those below ₹500 crore asset size
- priority: high
- collection: `reg_master_directions`

**2. Prudential Norms**
- display_name: "Prudential Norms for NBFCs"
- id: `prudential_norms`
- rbi_url: rbi.org.in Master Directions on Prudential Norms
- applicability: NBFCs — capital adequacy, income recognition, asset classification, provisioning
- priority: high
- collection: `reg_prudential_norms`

**3. Fair Practices Code**
- display_name: "Fair Practices Code"
- id: `fair_practices`
- rbi_url: RBI Fair Practices Code directions
- applicability: All NBFCs — governs how they deal with borrowers
- priority: medium
- collection: `reg_fair_practices`

**4. KYC / AML**
- display_name: "KYC and Anti-Money Laundering"
- id: `kyc_aml`
- rbi_url: RBI KYC Master Directions
- applicability: All NBFCs — customer identification, verification, monitoring
- priority: high
- collection: `reg_kyc_aml`

**5. Digital Lending Guidelines**
- display_name: "Digital Lending Guidelines"
- id: `digital_lending`
- rbi_url: rbi.org.in Digital Lending Guidelines 2022
- applicability: NBFCs engaged in digital lending or using Lending Service Providers (LSPs)
- priority: high
- collection: `reg_digital_lending`

**6. Outsourcing Guidelines**
- display_name: "Outsourcing of Financial Services"
- id: `outsourcing`
- rbi_url: RBI guidelines on outsourcing
- applicability: NBFCs that outsource any financial or operational function
- priority: medium
- collection: `reg_outsourcing`

**7. Corporate Governance**
- display_name: "Corporate Governance Norms"
- id: `governance`
- rbi_url: RBI Corporate Governance directions for NBFCs
- applicability: All NBFCs — board composition, committees, disclosures
- priority: medium
- collection: `reg_governance`

**8. Information Security**
- display_name: "Information Security and Cyber Resilience"
- id: `information_security`
- rbi_url: RBI Information Security directions
- applicability: All NBFCs — IT systems, cyber resilience framework, data protection
- priority: high
- collection: `reg_information_security`

**9. Circulars and Notifications**
- display_name: "Recent RBI Circulars"
- id: `circulars`
- rbi_url: rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx
- applicability: Current-year circulars relevant to NBFCs below ₹500 crore
- priority: medium
- collection: `reg_circulars`

---

## HOUR 4–7: Data Collection

**Primary source for everything:** Reserve Bank of India — rbi.org.in

All regulation documents are freely available on the RBI website. Your job is to find and download the right PDFs.

---

### Documents to Download

**Essential — Must Have**

**1. NBFC Master Directions (Non-Banking Financial Company — Non-Systemically Important Non-Deposit taking Company)**
- Go to: rbi.org.in → Regulations → Master Directions
- The direct URL is provided in the buildathon brief
- This is the main governing document for NBFCs below the systemically important threshold
- Save as: `rbi_nbfc_master_directions.pdf`
- This single PDF covers prudential norms, governance, fair practices, and more

**2. RBI Digital Lending Guidelines 2022**
- Search: "RBI digital lending guidelines 2022 pdf"
- Circular issued September 2, 2022
- Save as: `rbi_digital_lending_2022.pdf`
- Covers: Lending Service Providers, Key Fact Statement, first loss default guarantee, data privacy

**3. KYC Master Directions (Updated)**
- Go to: rbi.org.in → Master Directions → Know Your Customer
- Search for the most recent update (2023 or 2024)
- Save as: `rbi_kyc_master_directions.pdf`
- Covers: CIP, CDD, Video KYC (V-CIP), Aadhaar-based KYC, AML monitoring

**4. Information Technology Framework for NBFCs / Cyber Security Framework**
- Search: "RBI IT framework NBFC pdf" or "RBI cyber security circular NBFC"
- Save as: `rbi_it_framework_nbfc.pdf`

**5. Fair Practices Code for NBFCs**
- Search: "RBI fair practices code NBFC master directions"
- Covers loan application, appraisal, disbursement, interest rates, grievance redressal
- Save as: `rbi_fair_practices_code.pdf`

**Good to Have — Get If Time Allows**

**6. Outsourcing Guidelines**
- Search: "RBI guidelines on outsourcing of financial services NBFC pdf"
- Save as: `rbi_outsourcing_guidelines.pdf`

**7. Corporate Governance Directions**
- Search: "RBI NBFC corporate governance directions 2023 pdf"
- Save as: `rbi_corporate_governance.pdf`

**8. Recent RBI Circulars (2023–2024)**
- Go to: rbi.org.in → Notifications → Circulars
- Filter to NBFCs, last 12 months
- Download 3–5 relevant circulars, save as individual PDFs or combine into `rbi_recent_circulars.pdf`

---

### Tips for RBI Website Navigation

- The RBI website can be slow. Use Google to find direct PDF links: "site:rbi.org.in NBFC master directions pdf"
- Master Directions are long documents — they cover multiple topics. One PDF may cover multiple regulation categories (this is fine, index it into each relevant collection)
- If a PDF cannot be found, go to rbi.org.in → Press Releases and search for the regulation name

---

### Data Collection Split (2 People)

**Person 1:** Master Directions, Digital Lending, KYC/AML, Information Security
**Person 2:** Fair Practices, Outsourcing, Governance, Circulars, and help with ingestion

---

## HOUR 7–9: Ingestion

We go Direct — no RAG framework. The pipeline is:

1. **Load** — read each PDF using pypdf, extract text page by page
2. **Chunk** — split into ~600-word segments with ~80-word overlap. Use larger chunks than other modules because RBI legalese needs more surrounding context to make sense
3. **Embed** — pass each chunk through bge-m3 via sentence-transformers → 1024-dimension vector. bge-m3's 8192-token window is critical here — RBI documents are dense and you need large chunks to avoid cutting requirements mid-sentence
4. **Store** — upsert vector + chunk text + metadata (regulation category, source PDF, page number) into that category's Qdrant collection

Use the shared `rag_helpers.py` from the Integration Lead for embed and store functions.

**Note on the Master Directions PDF:** It is a large document covering multiple categories. You can index the same PDF into multiple Qdrant collections (e.g. both `reg_master_directions` and `reg_prudential_norms`). This is fine — the collection scoping ensures each query only retrieves relevant chunks.

For each category:
1. Confirm source PDF is in `backend/data/regulatory/`
2. Run ingestion: `python scripts/ingest.py regulatory`
3. Test: embed "What are GICC's compliance requirements for digital lending?" → search Qdrant → verify returned chunks are from the right document

---

## HOUR 9–14: Build the 3 Endpoints

---

### Endpoint 1: `GET /regulatory/categories` — Category List

This endpoint does not need RAG. It reads all JSON files from your `regulations/` folder and returns a summary list.

**Returns for each category:**
- id
- display_name
- applicability
- effective_date
- priority (high/medium/low)
- rbi_url

**This is how the frontend draws the regulatory accordion list.** No AI involved.

---

### Endpoint 2: `GET /regulatory/{category_id}` — Regulation Detail

**What the frontend shows:** When a user expands a regulation in the accordion, this is what they see. The most important endpoint in your module.

**For the given category, run RAG and generate a response structured in exactly these 5 sections:**

---

**EXECUTIVE SUMMARY**
2–3 sentences maximum. What is this regulation? What is its purpose? Why did RBI issue it?

Example: "RBI's Digital Lending Guidelines 2022 regulate the use of digital platforms and third-party Lending Service Providers (LSPs) by NBFCs. The guidelines were issued to protect borrowers from predatory digital lending practices and ensure transparency in loan processing and collections."

---

**APPLICABILITY**
Who does this apply to? Be specific about whether it applies to NBFCs below ₹500 crore. Most RBI Master Directions apply to all registered NBFCs regardless of size — say so clearly if that is the case.

Also clarify: does it apply to GICC specifically based on their operations? (e.g. Digital Lending guidelines apply if they use any app, website, or LSP for loan processing — which most modern institutions do)

---

**BUSINESS IMPACT**
What does GICC need to change or comply with? Be operational and specific. Do not summarise the regulation — translate it into business actions.

Bad: "The regulation requires NBFCs to maintain proper records."
Good: "GICC must issue a Key Fact Statement (KFS) to every borrower before loan disbursement, disclosing the Annual Percentage Rate (APR), total cost of credit, and all fees. This requires updating the loan application workflow and borrower communication process."

Cover 3–5 specific operational impacts. If a requirement involves a cost or process change, say what that change is.

---

**COMPLIANCE ACTIONS**
A checklist of 4–6 specific actions GICC must take. These should be directly actionable — something that can be assigned to a team member.

Format each as a clear action verb:
- "Appoint a Nodal Officer for Digital Lending grievance redressal"
- "Implement a Key Fact Statement (KFS) in loan application workflow"
- "Review all LSP agreements for compliance with RBI data privacy requirements"
- "Train collections team on RBI-prescribed fair debt collection practices"

---

**EFFECTIVE DATE**
Pull this from your JSON config. State it clearly. If there have been amendments, note the most recent amendment date.

---

**Prompt direction:** Frame every prompt as a compliance briefing for the Director and Policy Maker of GICC, a Karnataka co-operative bank with assets below ₹500 crore. Translate legal language into business language. Be specific about what they must do, not just what the regulation says.

**Confidence:** high (RBI documents are authoritative)

**Source:** Always cite the specific RBI document and its direct URL from rbi.org.in

**ai_note example:** "Summary generated from RBI Digital Lending Guidelines circular dated September 2, 2022 (RBI/2022-23/111). Compliance actions are AI interpretation of regulatory requirements and should be validated with a qualified compliance officer."

---

### The 9 Regulation Detail Prompts — What Each Must Cover

---

**`/regulatory/master_directions`**
Cover: Minimum owned fund requirements, registration requirements, capital adequacy ratio, leverage ratio, income recognition norms, asset classification, provisioning norms. Focus on what a sub-₹500 crore NBFC must maintain day-to-day.

---

**`/regulatory/prudential_norms`**
Cover: CRAR (Capital to Risk-weighted Assets Ratio) requirement of 15%, asset classification into standard/sub-standard/doubtful/loss categories, provisioning percentages for each category, income recognition rules for NPAs.

---

**`/regulatory/fair_practices`**
Cover: Loan application processing requirements, written appraisal communication to borrowers, interest rate disclosure, prepayment penalty rules, grievance redressal mechanism, prohibition on harassment in collections, annual statement of accounts to borrowers.

---

**`/regulatory/kyc_aml`**
Cover: Customer Identification Procedure (CIP), Customer Due Diligence (CDD) requirements, Aadhaar-based KYC acceptance, Video KYC (V-CIP) option, Periodic KYC refresh requirements, suspicious transaction reporting to FIU-IND, PMLA compliance. Note that V-CIP is now an accepted option and reduces in-person branch visits.

---

**`/regulatory/digital_lending`**
Cover: Lending Service Provider (LSP) registration and oversight responsibilities, Key Fact Statement (KFS) mandatory disclosure, Annual Percentage Rate calculation and disclosure, prohibition on automatic credit limit increases, first loss default guarantee (FLDG) framework, data collection and privacy requirements for apps, loan account statements must be available digitally.

---

**`/regulatory/outsourcing`**
Cover: Which functions can and cannot be outsourced, NBFC retains responsibility even when outsourced, due diligence on service providers, exit clauses in contracts, RBI's right to inspect outsourced service providers, data security in outsourcing arrangements.

---

**`/regulatory/governance`**
Cover: Board composition requirements (independent directors, women directors), mandatory board committees (Audit, Risk, Nomination, Remuneration, IT Strategy for larger NBFCs), board-level oversight of compliance, CEO appointment process and RBI approval if needed, related party transaction policies.

---

**`/regulatory/information_security`**
Cover: Board-approved Information Security policy requirement, cyber resilience framework, IT governance structure, incident reporting timeline to RBI (within 2–6 hours of major cyber incident), data backup and recovery requirements, vendor risk management for IT vendors, business continuity planning.

---

**`/regulatory/circulars`**
Cover: Summarise the 3–5 most recent RBI circulars relevant to NBFCs below ₹500 crore from the past 12 months. Each circular should have: what changed, who it applies to, what the deadline is.

---

### Endpoint 3: `GET /regulatory/alerts` — Regulatory Alerts Widget

**What the frontend shows:** A column of coloured alert cards on the GICC Director's dashboard. This is the most visible part of your module.

**This endpoint returns a hardcoded list of 4–5 alerts.** No RAG needed. These are pre-written, carefully crafted alert cards that highlight the most pressing regulatory items for GICC.

**Each alert must contain:**
- **title** — short, punchy headline (max 8 words)
- **category** — links to a regulation category id
- **severity** — `high` or `medium`
- **summary** — one sentence explaining the issue
- **action** — one sentence on what GICC must do
- **deadline** — if applicable
- **source_url** — link to the RBI source
- **ai_note** — one line on where this comes from

---

### 5 Alerts to Include

**Alert 1 — High Severity**
Title: "Digital Lending LSP Agreements Review Due"
Summary: RBI requires all NBFC-LSP agreements to include specific data privacy and grievance clauses.
Action: Review all Lending Service Provider contracts for RBI compliance by next board meeting.
Source: Digital Lending Guidelines 2022

**Alert 2 — High Severity**
Title: "KYC Refresh — Periodic CDD Required"
Summary: RBI mandates periodic re-KYC for all customers based on risk categorisation (low/medium/high risk).
Action: Audit current customer KYC database and schedule re-KYC for overdue accounts.
Source: KYC Master Directions

**Alert 3 — High Severity**
Title: "Cyber Incident Reporting — 2-Hour Window"
Summary: RBI requires NBFCs to report major cyber security incidents within 2–6 hours of detection.
Action: Verify incident response procedure has the RBI reporting step within the 2-hour window.
Source: Information Security Directions

**Alert 4 — Medium Severity**
Title: "Key Fact Statement Mandatory for All Loans"
Summary: Every loan disbursement must be preceded by a KFS disclosing APR, fees, and all charges.
Action: Update loan origination workflow to generate and obtain borrower acknowledgment of KFS.
Source: Digital Lending Guidelines 2022

**Alert 5 — Medium Severity**
Title: "Board Approval for IT Security Policy Required"
Summary: All NBFCs must have a board-approved Information Security policy in place.
Action: Place Information Security Policy on next board agenda for formal approval and documentation.
Source: RBI Information Security Directions

---

## HOUR 14: Handoff to Integration Lead

### Handoff Checklist

**Config System**
- [ ] All 9 regulation categories have a JSON config file in [backend/registry/regulations/](file:///home/null/Projects/moneypal/backend/registry/regulations/) folder
- [ ] Every JSON has a valid `rbi_url` linking to the actual RBI page
- [ ] Every JSON has a correct `effective_date`

**Response Format**
- [ ] `/regulatory/categories` lists all 9 categories correctly
- [ ] `/regulatory/{id}` follows the 5-section structure: Executive Summary, Applicability, Business Impact, Compliance Actions, Effective Date
- [ ] `/regulatory/alerts` returns at least 4 well-formatted alert cards
- [ ] All responses use the shared schema format

**Content Quality**
- [ ] Business Impact section is specific and operational — not a restatement of the regulation
- [ ] Compliance Actions are actionable bullet points with clear verbs
- [ ] At least 5 of the 9 regulation categories have working detail endpoints
- [ ] Alerts have both `summary` and `action` fields — not just descriptions

**Technical**
- [ ] CORS is open — Integration Lead can call your API from localhost:3000
- [ ] `/health` returns 200
- [ ] All endpoints return 200 (no 500 errors)
- [ ] Working inside [regulatory.py](file:///home/null/Projects/moneypal/backend/app/api/routes/regulatory.py) and [regulatory.py](file:///home/null/Projects/moneypal/backend/app/services/regulatory.py)
- [ ] Response time under 30 seconds

---

## Common Mistakes to Avoid

**Mistake 1: Summarising the regulation instead of translating it**
Bad: "The regulation states that NBFCs must maintain a Key Fact Statement."
Good: "GICC must generate a KFS for every borrower before disbursement, showing the exact APR including all fees. This means updating the loan application system and training the operations team."

**Mistake 2: Generic compliance actions**
Bad: "Ensure compliance with all regulatory requirements."
Good: "Appoint a dedicated KYC officer responsible for V-CIP operations and periodic CDD reviews."

**Mistake 3: Missing source URLs**
Every response must link to the specific RBI document URL. If a judge clicks the source and it leads nowhere, it undermines the whole module.

**Mistake 4: Skipping the ai_note**
The brief explicitly states every AI insight must distinguish factual information from AI interpretation. The ai_note is non-negotiable. It is an evaluation criterion.

**Mistake 5: Covering only 3 of the 9 categories**
Aim for all 9. If time runs short, prioritise in this order: master_directions, digital_lending, kyc_aml, information_security, prudential_norms, fair_practices, governance, outsourcing, circulars.

**Mistake 6: Ignoring the sub-₹500 crore context**
The brief is explicit: GICC is an NBFC with assets below ₹500 crore. Some RBI requirements only kick in above this threshold. Your prompts must always ask the RAG engine to filter for what applies to smaller NBFCs. This context matters to the judges.

---

## What a Winning Response Looks Like

The judges will login as GICC Policy Maker, open the Regulatory page, and click on Digital Lending. They will read:

1. An Executive Summary that explains in two sentences what the guideline does and why RBI issued it
2. A Business Impact section that tells them specifically what GICC needs to change — not what the regulation says in general
3. A Compliance Actions checklist they could hand to a team member tomorrow morning
4. A source link that opens the actual RBI circular

Then they will check the dashboard and see the Regulatory Alerts widget with 4–5 sharp, specific alerts — each with a clear action and severity colour.

If the Compliance Actions are specific and operational, and every item links back to an RBI source, you have won Module 3.

---

## Quick Reference — RBI Website Navigation

| What You Need | Where to Find It |
|---------------|-----------------|
| Master Directions | rbi.org.in → Regulations → Master Directions |
| Recent Circulars | rbi.org.in → Notifications → Circulars |
| Press Releases | rbi.org.in → Press Releases |
| FAQs on specific topics | rbi.org.in → FAQs |
| Financial Stability Report | rbi.org.in → Publications → Financial Stability Reports |
| NBFC-specific page | rbi.org.in → Regulations → Non-Banking |
