---
name: gtm-pipeline:people-search
description: Find contacts at specific companies or by persona. Use when you have a company list and need contacts with specific roles (company mode), or when building a persona-based prospect list without a company list (persona mode). Also triggers on "find contacts", "search for people at [company]", "find [role] contacts", "people search".
---

# People Search

Find contacts at specific companies or by persona. Returns a CSV with LinkedIn profile URLs, ready for enrichment.

**Read `~/.claude/skills/gtm-pipeline/_shared/conventions.md` before executing.**

---

## When to Use

- You have a company list and need contacts with specific roles
- You need to build a persona-based prospect list (no company list)
- A demo was triggered and you need ~10 contacts matching a prompt

## Inputs

| Input | Required | Source |
|-------|----------|--------|
| Company list (CSV with names + domains) | For company mode | Company Search / Company Enrichment output, or user-provided |
| Target roles / job titles | Yes | User prompt or ICP definition |
| Location filter | Recommended | User prompt or ICP definition |
| Search mode | Yes | `company` (have company list) or `persona` (no company list) |

If company domains are missing, use SerpAPI domain lookup first (see Step 0 below).

---

## Step 0: Domain Lookup (SerpAPI) — When Domains Are Missing

Most people-search APIs require domains, not LinkedIn URLs.

```
GET https://serpapi.com/search
  ?engine=google_light
  &q={company_name}
  &location={target_country}
  &google_domain={country_google_domain}
  &api_key=YOUR_KEY
```

Extract domain:
```python
import urllib.parse
organic = response.get("organic_results", [])
link = organic[0].get("link", "")
domain = urllib.parse.urlparse(link).netloc.lstrip("www.")
```

**Spot-check all domains** before using — SerpAPI returns wrong results for generic names and global brands.

Env var: `SERPAPI_API_KEY`

---

## Provider Selection

### Company mode (have company list)

**Finder cadence (segment-routed waterfall): FullEnrich Finder → BetterContact Lead Finder → Pipe0 searches (`amplemarket@2` → `crustdata@3` → `parallel@1`, last resort). Max 2 attempts per source (e.g. a title-token query then a name-only query), then fall through. Lead with FullEnrich for SME / owner-led / non-English-market segments (better indexed there); lead with BetterContact for broader / English-market / larger companies. Add a Pipe0 pass on whatever the finders missed — different index, additive coverage. See conventions "People-Source Cadence" for the full waterfall and fallback rule; the table below is per-provider mechanics and cost, not a fixed running order.**

| Priority | Provider | Cost | LinkedIn URLs | Key Strength |
|----------|----------|------|---------------|-------------|
| 1st | **BetterContact Lead Finder** | 0.10 cr/lead returned | Yes | **Cheapest per lead** (2.5× under FE); good for high-volume batches |
| 2nd | **FullEnrich Finder** | 0.25 cr/person | Yes | Richest filters; richer fields (seniority, headcount, industry) |
| 3rd | **Pipe0 `amplemarket@2`** | 3.00 cr/page, **flat** (1 page = 100 records) | Yes | **Cheap waterfall for FE/BC misses** — separate index covers different shops (+36% shop coverage on DACH SMEs where FE had 0 hits). Company domain + name filters. Always ask for `limit: 100` — 25 costs the same |
| 4th | **Pipe0 `crustdata@3`** | 0.15 cr **per result returned** (`limit: 25` → 3.75 worst case) | Yes | Richest filter set (29). Low additive value when run after amplemarket (+1 shop out of 81 in DACH test) |
| 5th | **Pipe0 `parallel@1`** | 0.50 cr flat | Yes | AI entity search — no filters at all, every criterion goes in the objective prose. Use when the structured searches return 0 |
| 6th | **PhantomBuster Company Employees Export** | Free (LinkedIn account) | Yes | Good when SN not available; scrapes directly from LinkedIn company page |
| 7th | **PhantomBuster SN Search Export** | Free (SN account) | Yes | Full SN search power; use when you have a saved SN search URL |

**Indexes barely overlap on small EU SMEs** — running FE → `amplemarket@2` → `crustdata@3` is additive, not redundant. In an April 2026 DACH e-commerce run (81 FE-missed shops): amplemarket recovered 29 shops (74 contacts, 35%), crustdata added 1 more shop as fallback. Amplemarket stays first: 3.00 flat for up to 100 rows beats crustdata's 3.75 worst case for 25.

**Two-tier search pattern** (proven on EU e-commerce campaigns):
1. **Tier 1** — E-commerce + Marketing titles (always run)
2. **Tier 2** — Leadership titles (CEO/MD/Founder) — only if Tier 1 returns 0 contacts AND company traffic ≤ 200K visits/month (large shops likely have dedicated e-comm/marketing staff indexed by FE)

Run the same two-tier logic on whichever finder leads the cadence for the segment (FE or BC). Both bill per person returned: BC 0.10, FE 0.25.

When PhantomBuster is selected: read `_shared/phantombuster.md` and use the `/phantombuster` skill to generate the script. Phantom scripts: "LinkedIn Company Employees Export" (config key `PB_AGENT_EMPLOYEES`) and "Sales Navigator Search Export" (config key `PB_AGENT_SN_SEARCH`).

### Persona mode (no company list)

| Priority | Provider | Cost | Key Strength |
|----------|----------|------|-------------|
| 1st | **Parallel FindAll** | varies by processor | Discover people matching criteria from web sources |
| 2nd | **BetterContact Search** | TBD | Search without company filter |
| 3rd | **Pipe0 `crustdata@3`** | 0.15 cr/result | Richest persona filters (29): headcount brackets, industries, seniority, tenure, skills, education, career movement |
| 4th | **Pipe0 `amplemarket@2`** | 3.00 cr/page | Structured filters (21): location, headcount, LinkedIn industry, employer revenue, founded year, departments, seniority, funding, follower level, b2b/b2c |
| 5th | **Pipe0 `parallel@1`** | 0.50 cr | Prose criteria that no filter expresses (keywords, signals, free-text ICP brief) |

