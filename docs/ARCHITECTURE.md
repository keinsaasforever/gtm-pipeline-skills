# GTM Pipeline — Architecture

The plugin has two families of skills:
- **Prospecting** (this document): find and rank prospects, then hand them to Sales Agent.
- **Revenue intelligence** (`shared/revenue.md`, `docs/ROUTINES.md`): work on existing deals through the user's own connectors.

Work emails, phone numbers and outreach are not part of the plugin. They run in keinsaas Sales Agent, connected through the bundled `sales-agent` connector or a CSV import.

## Two Workflows

### Company-First (Finite Markets)

Use when you have a company list or a known, bounded industry.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     COMPANY-FIRST WORKFLOW                          │
└─────────────────────────────────────────────────────────────────────┘

 ┌──────────────────┐
 │  company-search  │  Providers: Parallel FindAll, Firecrawl Agent,
 │                  │  Pipe0 searches, web scraping
 └────────┬─────────┘
          │ csv/input/companies_raw.csv
          ▼
 ┌──────────────────────┐
 │  company-enrichment  │  Phase 1: Enrich (Parallel Task Group, SimilarWeb,
 │                      │  Firecrawl, SerpAPI)
 │                      │  Phase 2: ICP scoring → icp_score 0–100
 └────────┬─────────────┘
          │ csv/intermediate/companies_scored.csv
          │
          │  [optional gate: icp_score >= 70 to save credits downstream]
          │
          ├──────────────────────────────────┐
          ▼                                  ▼
 ┌─────────────────┐              ┌──────────────────┐
 │  signal-search  │              │  people-search   │
 │                 │  (parallel   │                  │
 │  sources:       │   or         │  company mode:   │
 │  - Parallel web │   sequential)│  find contacts   │
 │  - Firecrawl    │              │  at companies    │
 │  - Parallel     │              │                  │
 │    enrichment   │              │  persona mode:   │
 │  - job feeds    │              │  no company list │
 └────────┬────────┘              └────────┬─────────┘
          │ csv/intermediate/signals.csv   │ csv/intermediate/contacts_found.csv
          │ (message context)              │
          │                               ▼
          │                    ┌──────────────────┐
          │                    │  contact-filter  │  Rank by job tier, industry tier,
          │                    │                  │  location tier, company size,
          │                    │                  │  ICP keywords
          │                    └────────┬─────────┘
          │                             │ csv/intermediate/contacts_filtered.csv
          │                             ▼
          └──────────────────► ┌─────────────────────────┐
                               │  Sales Agent (hand-off)  │  Verified work emails,
                               │  connector or CSV import │  outreach
                               └─────────────────────────┘
```

---

### Signal-First (Infinite Markets)

Use when you have no company list — discover companies based on buying behavior.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SIGNAL-FIRST WORKFLOW                           │
└─────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────┐
 │  signal-search (discovery)  │  FindAll by signal criteria, Firecrawl Agent,
 │                             │  job boards, Exa Websets (via Pipe0)
 └─────────────────┬───────────┘
                   │ csv/input/companies_raw.csv  (raw company names from signals)
                   ▼
          ┌──────────────────────┐
          │  company-enrichment  │  Enrich + ICP score discovered companies
          └────────┬─────────────┘
                   │ csv/intermediate/companies_scored.csv
                   │
                   │  [optional gate: icp_score >= 70]
                   ▼
          ┌──────────────────┐
          │  people-search   │
          └────────┬─────────┘
                   │
                   ▼
          ┌──────────────────┐
          │  contact-filter  │
          └────────┬─────────┘
                   │
                   ▼
          ┌─────────────────────────┐
          │  Sales Agent (hand-off)  │
          └─────────────────────────┘
```

---

## CSV Handoffs

| Output File | Written By | Read By |
|-------------|-----------|---------|
| `csv/input/companies_raw.csv` | company-search | company-enrichment |
| `csv/intermediate/companies_enriched.csv` | company-enrichment Phase 1 | ICP scoring (Phase 2) |
| `csv/intermediate/companies_scored.csv` | company-enrichment Phase 2 | signal-search, people-search |
| `csv/intermediate/signals.csv` | signal-search | message context (demo) |
| `csv/intermediate/contacts_found.csv` | people-search | contact-filter |
| `csv/intermediate/contacts_filtered.csv` | contact-filter | Sales Agent (import) |
| `csv/output/contacts.csv` | demo | the deck, Sales Agent (import) |

---

## Cost Checkpoints

The pipeline has natural checkpoints where credits are spent. Review output quality before continuing.

```
company-search          ← credits: Parallel FindAll or Pipe0 searches
        ↓
company-enrichment      ← credits: Parallel (~$0.025–0.05/row), optional SimilarWeb
        ↓
[ICP gate icp_score ≥ 70]  ← saves downstream credits (signal-search, people-search)
        ↓
signal-search           ← credits: Parallel web search + enrichment, Firecrawl
        ↓
people-search           ← credits: FE Finder, BC Lead Finder, Pipe0
        ↓
contact-filter          ← no API cost — local classification only
        ↓
Sales Agent             ← email verification and outreach, charged in Sales Agent credits
```

---

## Provider Summary

| Skill | Recommended Provider | Alternative |
|-------|---------------------|-------------|
| Company search | Parallel FindAll | Firecrawl Agent, Pipe0 |
| Company enrichment | Parallel Task Group | SimilarWeb (Apify), Firecrawl |
| ICP scoring | Claude (in-context) | — |
| Signal web search | Parallel (processor: pro) | SerpAPI |
| Website crawl | Firecrawl | — |
| People search | FullEnrich Finder | BetterContact Lead Finder, Pipe0 |
| Emails, phones, outreach | Sales Agent | — |

---

## Shared Files

All skills read from `${CLAUDE_PLUGIN_ROOT}/shared/`:

| File | Purpose |
|------|---------|
| `conventions.md` | Field names (snake_case), terminology, provider disambiguation |
| `revenue.md` | Rules for the revenue-intelligence skills (copied into their `references/`) |
| `resolve_env.sh` | Finds the API key file (`GTM_ENV_PATH` or `~/.env.gtm`) |
| `sanitize.py` | Deterministic output sanitizer for lead-facing files |
| `deploy/` | Headless demo runner |
