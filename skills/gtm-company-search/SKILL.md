---
name: gtm-pipeline:company-search
description: Build a list of companies matching ICP criteria. Use when a client needs a company list — no existing list, wants to expand, or signal-based discovery needs enrichment. Providers: FullEnrich Company Search (default for firmographic filters), Sales Navigator + PhantomBuster, Parallel FindAll, Firecrawl Agent, Pipe0 Amplemarket, BC/FE byproduct, web scraping. Also triggers on "build company list", "find companies", "company search".
---

# Company Search

Build a list of companies matching ICP criteria. Returns a CSV with domains and LinkedIn URLs.

**Read `~/.claude/skills/gtm-pipeline/_shared/conventions.md` before executing.**

---

## When to Use

- **Company-First workflow:** Client needs a company list — no existing list, or wants to expand beyond what they have
- **Signal-First workflow:** Signal-based discovery has found companies — this skill enriches the initial list with domains/LinkedIn URLs if missing

## Inputs

| Input | Required | Source |
|-------|----------|--------|
| ICP definition | Yes | User prompt, `context/icp.md`, or discovery questions |
| SN search URL | Optional | Sales Navigator saved search |
| Existing partial list | Optional | User-provided CSV |

---

## Provider Selection

**First, check you need a company list at all** (`conventions.md` → Search Routing). A people search
takes company filters directly **and returns the companies for free**, so buying companies first
pays off only when you need **≥2 contacts per company**, when the account list is itself a
deliverable or a gate the client reviews, or when discovery is company-shaped anyway (client CSV,
directory, Sales Navigator, FindAll). A requirement that needs research or scoring is **not** a
reason on its own: screen the companies the people search returned instead.

**Default: FullEnrich Company Search** whenever the ICP can be written as filters (industry,
headcount, HQ location, company type, founded year, specialties, technologies, description
keywords). FullEnrich has no funding, hiring or revenue filter. BetterContact and Amplemarket do,
on the people search, which usually means no company step at all (see the matrix). Use
Parallel FindAll or Firecrawl Agent for behaviour no filter anywhere expresses (a project, a
campaign, press), or when FE returns too few relevant companies after 2 attempts.

### From FullEnrich Company Search (default)