**Persona mode has no company anchor, so an unfiltered search is a fully-billed market-wide dump.** Never send a persona search without both a title list and at least one resolved region — the repo's builder raises on either being empty (see Provider E).

**Do NOT use Parallel Task enrichment for people** — model guesses titles, returns wrong roles. Use FindAll.

### Manual / one-time

Both BetterContact and FullEnrich dashboards offer **free search** without API credits.

---

## Execution Protocol

### 1. Sandbox / Docs Check
- Verify request/response structure with 1 record, zero cost
- For Pipe0: use `"environment": "sandbox"`
- For FE/BC: review docs or test via dashboard

### 2. Test Batch (15 companies or 15 records)
- Run chosen provider on 15 companies in production
- **Print and review every row**: company names, contact names, job titles, locations, LinkedIn URLs
- Check for global domain contamination (BC: add `lead_location` filter for `.com` domains)
- Assess hit rate, data completeness, relevance

### 3. Review with User
- Present test results with hit rate and sample rows
- Flag issues (wrong country, irrelevant titles, missing LinkedIn URLs)
- Suggest improvements or provider switch if results are poor
- Get approval before full run

### 4. Full Run
- Submit remaining companies (skip test batch)
- **Save request IDs to file immediately** (recovery if crash)
- Poll with sufficient timeout
- Save results incrementally to CSV after each batch

### 5. Consolidation
- Merge test + full run results
- Deduplicate by LinkedIn URL (fallback: name + company)
- Clean names/titles (`.title()`, strip whitespace)
- Add `source` column
- Write to `csv/intermediate/contacts_found.csv`

---

## Provider A: FullEnrich Finder

**Endpoint:** `POST https://app.fullenrich.com/api/v2/people/search`
**Auth:** `Authorization: Bearer $FULLENRICH_API_KEY`
**Cloudflare:** call with `curl` + a browser `User-Agent` — Python `requests`/`urllib` get blocked (error 1010). Never ship a urllib-based provider script. See conventions rule #8.
**Domain-keyed index:** the Finder is keyed on company domain and misses orgs whose domain differs from the indexed one — **prefer name-based search** (`current_company_names` + location) over the domain filter; validate hits by domain-root or name token.

### Company-keyed mode (companies came from FullEnrich Company Search)

