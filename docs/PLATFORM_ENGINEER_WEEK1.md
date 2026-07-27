# Platform Engineer — Week 1 Role & Work Plan (Plain-English Guide)

**Who this is for:** You — the person who built the Moneypal app that already exists in this repo, and who is now the 5th person on the Genesis Layer / NEST team alongside 4 engineers.

**Goal of this document:** Answer, in plain language, "what do I actually do this week, day by day, and how do I relate to the 4 engineers?"

---

## 1. The one-paragraph version

The 4 engineers are each designing **one piece of paper** this week — a spec, a schema, a diagram. None of them are responsible for making sure those 4 pieces of paper actually turn into a **working system that runs on a real server**, or for making sure this new work doesn't break the app you already built and shipped. That gap is you. You are not one of the 4 engineers designing a piece of the new architecture — you are the person who makes sure all 4 pieces fit together, run somewhere real, and don't break what's already live. Think of yourself as **the general contractor** on a house where 4 specialists (electrician, plumber, framer, roofer) are each drawing their own blueprint this week — you're the one who has to make sure the blueprints agree with each other and that there's an actual foundation and site for them to build on.

---

## 2. Are you "coordinating" the 4 engineers?

**Partially — but not as their manager.** Here's the precise answer:

- **You do NOT manage them.** You don't assign their tasks, review their technical decisions as an authority, or approve their designs. That's the Program Manager's and/or architecture lead's job (see the questions for the PM at the bottom — this is exactly one of the things to confirm).
- **You DO coordinate with them, constantly, in a specific way:** you are the shared dependency all 4 of them run into. Every one of them, at some point this week, needs something from you or needs to hand you something:
  - Engineer 1 (NAB Platform Lead) needs a database to actually store the JSON schema he's designing — that's your Postgres instance.
  - Engineer 2 (Genesis Mapping Lead) needs to know what field names and structures Engineer 1 chose, and you're often the one who notices when two people's specs don't line up, because you're the one trying to wire them together.
  - Engineer 3 (Import Framework Lead) needs somewhere to actually drop sample CSV files and test that they parse correctly — that's your environment.
  - Engineer 4 (Intelligence & Reporting Lead) needs a vector store and an LLM connection to prototype "Moneypal Genie" — you already have a Qdrant vector database running (see `docker-compose.yml`), so you're the one who tells them "yes, use this one" or sets up a new one.
- **In practice this looks like:** you're in their design reviews (Tuesday, Thursday) not to grade their work, but to ask "how does this connect to what I'm building?" and to flag early if two specs contradict each other. You're the connective tissue, not the boss.

So: **you're a peer who happens to own the shared plumbing everyone's work has to run through.** That naturally puts you in a lot of conversations with all 4 of them, which can feel like "coordinating," but the actual decision-making authority over their designs sits elsewhere.

---

## 3. What "the existing app" has to do with any of this

Quick grounding, since this matters for your day-to-day decisions:

- **What you already built (Gen 1):** the FastAPI backend (`backend/`) and Next.js frontend (`frontend/`) that already do regulatory research, macro/economic data, competitive intelligence, and an AI "brief" panel — all running today behind nginx (`docker-compose.yml`, `nginx/nginx.conf`), reachable by the client.
- **What the 4 engineers are designing (Gen 2):** a completely different kind of system — instead of a normal database where you update rows, NAB stores every single business event forever and never changes old records (like a Git history for a loan or a customer, not a spreadsheet). This is the NEST Aggregate Block (NAB) architecture, and the "Genesis Layer" is the one-time process that takes a lender's old messy data (from Oracle, Tally, Prosper, spreadsheets, etc.) and converts it into that new event-based format.
- **Why this matters to you specifically:** Gen 2 is not a small feature add to Gen 1 — it's a different architectural pattern (event sourcing vs. normal CRUD). Part of your job this week is figuring out, practically, whether it lives inside this same repo (maybe building on `packages/genesis_core`, which already exists as an early stub) or as a separate service — and making sure that decision doesn't put the currently-live client app at risk.
- **Bottom line:** you keep Gen 1 running exactly as it is for the client, while quietly building the foundation Gen 2 needs underneath it, so that by the time the 4 engineers are ready to write real code (Sprint 2+), there's somewhere solid for it to go.

---

## 4. Your actual day-by-day job this week

This mirrors the brief's Monday–Friday plan, but from your seat.

### Monday — Architecture workshop day

**What happens:** Everyone (4 engineers + you) gets in a room/call and agrees on the basics: what do we call things, how is the code organized, what are our coding standards.

**What you specifically do:**
- Show up and represent "how things actually run today." When someone says "let's structure the repo this way," you're the one who knows what breaks or doesn't fit with the current deployment setup.
- Write down, in plain terms, what infrastructure already exists that Gen 2 could reuse: the Postgres-friendly setup, the existing Qdrant vector database connection, the nginx routing pattern (`/api/*` → backend, everything else → frontend), the Docker-based deploy process.
- Leave this meeting with a decision (even a tentative one) on: **does NEST/NAB code go in this repo or a new one?** If nobody decides, escalate it as a question for the PM (see §6) rather than guessing.

**Output:** A short internal note (a paragraph or two) capturing what was agreed — repo location, naming conventions, standards — so nobody has to remember it from memory later in the week.

### Tuesday — Individual design work + daily review

**What happens:** Each engineer works alone on their own spec (NAB schema, mapping rules, CSV format, DNBS/Genie architecture). There's a daily check-in.