**Endpoint:** `POST https://app.fullenrich.com/api/v2/company/search`, synchronous
**Auth:** `Authorization: Bearer $FULLENRICH_API_KEY`, called with curl (Cloudflare, conventions #8)
**Cost:** **0.25 credits per company returned.** A company the workspace already exported is free
to fetch again. Zero results cost nothing. The row cap is therefore the cost ceiling.
**Docs:** https://docs.fullenrich.com/api/v2/company/search/post

**Run it through `_shared/fe_search.py`, never hand-rolled curl.** The script validates filter
keys and enum values offline, owns pagination, maps `0` (FE's "unknown" for headcount and founded
year) to blank, keeps FE's company `id` as `fe_company_id` for the people step, and writes the raw
response to `csv/intermediate/fe_company_search_raw.json`.

```bash
source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh" && \
  export $(grep -E '^FULLENRICH_API_KEY=' "$GTM_ENV_PATH" | xargs) && \
  python3 ~/.claude/skills/gtm-pipeline/_shared/fe_search.py companies \
    --client-dir {client-slug}-gtm --filters {client-slug}-gtm/context/fe_company_filters.json \
    --max 40 --dry-run        # drop --dry-run once the printed request + ceiling look right
```

`fe_company_filters.json` is the request body without `limit`/`offset`/`search_after`:

```json
{
  "industries": [{"value": "Telephone Call Centers"}, {"value": "Outsourcing and Offshoring Consulting"}],
  "headquarters_locations": [{"value": "Germany"}, {"value": "Austria"}, {"value": "Switzerland"}],
  "headcounts": [{"min": 50, "max": 1000}],
  "keywords": [{"value": "customer service outsourcing"}],
  "domains": [{"value": "competitor.de", "exclude": true}]
}
```

| Filter | Shape | Notes |
|---|---|---|
| `industries` | `{value}` | LinkedIn industry names, **exact list in `_shared/fe_industries.txt`** (script rejects anything else). "Call centers" is `Telephone Call Centers`. |
| `headquarters_locations` | `{value}` | Continent / country **in English** / region + city **in the local language** (`Bayern`, `München`). "DACH" is not a value: list the three countries. |
| `headcounts`, `founded_years` | `{min, max}` | Inclusive ranges. |
| `keywords` | `{value}` | Matches the company **description**. The only filter People Search doesn't have, and the sharpest one for niche ICPs. Fuzzy by default, so test it small. |
| `specialties`, `technologies` | `{value}` | Self-declared specialties and detected tech stack (`HubSpot`, `Shopify`). |
| `types` | `{value}` | `Privately Held`, `Public Company`, `Self-Owned`, `Self-Employed`, `Partnership`, `Nonprofit`, `Educational`, `Government Agency`. |
| `names`, `domains`, `professional_network_urls`, `company_ids` | `{value}` | Exact lookups. With `exclude: true`, they drop existing customers or companies already contacted. |

- **Logic:** values inside one filter are OR, and different filters are AND (FE's
  *Filtering Logic Explained* page). Every string item takes `exact_match` (default `false`, fuzzy)
  and `exclude` (default `false`).
- **Not in the API:** revenue, funding, hiring and follower count show as "soon" in the FE UI.
  Don't plan a search around them.
- **Size before you pull:** the script prints `metadata.total` (all matches in the index). Run
  `--max 10` first (≤ 2.5 credits). If `total` is in the tens of thousands, the filters are too
  loose; tighten them before raising `--max`.
- **Re-verify locally:** check HQ country, headcount and industry on the returned rows before
  handing them on (filters narrow the search; they are not a guarantee).
- **Unverified until the first live call:** whether FE rejects or silently ignores an unknown
  filter key or an off-list value. The script refuses both, so don't bypass it.
- `logo_url` points at a fullenrich.com host. Never put it in a client deck (the deck names no
  provider). Use the domain favicon as the deck template does.

### From Sales Navigator (most comprehensive B2B data)

1. **SN Account Search → PhantomBuster SN Account Scraper**
   - Rich data: name, industry, headcount, location, LinkedIn URL, SN URL, employee search URLs, revenue range, growth metrics, department headcounts
   - PhantomBuster agent: `Sales Navigator Account Scraper`
   - Input: SN search URL
   - Output: full company profile data

2. **SN Lead Search → PhantomBuster Employee Export**
   - When you want contacts directly (skip separate people search)
   - PhantomBuster agent: `Sales Navigator Employee Export`
   - Input: spreadsheet of company URLs

### From Parallel FindAll (signal-based discovery)

**Endpoint:** `POST https://api.parallel.ai/v1beta/findall/runs`
**Required header:** `parallel-beta: findall-2025-09-15`
**Auth:** `x-api-key: $PARALLEL_API_KEY`

**Always ask which processor to use:** `core`, `core2x`, `pro`, `ultra`

Best when combined with signal criteria in the objective. Returns matched companies with reasoning and confidence.

```json
{
  "objective": "Find all DACH-based B2B SaaS companies with 10-200 employees that have shown signals of operational scaling challenges, digital transformation initiatives, or recent funding in the last 4 months. Focus on non-technical sectors: e-commerce, professional services, recruiting agencies, marketing agencies.",
  "entity_type": "companies",
  "match_conditions": [
    {"name": "location", "description": "Company must be headquartered in DACH region (Germany, Austria, Switzerland)"},
    {"name": "size", "description": "Company must have between 10 and 200 employees"},
    {"name": "recent_signals", "description": "Company must have shown at least one buying signal in the last 4 months"}
  ],
  "generator": "core",
  "match_limit": 25
}
```

**Writing good objectives:**
- Write like a research brief — detailed, with source guidance
- Describe what signals/sources to start from
- Include geographic, industry, and size constraints in text AND as match_conditions
- Include a LinkedIn URL condition if needed downstream

**Polling:**
```
GET /v1beta/findall/runs/{findall_id}         # status
GET /v1beta/findall/runs/{findall_id}/result   # results
```
Timeout: 15 min for `core`/`core2x`, 30 min for `pro`/`ultra`

**Enrich FindAll results** to add missing fields:
```
POST /v1beta/findall/runs/{findall_id}/enrich
```
Always include `company_website` and `linkedin_company_url` in output schema.

Always check latest docs via context7 (`libraryName: parallel-web`).

### From Firecrawl Agent (web agent)

`POST https://api.firecrawl.dev/v2/agent` with `spark-1-pro`

- Include structured schema with citation fields for traceability
- Good for niche criteria or specific industry directories

### From BetterContact or FullEnrich (people search as company source)

When running people search via BC Lead Finder or FE Finder, **company data is returned as a byproduct** — no extra API cost:

- **BC Lead Finder:** `company_name`, `company_domain`, `company_linkedin_url` per lead result
- **FE Finder:** `current_company_name`, `current_company_domain` per result

Use this when you already need contacts AND want to build/verify the company list simultaneously.

Both tools also offer **free dashboard search** for one-time manual company lookups.

### From Pipe0 (company search)

**Endpoint:** `POST https://api.pipe0.com/v1/search/run/sync` — **singular `search`**. The plural
`/v1/searches/*` is a different schema with a different body shape (`searches: [...]`, and it is the
only place `config.dedup` exists); posting the body below to it fails.

| Search ID | Filters | Billing |
|---|---|---|
| `companies:profiles:crustdata@3` | 27 | **0.15 credits per result** — `cursor` pagination |
| `companies:profiles:amplemarket@2` | 14 | 2.00 credits per page of 100 — `page_number` pagination |
| `companies:entitysearch:parallel@1` | 0 (free-text `objective`) | 0.50 credits per page |

`filters` is REQUIRED and may not be empty for the two profile searches. Verify every filter name,
value form and enum against the vendored catalog before sending — unknown keys are silently dropped
and billed. Sources and the people-side equivalents: **people-search skill → Pipe0 Searches**.

```json
{
  "config": {"environment": "production"},
  "search": {
    "search_id": "companies:profiles:amplemarket@2",
    "config": {
      "page_number": 1,
      "limit": 100,
      "filters": {"locations": {"include": ["Munich, Bavaria, Germany"]}}
    }
  }
}
```

**Response fields:**
```python
results = response.get("results", [])
for r in results:
    name    = r.get("company_name", {}).get("value", "")
    website = r.get("company_website_url", {}).get("value", "")
    desc    = r.get("company_description", {}).get("value", "")
    li_url  = r.get("company_profile_url", {}).get("value", "")
    match   = r.get("amplemarket_company_match", {}).get("value", "")
```

**Cost:** 2.00 credits per page (100 results). Crustdata bills **per result returned**, so its
`limit` IS the cost ceiling; Amplemarket bills the whole page whatever you ask for, so asking for
25 throws away 75 rows you already paid for.

---

### From Web Scraping

- Industry directories, association member lists, competitor customer lists
- Firecrawl scrape or manual collection

---

## Missing Data Recovery

| Have | Missing | Solution |
|------|---------|----------|
| Names / LinkedIn URLs | Domains | SerpAPI domain lookup (see people-search Step 0) |
| Names / domains | LinkedIn URLs | PhantomBuster URL Finder |
| LinkedIn company URLs | SN URLs | PhantomBuster can derive |

### SerpAPI Domain Lookup
```
GET https://serpapi.com/search
  ?engine=google_light
  &q={company_name}
  &location={target_country}
  &google_domain={country_google}
  &api_key=$SERPAPI_API_KEY
```

Extract: `urllib.parse.urlparse(organic_results[0]["link"]).netloc.removeprefix("www.")`

Always spot-check domains — SerpAPI returns wrong results for generic names and global brands.

---

## PhantomBuster API

```
Auth: X-Phantombuster-Key-1: <key>
Launch:  POST /api/v2/agents/launch  (agent ID + override arguments)
Poll:    GET /api/v2/agents/fetch?id=<agent_id>  (status == "finished")
Result:  GET /api/v2/containers/fetch-result-object  (or download S3 CSV)
```

Agent IDs: `_shared/local.md` (PB_AGENT_* table). Detailed API + in-script env loading: `_shared/phantombuster.md`.

---

## Execution Protocol

### 1. Clarify ICP
Before searching, ensure these are defined:
- Industry / vertical
- Company size (headcount range)
- Location / geography
- Revenue range (if relevant)
- Exclusions (e.g. no software companies)

### 2. Select Provider
FullEnrich Company Search when the ICP fits its filters (see Provider Selection). Otherwise
present the options with estimated costs and get approval.

### 3. Test Run
- For FullEnrich: `--dry-run` first (free), then `--max 10`, then read `metadata.total` and the rows
- For FindAll: start with `match_limit: 10`, review results
- For SN+PB: export 10–20 companies, verify data quality
- For Firecrawl Agent: test with a small prompt

### 4. Review
- Check company names, domains, LinkedIn URLs, industries
- Flag mismatches or low confidence results
- Get approval for full run

### 5. Full Run
- Submit full search
- Save results to `csv/input/companies_raw.csv`

---

## Output

CSV at `csv/input/companies_raw.csv`:

```
company_name, company_domain, company_linkedin_url,
company_industry, company_hq_location, company_hq_country,
company_employee_count, company_employee_range,
source
```

Additional fields from FullEnrich (`fe_search.py companies`):
```
company_website, company_type, year_founded, company_description,
company_specialities, company_technologies, fe_company_id
```
`fe_company_id` is what `fe_search.py people` joins on. Keep it in every downstream CSV
(sanitize strips `fe_*` from the lead-facing output).

Additional fields from SN (if available):
```
sales_navigator_company_url, employee_search_url, decision_makers_search_url,
year_founded, revenue_range, growth_6m, growth_1y, growth_2y,
headcount_engineering, headcount_sales, headcount_operations, headcount_it
```

---

## What's Missing (To Document)

- PhantomBuster API: full launch/poll/download flow for each agent (SN Account Scraper, Employee Export, URL Finder)
- Firecrawl Agent (`POST /v2/agent`): request/response format with structured schema
- Exa Websets via Pipe0: company discovery endpoint
- n8n workflow API: export/import existing flows for new client instances