When `companies_raw.csv` carries `fe_company_id` (company-search → FullEnrich), skip names and
domains entirely: query **`current_company_ids`** with FE's own id. The people response carries
the same id at `employment.current.company.id`, so identity is an exact check instead of a
fuzzy name comparison, and the domain-mismatch problem (conventions #11) goes away.
`_shared/fe_search.py people` does this: one request per company, `limit = --per-company`, rows
whose current-company id differs are dropped and counted, and each contact inherits the
company's industry, headcount and HQ for contact-filter.

```bash
source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh" && \
  export $(grep -E '^FULLENRICH_API_KEY=' "$GTM_ENV_PATH" | xargs) && \
  python3 ~/.claude/skills/gtm-pipeline/_shared/fe_search.py people \
    --client-dir {client-slug}-gtm --filters {client-slug}-gtm/context/fe_people_filters.json \
    --per-company 2 --dry-run   # ceiling = companies × per-company × 0.25
```

```json
{"current_position_seniority_level": [{"value": "Owner"}, {"value": "Founder"}, {"value": "C-level"}, {"value": "Head"}, {"value": "Director"}]}
```

Prefer `current_position_seniority_level` (a closed enum) over titles here: the company is already
pinned, so a seniority net plus local title-tier ranking in contact-filter beats a brittle title
list. Companies that come back with 0 contacts fall through to the normal cadence (BetterContact →
Pipe0) keyed on `company_domain`.

### Request
```json
{
  "offset": 0,
  "limit": 100,
  "current_company_domains": [
    {"value": "example.com", "exact_match": true, "exclude": false}
  ],
  "current_position_titles": [
    {"value": "Marketing Manager", "exact_match": false, "exclude": false},
    {"value": "Head of Marketing", "exact_match": false, "exclude": false}
  ],
  "person_locations": [
    {"value": "South Africa", "exact_match": false, "exclude": false}
  ]
}
```

### Available Filters
| Filter | Type | Example |
|--------|------|---------|
| `current_company_names` | object[] | `{"value": "Anthropic", "exact_match": true}` |
| `current_company_domains` | object[] | `{"value": "google.com", "exact_match": true}` |
| `current_company_professional_network_urls` | object[] | LinkedIn company URL |
| `current_company_ids` | object[] | FullEnrich company `id` from Company Search (exact join) |
| `current_company_industries` | object[] | `"Software Development"` |
| `current_company_professional_network_ids` | object[] | Numeric LinkedIn company id |
| `current_company_types` | object[] | `"Public Company"`, `"Privately Held"` |
| `current_company_headquarters` | object[] | `"San Francisco"` |
| `current_company_headcounts` | object[] | `{"min": 50, "max": 200}` |
| `current_company_founded_years` | object[] | `{"min": 2020, "max": 2024}` |
| `current_company_specialties` | object[] | `"AI safety"` (self-declared company specialties) |
| `current_company_technologies` | object[] | `"HubSpot"`, `"Shopify"` (detected tech stack) |
| `current_position_titles` | object[] | `"Chief Technology Officer"` |
| `current_position_seniority_level` | object[] | `"Director"`, `"VP"`, `"C-level"` |
| `current_position_job_functions` | object[] | `"Customer Service"` (closed list) |
| `current_position_sub_functions` | object[] | `"Call Center"` (closed list, nested under a function) |
| `past_position_titles` | object[] | Past job title |
| `past_company_names` | object[] | Previous employer name |
| `past_company_domains` | object[] | Previous employer domain |
| `person_ids` | object[] | FullEnrich person `id` |
| `person_names` | object[] | `"John Smith"` |
| `person_professional_network_urls` | object[] | Direct LinkedIn URL lookup |
| `person_professional_network_ids` | object[] | Numeric LinkedIn profile id |
| `person_locations` | object[] | `"South Africa"`, `"California"` |
| `person_languages` | object[] | `"German"` |
| `person_skills` | object[] | `"JavaScript"`, `"Project Management"` |
| `current_position_years_in` | object[] | `{"min": 0, "max": 1}` (new in role) |
| `current_company_years_at` | object[] | `{"min": 2, "max": 5}` (tenure) |
| `person_universities` | object[] | `"Stanford University"` |
| `current_company_days_since_last_job_change` | object[] | `{"min": 0, "max": 90}` (recent hires) |

**Closed value lists:** industries = `_shared/fe_industries.txt`. Seniority = `Owner`, `Founder`, `C-level`, `Partner`, `VP`, `Head`, `Director`, `Manager`, `Senior`. Company types = 8 values (company-search → FullEnrich). Functions and sub-functions (~385 lines) and location granularity: https://docs.fullenrich.com/api/v2/general/enums. Fetch that page and grep it before mapping a function; never guess one. Functions + seniority are the enum alternative when the title filter is too loose (see Key Notes).

All filters support `exclude: true` for negative matching. Values within one filter = OR, different filters = AND (FE's *Filtering Logic Explained* page; the endpoint's one-line summary says "AND within a field", but its own worked example contradicts that).

Key names above are checked against the v2 OpenAPI spec (2026-09-17). Older notes here used `current_company_linkedin_urls` and `person_linkedin_urls`, which are **not in the current spec**. They most likely predate FE's `linkedin` → `professional_network` rename (the same rename as the response-side URL gotcha below), and the ~48% URL-filter hit rate shows the old key worked when it was recorded. Whether FE now rejects or silently ignores an unknown key is unverified, so `fe_search.py` refuses unknown keys.

Pagination: `offset` + `limit` (max 100/page, max offset 10,000). Beyond 10k: use `search_after` cursor.

### Response
Response fields are **nested** — `current_position_title` and `linkedin_url` do NOT exist at top level.

⚠ **LinkedIn URL path gotcha:** the URL lives under `social_profiles.professional_network.url`, NOT `social_profiles.linkedin.url`. Older notes/snippets used `.linkedin.url` and silently returned empty strings for every row. Always parse `professional_network` first.

Also: the seniority field is `seniority` (not `seniority_level`) at `employment.current.seniority`. Values include `Manager`, `Senior`, `Head`, `Director`, `VP`, `C-Level`.

```python
people = response.get("people", [])
for person in people:
    name        = person.get("full_name", "")
    current     = (person.get("employment", {}) or {}).get("current", {}) or {}
    title       = current.get("title", "")
    seniority   = current.get("seniority", "")
    social      = person.get("social_profiles", {}) or {}
    li_url      = (social.get("professional_network", {}) or {}).get("url", "")
    loc_obj     = person.get("location", {}) or {}
    location    = f"{loc_obj.get('city', '')}, {loc_obj.get('country', '')}".strip(", ")
    # company info also nested: current["company"]["name"], current["company"]["domain"]
```

### Key Notes
- **Company LinkedIn URL = the fallback when name or domain are missing or miss.** `current_company_professional_network_urls` pins people to the company by its LinkedIn company URL (e.g. `https://www.linkedin.com/company/dojo-tech/`), so no domain lookup is needed when the input CSV only carries that URL. Order: name/domain → company LinkedIn URL.
- Hit rate for EU SME audience (via LinkedIn URL filter): ~48% (15/31 companies). Very small/niche companies with few employees often have low FE index coverage — expect 0 results.
- **Title filter is unreliable** — don't trust the API's title match. Query with **broad single-token titles** and score/filter roles **locally** in the response.
- **The Finder is NOT free:** 0.25 credits per person returned (FE *Credits & Testing Tips*). A person the workspace already exported costs nothing to fetch again, so overlapping **union queries** (title tokens / full titles / name-only) pay only for the new people. Cap `limit` per query, then **dedupe by LinkedIn URL**. The old "0-credit" note here was wrong for the API; FE's dashboard search is what's free.
- **Drop the per-person `person_locations` filter** — it's often null in the index and silently returns zero results; filter location locally instead.

### Cost
**0.25 credits per person** returned.

### Docs
https://docs.fullenrich.com/api/v2/people/search/post

---

## Provider B: BetterContact Lead Finder

**Endpoint:** `POST https://app.bettercontact.rocks/api/v2/lead_finder/async`
**Auth:** `X-API-Key: $BETTERCONTACT_API_KEY`
**Cloudflare:** call with `curl` + a browser `User-Agent` — Python `requests`/`urllib` get blocked (error 1010). Never ship a urllib-based provider script. See conventions rule #8.

### Submit
```json
{
  "filters": {
    "company": {
      "include": ["virginactive.co.za"]
    },
    "lead_location": {
      "include": ["South Africa"]
    },
    "lead_job_title": {
      "include": [
        "marketing manager", "head of marketing", "brand manager",
        "marketing director", "CMO", "digital marketing"
      ],
      "exact_match": false
    }
  },
  "max_leads": 10
}
```

Returns: `{ "success": true, "request_id": "abc123" }`

### All filters (`filters.*`, checked against the Lead Finder spec 2026-09-17)

At least one filter is required (400 otherwise). List filters take `{"include": [...], "exclude": [...]}`.

| Filter | Shape | Values |
|---|---|---|
| `company` | include/exclude | Company domains |
| `company_linkedin_url` | include/exclude | Company LinkedIn URL or slug (normalised server-side). The fallback when name/domain are missing. |
| `company_industry` | include/exclude | **120 exact Landbase industries** (not LinkedIn's) |
| `company_hq_location` | include/exclude | Country name, state or city ("Germany", "Berlin, Germany") |
| `company_technologies` | include/exclude | Exact values from the technologies taxonomy |
| `company_keywords` | include/exclude | Free text, searched across the company profile |
| `company_description` | include/exclude | Free-text phrases in the company description |
| `company_headcount_min` / `_max` | integer | Converted server-side to overlapping size ranges |
| `revenue_ranges` | include/exclude | 9 USD buckets from 0–1M to 10B+; exact strings in `_shared/finder_values.md` |
| `last_funding_round_names` | include/exclude | 29 exact values (`Seed Round`, `Series A`, `Private Equity Round`, …) |
| `last_funding_date_range` | `{gte, lte}` | `YYYY-MM-DD` |
| `last_amount_raised_usd` / `total_amount_raised_usd` | `{gte, lte}` | USD |
| `is_b2b` / `is_b2c` / `is_public` | boolean | `false` is sent as a real value |
| `job_post_titles` | include/exclude | Titles the company is **hiring for right now** |
| `job_posting_countries` / `job_posting_locations` | include/exclude | Where those open roles are |
| `limit_per_company` | integer 1–100 | Caps leads per company, so results spread across accounts |
| `lead_job_title` | include/exclude + `exact_match` | `false` (default) = title contains the value |
| `lead_seniority` | include/exclude | `c_suite` `vp` `director` `head` `manager` `senior` `mid-level` `entry` `founder` `owner` `partner` `intern` |
| `lead_department` / `lead_function` | include/exclude | Same 27 values for both, and merged if both are set (`Sales`, `Marketing`, `Operations`, `Customer Success`, …) |
| `lead_location` | include/exclude | Country name, or an address with a comma ("Paris, France") |
| `lead_skills`, `lead_fullname`, `lead_linkedin_url` | include/exclude | Free text / URL |

Request level: `limit` (1–200) + zero-based `offset` to paginate (total in `summary.leads_found`), or `max_leads` (1–200, default 100) without pagination. Never set `enrich_email_address` / `enrich_phone_number` here: they bill enrichment inside the search and bypass the email waterfall.

⚠ **Exact lists are case-sensitive, and an off-list value silently matches nothing** (industries, technologies, seniority, departments/functions, revenue, funding rounds, countries). A 0-lead result can mean a typo, not an empty market. Look values up first: https://doc.bettercontact.rocks/api-reference/taxonomies (technologies alone is ~1,700 lines, so grep it, don't read it).
⚠ **An on-list industry value can still poison the whole query.** Measured 2026-09-17 (Norway, same three `lead_job_title` values, only the industry list changed): `["Construction"]` → 2 leads, `+ "Civil Engineering"` → 2, `+ "Commercial Real Estate"` → 2, `+ "Architecture & Planning"` → **0**. `Architecture & Planning` is printed in BC's own 120-value list, yet including it zeroes the result instead of widening it (industry include should be OR). **Add industry values one at a time and watch `summary.leads_found`;** a value that drops the count to 0 is broken, not selective — drop it and, if that segment matters, reach it through `company_keywords` / `company_description` instead.
⚠ **Known traps (2026-09-24):** nine on-list industries zero every query they join, there is no Machinery value, and `company_hq_location` is not honoured; the list and details are in `_shared/finder_values.md`. A `company` domain list (+ `lead_location`, titles, `limit_per_company`) is reliable and was billed 0.0.
⚠ **`exclude` is applied after the search** (except `lead_job_title`'s, which the provider applies natively), so a request made only of excludes returns nothing. Pair every exclude with an include.
⚠ **Submissions are not idempotent.** A retried POST that actually succeeded is a second request.
⚠ **The API documents more filters than the BetterContact dashboard shows** (the UI has job title, seniority, department, location, skills, lead name, company name, industry, headcount, HQ, technologies, keywords). Funding, job postings, revenue, B2B/B2C, description and `limit_per_company` are API-only in the docs and **unverified in practice**. Check one before relying on it: run the search with and without that filter and compare `summary.leads_found`. An unchanged count means it was ignored; 0 usually means an off-list value. The dashboard's "exclude leads already exported" has no documented API equivalent.

### Poll
```
GET https://app.bettercontact.rocks/api/v2/lead_finder/async/{request_id}
```
Done when: `response["status"] == "terminated"` (not "completed")
Typical wait: 30–60 seconds per request.

### Parse
```python
leads = response.get("leads", [])
for lead in leads:
    name    = lead.get("contact_full_name", "")
    title   = lead.get("contact_job_title", "")
    li_url  = lead.get("contact_linkedin_profile_url", "")
    company = lead.get("company_name", "")
    domain  = lead.get("company_domain", "")
    country = lead.get("contact_location_country", "")
    co_li   = lead.get("company_linkedin_url", "")
```

### Global Domain Contamination
When using a global domain (`.com` for Samsung, H&M, Amazon, etc.), BetterContact returns employees from **all countries**. Always add `"lead_location": {"include": ["Target Country"]}` for global-domain companies. Local ccTLD domains (`.co.za`, `.de`) are safe without it.

### Cost
**0.10 credits per lead returned**, search only (never set `enrich_email_address` /
`enrich_phone_number` — that bills enrichment on top and bypasses the email waterfall). So
`limit` / `max_leads` is the cost ceiling, and `limit_per_company` caps what a single big company
can cost you. Zero results cost nothing. Every result carries `credits_consumed` and
`credits_left`; reconcile from those, not from the docs (the public credits page only says a search
consumes no *enrichment* credits, and the endpoint also has a free-request quota: `402` "not enough
tokens", `422` "out of free lead finder requests").

### Fields Returned
BC returns fewer fields than FE — no `seniority`, `companyHeadcount`, `companyIndustry`, or `roleStartDate`. Derive `linkedinProfileSlug` from the LinkedIn URL (`/in/<slug>`). Split `contact_full_name` into first/last manually.

### Filter Compatibility
When filtering contacts by job title keyword, BC uses `contact_job_title` (not FE's nested `employment.current.title`). Ensure your filter function checks both:
```python
title = (p.get("current_position_title") or
         p.get("contact_job_title") or          # BC format
         p.get("employment", {}).get("current", {}).get("title") or "")
```

### Hit Rate
- SA marketing roles, local (.co.za): ~65–70%
- DACH SME (March 2026): 1/3 companies (33%) — BC missed 2/3; FE found contacts at 2/3 on same set
- EU furniture e-commerce SME (April 2026): ~15–20% overall; T2 leadership tier recovers ~10% more

### When BC Finds Nothing
Fall back to FullEnrich. BC has lower index coverage for small EU SMEs, especially IT/PL markets. FE's richer filters and larger index often surface contacts BC misses — and vice versa. Running both covers ~25–30% of shops vs ~20% with either alone.

### Docs
https://doc.bettercontact.rocks/api-reference/endpoint/lead_finder_post

---

## Provider C: Parallel FindAll (Persona Mode)

**Endpoint:** `POST https://api.parallel.ai/v1beta/findall/runs`
**Required header:** `parallel-beta: findall-2025-09-15`
**Auth:** `x-api-key: $PARALLEL_API_KEY`

**Always ask which processor to use:** `core`, `core2x`, `pro`, `ultra`

### Request
```json
{
  "objective": "Find heads of marketing at e-commerce companies in South Africa with 50-500 employees",
  "entity_type": "people",
  "match_conditions": [
    {"name": "role", "description": "Person must hold a marketing leadership role (Head of Marketing, CMO, Marketing Director)"},
    {"name": "location", "description": "Person must be based in South Africa"},
    {"name": "company_size", "description": "Company must have roughly 50-500 employees"}
  ],
  "generator": "core",
  "match_limit": 25
}
```

**Writing good objectives:**
- Write like a research brief — detailed, with source guidance
- Describe what signals/sources to start from, not just what to find
- Include geographic, industry, and size constraints in the objective text AND as match_conditions

### Poll
```
GET /v1beta/findall/runs/{findall_id}         # status
GET /v1beta/findall/runs/{findall_id}/result   # results when complete
```
Timeout: 15 min for `core`/`core2x`, 30 min for `pro`/`ultra`

### Enrich FindAll Results
After FindAll, add structured fields:
```
POST /v1beta/findall/runs/{findall_id}/enrich
```
Always include `company_website` and `linkedin_company_url` in output schema.

### Rules
- **Always ask which processor to use** — never decide without asking
- **Never re-run before reviewing results**
- **Present the full request payload for review** before executing
- Assess accuracy using confidence score and reasoning

### Docs
Always check latest docs via context7 (`libraryName: parallel-web`) before building — endpoints and parameters evolve.

---

## Provider E: Pipe0 Searches (`crustdata@3` / `amplemarket@2` / `parallel@1`)

**Endpoint:** `POST https://api.pipe0.com/v1/search/run/sync` (singular `search`; `/v1/search/run` = async)
**Auth:** `Authorization: Bearer $PIPE0_API_KEY`
**Use curl** — Python requests blocked by Cloudflare (conventions rule #8).
**Sandbox is free and validates the request schema** — `{"config": {"environment": "sandbox"}}` returns fake rows. Probe every new body shape there before spending a credit.

**Do not hand-write these bodies.** The repo owns a verified builder that maps an ICP onto all three searches, resolves regions/industries against a vendored catalog, validates every key against the schema and returns `(body, warnings)`:

| What | Where |
|---|---|
| Builder (Python twin) | `scaleway-jobs/_shared/pipe0_payload.py` → `build_body(search_id, icp)` |
| Builder (TS twin) | `src/lib/contacts/pipe0-payload.ts` → `buildBody(searchId, icp)` |
| Vendored catalog | `scaleway-jobs/_shared/pipe0_catalog/{searches,regions,industries,industry_aliases}.json` — filter schemas + enums + per-filter `max`, 46,469 regions, 435 + 501 industries, 422 DE→EN industry aliases (source: `industries_de_en.csv`) |
| Callers | `scaleway-jobs/contact-search/search.py`, `src/lib/contacts/local-search.ts` |

Import it or copy its mapping; never reconstruct filters from memory. **`@1` search ids and their filter names (`current_employers`, `current_employer_website_urls`, `current_employers_linkedin_industries`, `profile_summary_keywords`) do not exist** — any script referencing them is pre-2026-08-12 and wrong.

### Envelope (all three)

```json
{"config": {"environment": "production"},
 "search": {"search_id": "<id>", "config": { }}}
```

`config.dedup` exists only on the plural `/v1/searches/*` schema — omit it here.

| Search ID | Cost | `search.config` keys |
|---|---|---|
| `people:profiles:crustdata@3` | **0.15 cr per result returned** — `limit` IS the cost ceiling (25 → 3.75 worst case) | `limit`, `cursor`, `output_fields`, **`filters` (required)** |
| `people:profiles:amplemarket@2` | **3.00 cr per page, flat** — 1 page = 100 records, so `limit: 25` throws away 75 free rows | `limit`, `page_number`, `output_fields`, **`filters` (required)** |
| `people:entitysearch:parallel@1` | **0.50 cr flat** | **`objective` (required, free text)**, `limit` (**min 5**), `output_fields` |

`output_fields` values are `{"enabled": true, "alias": ""}`; all default to enabled.

### `crustdata@3` — 29 filters

**Object `{"include": [...], "exclude": [...]}` (19):** `about_section_keywords`, `certifications`, `current_employer_domains`, `current_employer_industries`, `current_employer_names`, `current_employment_job_titles`, `current_school_names`, `degree_names`, `fields_of_study`, `honors`, `languages`, `locations`, `previous_employer_domains`, `previous_employer_industries`, `previous_employer_names`, `previous_employment_job_titles`, `profile_headline_keywords`, `school_names`, `skills`

**Plain array of enum (9):** `current_employer_headcount_brackets`, `current_employment_job_functions`, `current_employment_seniority_levels`, `current_employment_tenure_brackets`, `total_years_of_experience_brackets`, plus the `previous_employer_headcount_brackets` / `previous_employment_job_functions` / `previous_employment_seniority_levels` / `previous_employment_tenure_brackets` mirrors

**Scalar (1):** `recently_changed_jobs` (boolean | null)

Enums:
- headcount brackets (8) — **note the thousands separators**: `1-10`, `11-50`, `51-200`, `201-500`, `501-1,000`, `1,001-5,000`, `5,001-10,000`, `10,001+`
- job functions (12): Engineering, Sales, Consulting, Marketing, Operations, Finance, Research, Customer Success and Support, Arts and Design, Human Resources, Legal, Product Management
- seniority levels (10): Owner / Partner, CXO, Vice President, Director, Experienced Manager, Entry Level Manager, Strategic, Senior, Entry Level, In Training
- tenure brackets + total years of experience (5 each): Less than 1 year, 1 to 2 years, 3 to 5 years, 6 to 10 years, More than 10 years
- `locations` / `current_employer_industries` are free text validated against `regions.json` (46,469) / `industries.json` (435) — see Operational Rules

```json
{"config": {"environment": "production"},
 "search": {"search_id": "people:profiles:crustdata@3", "config": {
   "cursor": "", "limit": 25,
   "filters": {
     "current_employer_domains": {"include": ["example.com"]},
     "current_employment_job_titles": {"include": ["Geschäftsführung"], "exclude": ["Praktikant"]},
     "locations": {"include": ["Munich, Bavaria, Germany"]},
     "current_employer_headcount_brackets": ["51-200", "201-500"]}}}}
```

### `amplemarket@2` — 21 filters

**Plain array of string (4):** `current_job_titles`, `current_employer_investors`, `current_employer_open_position_titles`, `school_names`
**Plain array of enum (5):** `current_departments` (14), `current_seniority_levels` (14), `current_job_functions` (196), `current_employer_linkedin_industries` (501), `current_employer_estimated_revenue` (5 USD buckets, exact strings in `_shared/finder_values.md`)
**Object `{"include": [...], "exclude": [...]}` (4):** `current_locations`, `current_employer_locations` (← employer **HQ**, not the person), `current_employer_names`, `current_employer_domains`
**Range `{"min": …, "max": …}` (1):** `current_employer_founded_year`
**Scalar (1):** `person_name` (string | null)

- departments (14): Senior Leadership, Consulting, Design, Education, Engineering & Technical, Finance, Human Resources, Information Technology, Legal, Marketing, Medical & Health, Operations, Product, Revenue
- seniority (14): Owner, Founder, C-Suite, Partner, VP, Head, Director, Manager, Senior, Entry, Intern, Other, Non-Manager, Founder / Owner
- the 196 job functions and 501 industries live in the catalog — never guess one; **an unresolved industry value 422s the whole call**

⚠ **`current_job_titles` is a PLAIN ARRAY** (`["CEO", "Founder"]`), not the object form — and therefore **has no `exclude` arm**. Enforce exclusions locally.
⚠ **`current_employer_headcount_brackets` uses the SAME enum as crustdata** (`1-10 … 501-1,000 … 10,001+`, with thousands separators) — Pipe0 harmonised the two on 2026-08-12; an earlier catalog carried an `" employees"` suffixed variant and every value 422d. Read the enum from the catalog per search anyway; never re-type it. The *response* bracket still has no separators (`501-1000`).
⚠ **`current_job_titles` caps at 50 options and the cap is NOT in the schema.** Over-sending is not a 4xx: the call returns **HTTP 200 with `status: "failed"`, `results: []` and a full charge**, the reason only in `errors[0]` (`'person_titles' exceeds the maximum options per filter (50)`). Declared caps (spec `maxItems`) are 20 for `current_employer_linkedin_industries`, `current_job_functions`, `current_employer_investors`, `school_names`. **Always check `status` and `errors` — an empty `results` alone reads as "no matches".** Both twins trim + warn; crustdata has no title cap.
(Shipped 2026-08-12 — before that this search had no size filter at all, which is why older notes say to narrow locally. `current_employer_estimated_revenue` is still a different axis; do not substitute it.)

Also new on 2026-08-12: `current_employer_customer_types` (b2b/b2c), `current_employer_last_funding_round_types` (20), `current_employer_last_funding_within`, `current_employer_linkedin_follower_levels` (5), `linkedin_follower_levels` (6). None map to an ICP field today.

```json
{"config": {"environment": "production"},
 "search": {"search_id": "people:profiles:amplemarket@2", "config": {
   "page_number": 1, "limit": 100,
   "filters": {
     "current_employer_domains": {"include": ["example.com"]},
     "current_job_titles": ["Geschäftsführung", "Head of Marketing"],
     "current_locations": {"include": ["Munich, Bavaria, Germany"]}}}}}
```

### `parallel@1` — 0 filters

AI entity search. Every criterion — titles, size, industry, region, exclusions — goes into `objective` prose, and **nothing is validated**, so the objective must state each constraint explicitly. It is the only search that should receive raw client strings (unresolved locations, untranslated industries, keywords, the ICP description).

```json
{"config": {"environment": "production"},
 "search": {"search_id": "people:entitysearch:parallel@1", "config": {
   "limit": 25,
   "objective": "People whose current job title is one of: … (or the German or English equivalent). Employed at organisations with between 51 and 5000 employees. Located in … . Exclude anyone whose title contains: … .",
   "output_fields": {"name": {"enabled": true}, "job_title": {"enabled": true},
                     "profile_url": {"enabled": true},
                     "parallel_person_entity_match": {"enabled": true}}}}}
```

### Response shapes

Every output field is wrapped as `{"value": …}`. Results are in `response["results"]`.

```python
results = response.get("results", [])
v = lambda r, k: (r.get(k) or {}).get("value")
```

| Search | Output fields | Where the company/title actually is |
|---|---|---|
| `crustdata@3` | `name`, `profile_url`, `person_profile_match` — **no `job_title` field** | `person_profile_match`: `primary_job_title`, `headline`, `highest_current_seniority_level`, `current_location_city`, `current_location_country`, and `employment_history[]` — the entry flagged `is_primary_current_employer` carries `company_name`, `company_domain`, `company_profile_url`, `company_hq_region`, `headcount_bracket`, `company_industries[]`, `start_date` |
| `amplemarket@2` | `name`, `job_title`, `profile_url`, `company_domain`, `amplemarket_person_match` | `amplemarket_person_match`: `first_name`, `last_name`, `title`, `linkedin_url`, `location`, `headline`, `current_position_start_date`, `company.{name, website, size}` |
| `parallel@1` | `name`, `job_title`, `profile_url`, `parallel_person_entity_match` | `parallel_person_entity_match`: `current_company` (dict or string), `headline`, `experience_raw` |

⚠ `primary_company_domain` / `primary_job_title` / `primary_seniority` are output fields of the **enrichment pipe**, not of the crustdata *search*. Reading `person_profile_match.primary_company_domain` off a search row returns `""` — silently, and after the row is billed, so employer verification keyed on it fails for every row. Read `employment_history[]` first, fall back to `primary_company_domain`.

### Operational Rules (each one cost real money to learn)

1. **Unknown filter keys are silently dropped.** Pipe0 returns 200, bills the search as if unfiltered, and ignores the key. There is no runtime signal. **Discriminator when probing a key:** send it as the *only* filter — a bogus key 422s with "You must set at least one filter"; a real one runs. The builder's `_put()` raises on any key not in the catalog, and `chain_audit.py` enforces key parity between the twins.
2. **Values inside free-text include-lists are NOT validated.** An unrecognised region string is accepted and quietly widens/garbles the result set instead of erroring — metro-area and suburb forms (`Munich Metropolitan Area`, `Berlin/Brandenburg Metropolitan Area`, `Garching bei München, Bavaria, Germany`) are the common offenders, and out-of-country profiles then leak in. **Every region must be resolved against `regions.json`; anything unresolved is dropped and warned, never sent raw.** Valid forms: `Munich, Bavaria, Germany`, `Greater Munich Metropolitan Area`, `Berlin, Germany`. Never auto-widen a city to its state — `Hamburg, Alabama`, `Berlin, Ohio`, `Vienna, Georgia` all exist, and widening silently re-targets the client.
3. **Even valid enum filters are advisory.** Headcount brackets outside the requested range come back anyway, and a title list of `["CEO", "Founder"]` will still return a Product Owner. Filters are a **cost optimisation, never a guarantee** — widen at the provider, narrow locally. The local pass (title excludes, size check, employer verification, per-company cap) is the only real gate.
4. **Filter-vs-response bracket format mismatch.** The filter enum carries thousands separators (`501-1,000`), the response bracket does **not** (`501-1000`). Never compare the two forms directly — strip separators before parsing (`size_buckets.parse_bracket` / `bracket_overlaps_buckets` in both twins).
5. **Never send a persona search without an anchor.** No employer domain + no titles, or no resolved region, = a market-wide fully-billed dump. The builder raises on both.
6. **Empty filter → omit it**, never `{"include": []}` (either a 422 or a match-everything).

### ICP → filter mapping

`✅` clean · `⚠️` expressible but advisory, re-verify locally · `❌` not expressible, local only. Implemented in `pipe0_payload.py` / `pipe0-payload.ts` — this table is the spec, the builder is the truth.

| ICP field (`workflow_config`) | `crustdata@3` | `amplemarket@2` | `parallel@1` |
|---|---|---|---|
| `target_job_titles_tier1` + `tier2` | ✅ `current_employment_job_titles.include` | ✅ `current_job_titles` (bare array) | prose, ≤20 values |
| `exclude_job_titles` | ✅ `.exclude` arm of the same filter — but drop any value under 4 folded chars (`IT` is a substring of `Leitung`) or contained in an included title (`Assistenz` vs `Assistenz der Geschäftsführung`) | ❌ no exclude arm → local only | prose |
| `target_locations` (person) | ⚠️ `locations.include`, resolved | ⚠️ `current_locations.include`, resolved | prose, **raw** strings (an LLM reads "Garching" better than a canonical row) |
| `target_locations` (company HQ) | — | **never map** to `current_employer_locations` — that is employer HQ, which inverts a "staffed local site" criterion | — |
| `target_company_sizes` | ⚠️ `current_employer_headcount_brackets`, **widened** (our `51-250` → `51-200` + `201-500`) | ⚠️ same filter, same enum, widened the same way | prose ("between 51 and 5000 employees") |
| `target_industries` | ⚠️ `current_employer_industries.include`, resolved against the 435 list; unresolved → omit | ⚠️ `current_employer_linkedin_industries`, resolved against the 501 enum; **one bad value 422s the call**; capped at 20 | prose, raw |
| ↳ German industry labels | ✅ translated first via `industry_aliases.json` (`Gastgewerbe` → `Hospitality`, `Krankenhäuser und Gesundheitswesen` → `Hospitals and Health Care`). Exact fold-match only — Pipe0 serves the English side alone, and free-form business categories (`Privatkliniken`, `Handel und E-Commerce`) are NOT taxonomy labels and still drop | same | raw |
| `icp_keywords` | ❌ `profile_headline_keywords` / `about_section_keywords` are **person**-level; company/signal keywords there zero the recall | ❌ | ✅ their only home |
| `icp_description` | ❌ | ❌ | ✅ composed into the objective, never pasted whole |
| `max_contacts_per_company` | ❌ | ❌ | ❌ — group by employer after the call |
| company domain (company mode) | ✅ `current_employer_domains.include` | ✅ `current_employer_domains.include` | in the objective prose |
| seniority / departments / functions / tenure / `previous_*` | not emitted — no ICP field maps to them, and the vocabularies disagree (`Head` exists on amplemarket, not crustdata) | same | — |

**Company mode sends fewer filters on purpose:** domain + titles + excludes + person location. Size and industry are already known from the account row; re-asserting them can only drop real employees of the right company.

Warnings returned by the builder (unresolved regions/industries, dropped excludes, criteria the search cannot express) go to `activity_log.payload.targeting_warnings` — **ops-only**, they name search ids (Hard Rule 5). Most are fixable by the operator with data alone before the next run; that is the point of returning them.

### Refreshing the catalog

`scaleway-jobs/scripts/refresh_pipe0_catalog.py` regenerates the vendored JSON from:

| What | URL |
|---|---|
| OpenAPI 3.1 spec (39 searches) | `https://api.pipe0.com/openapi` — schemas at `components.schemas.SearchPayloadSchema.oneOf[]`, keyed by `properties.search_id.enum[0]` (**`.enum[0]`, not `.const`**) |
| Regions (46,469) | `https://raw.githubusercontent.com/pipe-0/pipe0/main/static/autocomplete/crustdata/regions.csv` |
| LinkedIn industries (435) | `…/static/autocomplete/crustdata/linkedin_industries.csv` |
| Other option lists | `…/static/autocomplete/common/{countries,titles,skills,schools,company_names,company_domains}.csv`, `…/crustdata/field_of_study.csv` |

It exits 1 when a pinned `search_id` disappears (Pipe0 ships `@4`), when a filter we emit changes form, or when a targeted headcount enum value vanishes.

**Pipe0 adds filters to an EXISTING version in place — the version number does not change.**
`amplemarket@2` went 15 → 21 filters on 2026-08-12 and grew the headcount filter it had never had —
a criterion that was simply not expressible on that search the day before. So a stable
`search_id` is no guarantee the capability set is stable: **re-run the refresher and diff the
catalog before any large persona run**, and treat "this search cannot express X" as a fact with an
expiry date, not a permanent limitation.

### DACH SME Hit Rate (company mode)

- `amplemarket@2` on FE-missed DACH e-commerce SMEs: **28/81 shops (35%)**, avg 2.5 contacts per hit shop, 74 contacts total
- `crustdata@3` as amplemarket-fallback: **1/52 shops** amplemarket missed — very low additive value, skip if budget is tight
- Company filter accepts `current_employer_names` and `current_employer_domains`; the domain form works with or without the `https://` prefix

---

## Output

CSV saved to `csv/intermediate/contacts_found.csv`:

```
company_name, company_domain, company_linkedin_url,
first_name, last_name, full_name,
job_title, linkedin_profile_url, source
```

All original input columns preserved. Always include a `source` column (e.g. `fullenrich_finder`, `bettercontact_lead_finder`, `pipe0_amplemarket`, `pipe0_crustdata`, `parallel_findall`).

---

## Key Rules

- **Finder cadence: FullEnrich → BetterContact → Pipe0 searches (`amplemarket@2` → `crustdata@3` → `parallel@1`), max 2 attempts per source then fall through.** Lead with FullEnrich for SME / owner-led / non-English-market segments; lead with BetterContact for broader / English-market / larger companies. Track each provider's credits separately. See conventions "People-Source Cadence".
- **Fallback trigger = zero *relevant* contacts, not zero rows.** A finder can return many rows that are all a *different* company (fuzzy name collision). Cross-check each candidate's returned company (`fe_company_name`) against the target and count only identity-matches before falling through. **Probe 3 companies first**; if the primary source returns 0 relevant on the probe, switch source before the full batch.
- **Directory/scrape-sourced company lists: search by NAME + location, never by exact domain.** A directory `acme.de` won't match a provider-indexed `acme.com` → 0 results. Validate each candidate by domain-root or name token. See conventions rule #11.
- **Cloudflare: BC and FE need curl too.** Like Pipe0, BetterContact and FullEnrich are Cloudflare-fronted — Python `requests`/`urllib` get blocked (error 1010). Call all three with `curl` + a browser `User-Agent`; never ship a urllib-based provider script. See conventions rule #8.
- **Two-tier search:** Always run Tier 1 (e-commerce/marketing titles). Only run Tier 2 (leadership) if Tier 1 returns 0 AND company is below traffic threshold (e.g. ≤ 200K monthly visits).
- **Global domains require location filter** in BetterContact (`.co.za` safe; `.com` for global brands returns worldwide).
- **BC is async** — submit then poll every 5s until `status == "terminated"`. Typical wait: 30–60s per request. Budget accordingly for large batches.
- **Senior titles bypass keyword filter** — "Head of", Founder, Director, C-level always pass regardless of excluded keywords (e.g. "Head of Marketing & Brand" should not be excluded for "brand").
- **Pipe0: use curl via subprocess** — Python requests blocked by Cloudflare.
- **Pipe0: build the body with `pipe0_payload.py` / `pipe0-payload.ts`, never by hand.** Unknown filter keys are billed-and-ignored, free-text regions are unvalidated, and every filter is advisory — the builder is what stops all three (Provider E → Operational Rules).
- **Never re-run before reviewing results** — save request IDs, poll for results, don't double-submit.
- **Unicode in company names** — CSV may use curly apostrophes (`\u2019`). Use `repr()` to debug string comparison failures.

## Google Sheets Row Matching (when writing results back)

When updating shop/lead status in a Google Sheet, build a lookup map at load time rather than calling `ws.find()` (which fails on large sheets):

```python
domain_row_map = {}
merchant_row_map = {}
for row_num, row in enumerate(all_values[1:], start=2):
    d = clean_domain(row[col["domain"]])  # strip www./https:// before storing
    if d:
        domain_row_map[d.lower()] = row_num
    m = row[col["merchant_name"]].strip()
    if m:
        merchant_row_map[m.lower()] = row_num
```

In `update_status()`, look up by domain first, fall back to `merchantName` if not found — handles domains stored with `www.` prefix or other mismatches.

---

## What's Missing (To Document)

- BetterContact Search (persona mode) — API endpoint and usage
- Exa Websets via Pipe0 for people discovery
- Pipe0 `crustdata@3` company-mode hit rates as PRIMARY search (currently only measured as amplemarket-fallback)
- Pipe0 persona-mode hit rates — the three searches have only been measured company-anchored
