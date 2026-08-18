# Macro Intelligence Refresh Pipeline

Weekly refresh of the macro Qdrant collection that `app/services/macro.py` reads.

```
Sunday 10:00 IST (APScheduler)
   │
   ▼
COLLECT     crawl the sources.txt portals (robots-aware, rate-limited,
            conditional GET) -> backend/data/macro/<slug>/
   │
   ▼
FINGERPRINT sha256 vs state.json -> new / changed / unchanged
   │
   ▼
EXTRACT     PDF (per page) / CSV / XLSX / TXT -> chunks via genesis_core.rag
   │
   ▼
STRUCTURE   topics (gdp_growth, inflation_cpi, msme_trends, ...) +
            regex-mined figures with their context sentence
   │
   ▼
EMBED       bge-m3 via genesis_core.rag.embed_batch (1024-dim, normalized)
   │
   ▼
UPSERT      changed doc -> delete its old points, then write new ones
            unchanged doc -> re-stamp with this run id (no re-embedding)
   │
   ▼
PURGE       delete every macro point not stamped with this run id
```

Everything is env-driven through `app.core.config.settings` — see `.env.example`.
Qdrant credentials are read from the environment only.

## Commands

Run from `backend/`:

```bash
python -m scripts.macro_pipeline.run once            # refresh now
python -m scripts.macro_pipeline.run once --force    # re-embed everything
python -m scripts.macro_pipeline.run schedule        # weekly worker
python -m scripts.macro_pipeline.run stats           # point counts
python -m scripts.macro_pipeline.run sources         # configured sources
python -m scripts.macro_pipeline.run analyze <file>  # topics/figures, no ingest
python -m scripts.macro_pipeline.run migrate         # legacy-point dry run
```

In compose the `macro-pipeline` service runs `schedule` with `restart: unless-stopped`.

## Why a generation stamp instead of wipe-and-rebuild

Every point carries `ingest_run = <run id>`. A refresh writes or re-stamps the
points it can account for, then deletes anything still on an older stamp. The
collection is therefore never empty mid-run and the macro API keeps serving, while
documents retired at the source still disappear.

Two rails stop a bad week from emptying the collection:

- if any source errored *without* yielding a file, the purge is skipped entirely
- if the run accounted for less than `MACRO_PURGE_MIN_RATIO` (default 50%) of the
  pre-run point count, the purge is skipped and the reason logged

This matters because three of the four configured sources are gated today
(`epwrfits.in` login, `mospi.gov.in` TLS, `docsend.com` JS viewer). Files placed
into `backend/data/macro/` by hand are picked up and re-stamped like any other, so
the purge never mistakes them for retired documents.

## Point identity

```
uuid5(NAMESPACE_URL, "<source_slug>:<document>:<page>:<chunk_index>")
```

The slug is in the key because portals serve colliding filenames
(`index.aspx.pdf`, `Infographics English.pdf`). Re-ingesting an unchanged document
therefore overwrites in place rather than duplicating.

## The legacy points already in macro_intel1

As of this writing the live collection holds ~6,377 points from an **earlier ingest
that was not `backend/scripts/ingest.py`**. Their payload schema is different and
richer:

```
content, document_name, source (a slug: "mospi" / "msme" / "economic_survey" /
"karnataka_des"), source_url, page_number (string), section, category, subcategory,
keywords, state, country, publication_year, financial_year, last_updated
```

There is no `module` key, so any filter scoped to `module == "macro"` matches none
of them. Two consequences worth understanding before touching them:

- `genesis_core.rag.search` already falls back to `document_name` and `page_number`,
  which is why the current briefs work at all — but `source` is a slug, so today's
  citations read *(mospi, p.4)*, not a filename.
- **They cover sources this crawler cannot reach.** `mospi`, `msme` and
  `karnataka_des` are TLS/auth/manual-only. Deleting them and rebuilding from the
  crawl would shrink the macro corpus to the Economic Survey plus whatever sits in
  `backend/data/macro/`.

So `MACRO_PURGE_LEGACY` defaults to **false**: the weekly purge only retires points
this pipeline itself wrote on an earlier run. Retiring the legacy corpus is a
deliberate, separate decision:

```bash
curl -X POST "$QDRANT_URL/collections/macro_intel1/snapshots"   # backup first
python -m scripts.macro_pipeline.run migrate            # dry run: how many?
python -m scripts.macro_pipeline.run migrate --apply
python -m scripts.macro_pipeline.run once --force
```

Do that only once the PDFs behind those legacy sources are back in
`backend/data/macro/`, or the corpus shrinks. Rehearse the whole cycle against a
scratch collection first with `MACRO_COLLECTION=macro_scratch`.

Note that until migration, `Infographics English.pdf` and `economic_survey_2024.pdf`
will exist twice — once under each schema. Retrieval still works (both carry `text`),
but the same passage can be cited twice in one brief.

## Known source limitations

| Source | Status |
|---|---|
| `indiabudget.gov.in` | Works — Economic Survey chapters and infographics. |
| `epwrfits.in` | Subscription login wall; needs credentials. |
| `mospi.gov.in` | TLS handshake failure from this network. |
| `docsend.com` | JS viewer, no crawlable file links — download by hand. |

Files dropped into `backend/data/macro/` are ingested on the next run regardless of
whether any crawl reached them.
