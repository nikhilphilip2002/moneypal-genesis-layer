# Moneypal Genesis Intelligence Console

Web-based Genesis Intelligence Console built on the Aroha Corporate Intelligence
(RAG) Framework, for onboarding GICC onto the Moneypal platform. Buildathon project.
Full plans live in `/docs`.

---

## ⚠️ COMMIT POLICY — STRICT, NON-NEGOTIABLE

**All commits in this repository must be authored solely in the repository owner's name (nikhiltphilip).**

- Do **NOT** add `Co-Authored-By: Claude <...>` or any Anthropic / AI attribution to commits.
- Do **NOT** add "🤖 Generated with Claude Code" or similar to commit messages or PR bodies.
- Commit messages must read as if written by the developer — plain, human, no AI signature.

This overrides any default assistant behavior about co-authorship trailers.

---

## Architecture

Monorepo. Four independent parts, one shared contract.

```
moneypal/
├── frontend/            Next.js 15 + Tailwind + shadcn (Integration Lead)
├── module1-macro/       FastAPI service — Macro-economic Intelligence (Team A)
├── module2-competitive/ FastAPI service — Competitive Intelligence (Team B)
├── module3-regulatory/  FastAPI service — Regulatory Intelligence (Team C)
├── shared/              schema.py + rag_helpers.py (shared by all modules)
├── assets/              Moneypal + GICC logos
└── docs/                buildathon plans, per-team briefs, qdrant setup
```

RAG approach is **Direct** — no framework. `qdrant-client` + `sentence-transformers`
(bge-m3) + `groq` (llama-3.3-70b-versatile) + `pypdf`.

## Infrastructure

- **Qdrant**: shared instance at `192.168.1.183:6333` (must be on `Aroha_T1`/`Aroha_G1` WiFi).
  Each team creates its own collections. Always `create_collection`, never `recreate_collection`.
- **LLM**: Groq API, model `llama-3.3-70b-versatile`.
- **Embeddings**: `BAAI/bge-m3` (1024-dim, local).

## Brand & UI Color Scheme (from the Moneypal logo)

Follow the Moneypal brand. Two-color identity, clean and corporate.

| Token | Value | Use |
|-------|-------|-----|
| `--brand-blue` | `#0069B4` (PANTONE 300) | primary actions, links, active nav, accents |
| `--brand-blue-dark` | `#004A87` | hover, headers |
| `--brand-blue-light` | `#E6F0F9` | subtle backgrounds, selected rows |
| `--ink` | `#1A1A1A` (Process Black) | primary text, "Money" wordmark |
| `--muted` | `#6B7280` | secondary text |
| `--surface` | `#FFFFFF` / `#F7F8FA` | cards / page background |

- Logo pairing: Moneypal (left) + GICC (right) in the header — logos are in `/assets`,
  copy to `frontend/public/` during scaffold.
- Tagline for reference: "We move with you".
- Fonts: logo uses Harabara / Myriad Pro. Web equivalent: **Inter** for body,
  a bold geometric sans for display headings. Keep it clean, lots of whitespace.
- Keep it executive and calm — this is for bank directors, not a consumer app.

## Frontend Reference

Reference (do **not** copy) `../scenario_pipeline/apps/frontend` for structure and
patterns only: Next.js app-router layout, `AppSidebar` + `NavBar` composition,
`components/ui/*` (shadcn/Radix), `ThemeProvider`, and markdown rendering with
`react-markdown` + `remark-gfm`. Our product, roles, and visual identity are our own.

## Shared Response Contract

Every module endpoint returns the same shape (`shared/schema.py`):
`title, summary, key_points[], source{document,url,page}, ai_note, last_updated, confidence`.
Every AI insight cites its source and its `ai_note` separates fact from AI interpretation.

## The Four Roles

`moneypal_admin` (full), `gicc_admin` (dashboard + competitive + regulatory),
`gicc_policy` (regulatory + competitive), `gicc_director` (executive dashboard only).

## Build Workflow

Work proceeds in phases. **Commit at the end of every phase** (in the owner's name only).
See `docs/BUILDATHON_PLAN.md` for the full phase breakdown.