**What you specifically do:**
- This is your "provisioning" day. While they're designing on paper, you start building the actual environment they'll need starting Wednesday:
  - Set up a Postgres schema/database for the Event Store (the tables the NAB brief describes: Aggregates, Events, Snapshots, Attachments, Links — just the empty table structure, not the business logic).
  - Confirm the vector store (Qdrant, already running at `192.168.1.183:6333` per your `docker-compose.yml`, or `pgvector` if that's preferred) is reachable and has a place for Engineer 4's prototype embeddings.
  - Sketch out where in the repo (or in a new repo) this all will live.
- At the daily review, you're mostly listening — but flag anything you hear that will be hard to build. Example: if Engineer 1 says "every event has a UUID and a global sequence number," you should be thinking "ok, that means my Postgres table needs a global sequence, not just a per-aggregate one" — and say so out loud if it changes your build.

**Output:** A working (even if empty/skeleton) database and vector store that the other 4 can point at starting tomorrow.

### Wednesday — Prototype implementation day

**What happens:** The 4 engineers start actually writing schemas (JSON, CSV) and maybe some prototype code.

**What you specifically do:**
- This is when they start needing you directly. Expect requests like "can you give me a connection string," "can I get write access to test my CSV importer," "does this JSON schema actually validate against Postgres jsonb."
- Set up basic tooling if useful: a way to validate JSON schemas, a place to drop sample CSVs and check they parse.
- Keep Gen 1 (the live app) completely unaffected — this should all be happening in a new schema/namespace/branch, not touching production.

**Output:** Each engineer has been unblocked at least once by something you set up. A repo skeleton exists with a place for each of the 4 deliverables to live.

### Thursday — Cross-review day

**What happens:** Each engineer reviews someone else's work to catch integration problems (e.g., does the CSV spec actually match the field names in the NAB schema?).

**What you specifically do:**
- This is the day you're most "coordinating." You're likely the one who first notices mismatches, because you're trying to actually wire the pieces together, not just read them.
- Concretely: try to load a sample CSV (Engineer 3's spec) through the mapping rules (Engineer 2's spec) into the NAB schema (Engineer 1's spec) and see if it actually produces a valid event. If it breaks, that's useful — bring it to the cross-review, don't quietly fix it yourself unless it's a trivial typo.
- Start wiring Engineer 4's DNBS/Genie prototype to read from whatever the Event Store looks like at this point.

**Output:** A list of "these two specs don't agree yet" issues, raised in time to fix before Friday — not discovered ON Friday.

### Friday — Integration day

**What happens:** The brief calls this out explicitly: make sure "NAB ↔ Mapping ↔ CSV ↔ Reporting ↔ Genie all connect logically."

**What you specifically do — this is your main deliverable of the week:**
- Actually run something end-to-end, even if tiny: one sample record (say, one loan from a CSV) goes in, gets mapped, becomes a NAB event, sits in your Postgres event store, and can be read back out through a projection or a Genie query.
- It does not need to be polished or complete. It needs to be **real** — proof that the 4 people's paper designs are compatible, not just four documents that look fine individually.
- Write a short integration report: what worked end-to-end, what's stubbed/faked for now, what's the biggest risk heading into next sprint.

**Output:** A working (minimal) demo path + a written report. This is the thing you show the PM as "Week 1, from the platform side, is done."

---

## 5. What you are explicitly NOT responsible for

To avoid stepping on the 4 engineers (and to avoid you quietly absorbing their work by accident):

- You don't design the NAB event/aggregate model — that's Engineer 1.
- You don't decide how legacy fields map to canonical fields — that's Engineer 2.
- You don't write the CSV column specs — that's Engineer 3.
- You don't design the regulatory report logic or the Genie's AI/RAG approach — that's Engineer 4.

Your job is **making their decisions runnable and compatible**, not making the decisions for them. If you find yourself designing business logic instead of infrastructure, that's a sign to hand it back or flag scope creep to the PM.

---

## 6. Questions to ask the Program Manager (put these to them directly)

1. **Scope check:** Is Friday supposed to produce a real (even if tiny) working demo, or is Week 1 purely documents/specs with no running code expected? This changes how much I build vs. just plan this week.
2. **Repo decision:** Should the NEST/Genesis Layer/NAB code live inside this existing `moneypal` repo (e.g., growing out of the `packages/genesis_core` stub that's already there) or as a brand-new, separate repository? I need this answered by Monday to set up the right structure.
3. **My authority:** When I notice two engineers' specs don't match on Thursday, am I expected to resolve it myself, escalate it to an architecture lead, or is that purely peer-to-peer between the two engineers?
4. **Environment/budget:** Is there a staging server planned beyond my local docker-compose setup, and do I have approval to provision new database/vector-store/object-storage resources if the current setup isn't enough?
5. **First real target:** Of the legacy systems listed (Oracle, Tally, Prosper, flat files), which one is the actual first client we're onboarding? That tells me which connector to prioritize supporting in the environment.
6. **Client visibility:** Is any of this NEST/NAB work shown to the client this week, or is it purely internal until a later milestone? This affects whether I need to protect demo time on the existing (Gen 1) app this week.
7. **Team shape beyond Week 1:** The full brief lists 16 deliverables (Oracle connector, Tally connector, Prosper connector, monitoring dashboard, developer SDK, etc.) — is the current 4-engineers-plus-me team going to be the team for all of that, or does it grow later? I want to plan infrastructure capacity accordingly.
8. **Ownership of "integration success":** The brief's Week 1 success criteria describe the 4 workstreams integrating into one coherent architecture — is that outcome specifically my responsibility to certify, or a shared/PM-owned checkpoint that I just contribute to?

---

## 7. TL;DR for a standup update

*"I'm not one of the 4 design workstreams — I'm the platform/infra person making sure their designs land somewhere real. This week I'm setting up the event store database, the vector store, and the repo structure, unblocking each engineer as they need infrastructure, and on Friday I'm wiring all 4 pieces together into one small working, end-to-end example to prove the designs actually fit."*
