---
name: gtm-pipeline:company-enrichment
description: Enrich a company list with structured data and score against ICP. Phase 1: data enrichment (PhantomBuster SN, Parallel Task Group, SimilarWeb, Firecrawl, SerpAPI). Phase 2: ICP scoring by the agent (icp_score 0-100, optional gate ≥70). Use after company-search and before signal-search. Also triggers on "enrich companies", "ICP scoring", "score companies".
---

# Company Enrichment

Enrich a company list with structured data and score against ICP. Returns enriched CSV + ICP scores.

**Read `~/.claude/skills/gtm-pipeline/_shared/conventions.md` before executing.**

---

## When to Use

- After `company-search` — raw list needs domains, revenue, headcount, etc.
- Before `signal-search` — ICP scoring determines which companies to invest signal credits on
- Before `people-search` — enriched domains required for most people search providers

## Inputs

| Input | Required | Source |
|-------|----------|--------|
| Company CSV | Yes | Company Search output (`csv/input/companies_raw.csv`) or user-provided |
| ICP definition | Yes | `context/icp.md` or user prompt |

---

## Two Phases

### Phase 1: Data Enrichment

Add structured company data. Choose provider based on what's available:

| Provider | Data Points | Input needed | Cost | Notes |
|----------|-------------|--------------|------|-------|
| **PB SN Scraper** | Full SN profile: headcount by dept, growth metrics, revenue range, industry, location | SN company URL | Free (SN account) | Most comprehensive |
| **Parallel Task Group** | Custom fields via web research | Company name + domain | ~$0.025–0.05/row | Flexible output schema. Ask which processor |
| **SimilarWeb via Apify** | Monthly traffic, traffic sources | Domain | Apify credits | Actor: `curious_coder/similarweb-scraper` |
| **Firecrawl** | Website content, tech stack signals | Domain | Firecrawl credits | Scrape + extract |
| **SerpAPI** | Domain from company name | Company name | SerpAPI credits | Google search → extract domain |
| **Pipe0 company data** | TBD — not yet tested | Domain | TBD | Check pipe0 catalog |

**Ask the user which provider to use.** Default: PB SN Scraper if SN URLs available, otherwise Parallel Task Group.

**Before the full batch:** state the estimated cost (rows x per-row cost from the table) and get user approval; test 5-15 rows first (conventions cross-cutting rule 2).

### Phase 2: ICP Scoring

Score enriched companies against client ICP definition.

---

## Phase 1 Execution

### PhantomBuster SN Account Scraper

**Agent:** Sales Navigator Account Scraper (config key: `PB_AGENT_SN_ACCOUNT` in `_shared/local.md`, or look up via PhantomBuster MCP)

Read `_shared/phantombuster.md` for the full API pattern. Use the `/phantombuster` skill to generate the script:
```
/phantombuster "Sales Navigator Account Scraper" -- scrape SN company data from <csv_file>, column <sn_url_column>
```

Input: SN company URLs (one per row in CSV)
Output per company: name, industry, headcount by dept, location, LinkedIn URL, SN URL, revenue range, growth metrics (6m / 1y / 2y), median tenure

### Parallel Task Group (Custom Enrichment)

**Endpoint:** `POST https://api.parallel.ai/v1/tasks`
**Auth:** `x-api-key: $PARALLEL_API_KEY`

**Always ask which processor to use:** `core`, `core2x`, `pro`, `ultra`

Design an output schema matching the data points needed for ICP scoring. Example:
```json
{
  "company_website": {"type": "string"},
  "linkedin_company_url": {"type": "string"},
  "estimated_revenue": {"type": "string"},
  "employee_count": {"type": "integer"},
  "industry": {"type": "string"},
  "founded_year": {"type": "integer"},
  "tech_stack_indicators": {"type": "array", "items": {"type": "string"}}
}
```

Always include `company_website` and `linkedin_company_url` in the schema.

Check latest docs via context7 (`libraryName: parallel-web`).

### SimilarWeb via Apify

Actor: `curious_coder/similarweb-scraper`
Env var: `APIFY_API_KEY`

Input: list of domains
Output: monthly visits, traffic sources, bounce rate, pages per visit

### Output

Write to `csv/intermediate/companies_enriched.csv`. Preserve all original columns, add enrichment columns.

---

## Phase 2: ICP Scoring

### How It Works

1. Read company rows (status=new, or all unscored)
2. Load ICP definition from `context/icp.md`
3. LLM scores each company → `icp_score` (0–100) + `icp_rationale`
4. Write score back to CSV
5. Process in batches (~10–20 companies per loop)

**Scoring is done by the agent** (sonnet tier suffices, see conventions Model Routing), never a third-party LLM API on the default path. Do not ask the user for a model.

### Input Fields Used for Scoring

From the enriched company data:
- name, industry, description, employee count, location, website, LinkedIn URL
- Revenue (min/max), department headcounts (engineering, sales, ops, IT, BD, marketing)
- Growth metrics (6m, 1y, 2y), median tenure, year founded

### ICP Scoring Prompt

The LLM receives each company row + the ICP definition and returns a structured score.

**Output schema per company:**
```json
{
  "icp_score": 85,
  "icp_rationale": "DACH-based B2B SaaS company in target revenue range. Experiencing rapid growth with lean tech team, indicating clear need for external automation support rather than in-house development."
}
```

### Per-Client Customization

- **ICP doc:** Maintain `context/icp.md` with the client's ICP definition — industry, size, location, revenue, tech profile, exclusions
- **Score threshold:** Adjust the gate based on selectivity (default: ≥70). The gate is optional — useful for credit savings on downstream steps, not a hard requirement.

### Optional Gate for Next Step (Signal Search)

To save credits on downstream signal-search, gate by:
- `icp_score >= 70`
- `website` not empty
- `type` in [Startup, Scaleup] (if type field available)

Skip the gate if you want to score signals on the full enriched set.

### Output

Write to `csv/intermediate/companies_scored.csv` with added columns:
```
icp_score, icp_rationale, scoring_status
```

All original + enrichment columns preserved.

---

## Full Output

Updated CSV with all columns:
```
company_name, company_domain, company_linkedin_url,
company_industry, company_hq_location, company_hq_country,
company_employee_count, company_employee_range,
revenue_range, growth_6m, growth_1y, growth_2y,
headcount_engineering, headcount_sales, headcount_operations, headcount_it,
icp_score, icp_rationale, scoring_status, enrichment_source
```

---

## What's Missing (To Document)

- Pipe0 company data pipe: test and document endpoint
- Parallel Task Group for company enrichment: test with specific output schema
- SimilarWeb via Apify: document the full actor setup and output field mapping
- LLM API integration patterns for standalone ICP scoring (outside orchestration platforms)
