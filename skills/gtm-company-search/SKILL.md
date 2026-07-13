---
name: gtm-pipeline:company-search
description: Build a list of companies matching ICP criteria. Use when a client needs a company list — no existing list, wants to expand, or signal-based discovery needs enrichment. Providers: Sales Navigator + PhantomBuster, Parallel FindAll, Firecrawl Agent, Pipe0 Amplemarket, BC/FE byproduct, web scraping. Also triggers on "build company list", "find companies", "company search".
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

**Ask the user which provider to use.**

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

### From Pipe0 Amplemarket (company search)

**Endpoint:** `POST https://api.pipe0.com/v1/searches/run/sync`
**Search ID:** `companies:profiles:amplemarket@1`
**Auth:** `Authorization: Bearer $PIPE0_API_KEY`

```json
{
  "config": {"environment": "production", "dedup": {"strategy": "default"}},
  "searches": [{
    "search_id": "companies:profiles:amplemarket@1",
    "config": {
      "limit": 100,
      "filters": {}
    }
  }]
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

**Cost:** 2.00 credits per page (100 results), per-search billing

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
Present options to user with estimated costs. Get approval.

### 3. Test Run
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
