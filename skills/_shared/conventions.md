# GTM Pipeline — Shared Conventions

All GTM pipeline skills must follow these conventions. Read this file before executing any skill.

---

## Working Directory

Every skill run operates inside a `{client-slug}-gtm/` directory. Create it on the first skill invocation for a client. If it already exists, reuse it.

```
{client-slug}-gtm/
├── context/
│   ├── icp.md                         ← ICP definition, voice, proof points
│   └── provider_performance.md        ← Running log of provider results per run
├── prompts/
│   └── message_prompt.md              ← Message generation prompt (demo skill)
├── csv/
│   ├── input/
│   │   ├── companies_raw.csv          ← Input company list
│   │   └── contacts_raw.csv           ← Input contact list (if provided)
│   ├── intermediate/
│   │   ├── companies_enriched.csv     ← After company-enrichment
│   │   ├── companies_scored.csv       ← After ICP scoring
│   │   ├── signals.csv                ← After signal-search
│   │   ├── contacts_found.csv         ← After people-search
│   │   ├── contacts_filtered.csv      ← After contact-filter (ICP-ranked, enrichment-ready)
│   │   └── request_ids.json           ← Saved API task IDs for recovery
│   └── output/
│       ├── contacts_enriched.csv      ← Final enriched contacts
│       └── messages.csv               ← Generated messages (demo only)
└── run_log.md                         ← Chronological log of all skill runs with costs
```

**Client slug:** lowercase, hyphens, no spaces (e.g. `acme-corp-gtm/`, `example-client-gtm/`).

---

## Output Format

Every skill run must end with this summary printed to the user AND appended to `run_log.md`:

```
## Run Summary — {skill name} — {timestamp}
- **Records processed:** {n}
- **Records with results:** {n_found} ({hit_rate}%)
- **Provider used:** {provider_name}
- **Credits consumed:** {credits} (est. {cost_per_record} × {n})
- **Cost:** ~${cost} (if pricing known)
- **Quality assessment:**
  - Hit rate: {hit_rate}%
  - Data completeness: {completeness details}
  - Issues: {issues or "None"}
- **Recommendation:** {proactive suggestion or "None"}

## Not Yet Available
- {list of undocumented tools/endpoints that could improve this run}
- {reference to the skill's "What's Missing" items}
```

**Rules:**
- Produce this summary after every step (test batch, full batch, fallback pass), not just at the end
- Include actual data quality observations, not just numbers — e.g. "2 contacts from wrong country (flagged)"
- The "Not Yet Available" section references items from each skill's own "What's Missing" list

---

## Run Log

Append to `{client-slug}-gtm/run_log.md` after each skill step:

```markdown
### {timestamp} — {skill name} — {step name}
- Provider: {provider}
- Records: {n_processed} → {n_found} ({hit_rate}%)
- Credits: {credits_consumed}
- Cost: ~${cost}
- Duration: {time}
- Notes: {any issues or observations}
```

---

## Provider Performance Log

Append to `{client-slug}-gtm/context/provider_performance.md` after each provider run:

```markdown
### {date} — {provider_name} — {skill}
- Audience: {description of target audience/geography}
- Hit rate: {actual}% (baseline: {expected from guide}%)
- Deviation: {actual - expected}%
- Records: {n}
- Cost: {credits} credits
- Issues: {any}
```

---

## Provider Optimization

After each batch:
1. Compare actual hit rate vs documented baseline (from the skill's provider tables)
2. If deviation > 15 percentage points below baseline → flag and suggest switching providers
3. If multiple providers are available, suggest A/B test on next batch
4. After a full run, produce a provider comparison table if multiple providers were used or could have been used

---

## Demo Mode

When a skill is invoked from the demo flow:
- **No phone enrichment** — email only, skip all phone providers
- **Scope:** ~10 contacts (request 10–15, expect drop-off)
- The demo skill sets this context explicitly when invoking other skills
- People-enrichment must check for this and skip phone providers entirely

---

## Cross-Cutting Rules

These rules apply to every skill in the pipeline:

1. **Plan and test in sandboxes** — validate request/response structure at zero cost before any production call
2. **Test a few leads before the full batch** — 5–15 records, never the full list
3. **Review results after each run** — inspect actual data rows (names, titles, locations, URLs), not just hit counts
4. **Ask which model/processor to use** — never decide on AI models, APIs, or tools without asking first
5. **Never re-run before reviewing** — do not waste credits on duplicate runs
6. **Save all API output fields** — never drop columns from API responses
7. **API keys via runtime injection** — never read `.env` files into context. Use: `export $(grep KEY_NAME /path/.env | xargs) && python3 script.py`
8. **Pipe0: use curl** — Python requests/urllib blocked by Cloudflare
9. **Max 100 contacts per batch** — all enrichment providers (Pipe0, BC, FE)
10. **Global domains require location filter** — BetterContact with `.com` for global brands returns worldwide results. Always add `lead_location` filter. Local ccTLD domains (`.co.za`, `.de`) are safe without it.

---

## Environment Variables

**.env path:** Set `GTM_ENV_PATH` in `_shared/local.md`. Default fallback: `$HOME/.env.gtm`.

`GTM_ENV_PATH` is documented in `local.md` but is **not** auto-exported into the shell — a fresh shell has it unset, so `"$GTM_ENV_PATH"` silently expands to empty. Always `source` the resolver first; it sets `GTM_ENV_PATH` from (1) an existing env var, else (2) the `GTM_ENV_PATH=` line in `local.md`, else (3) `~/.env.gtm`:

```bash
source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh"
```

Never read the .env file with the Read tool. Always inject keys at runtime via Bash, after sourcing the resolver:
```bash
source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh" && \
  export $(grep -E '^KEY_NAME=' "$GTM_ENV_PATH" | xargs) && python3 script.py
```

To inject multiple keys at once (anchor patterns with `^` so values can't match):
```bash
source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh" && \
  export $(grep -E '^(PIPE0_API_KEY|FULLENRICH_API_KEY|BETTERCONTACT_API_KEY|PARALLEL_API_KEY|SERPAPI_KEY|APIFY_API_TOKEN)=' "$GTM_ENV_PATH" | xargs) && python3 script.py
```

| Variable | Service | Used by |
|----------|---------|---------|
| `PIPE0_API_KEY` | Pipe0 | people-search, people-enrichment, company-enrichment |
| `BETTERCONTACT_API_KEY` | BetterContact | people-search, people-enrichment |
| `FULLENRICH_API_KEY` | FullEnrich | people-search, people-enrichment |
| `SERPAPI_API_KEY` | SerpAPI | company-search, people-search (domain lookup) |
| `PARALLEL_API_KEY` | Parallel AI | people-search (FindAll), signal-search, company-search, company-enrichment |
| `APIFY_API_KEY` | Apify | company-enrichment (SimilarWeb traffic) |
| `PHANTOMBUSTER_API_KEY` | PhantomBuster | company-enrichment (SN scraper), people-search (employees), outreach |
| `LINKEDIN_SESSION_COOKIE` | LinkedIn li_at cookie | all PhantomBuster agents |
| `LINKEDIN_USER_AGENT` | Browser user agent | all PhantomBuster agents |

Other credentials (OpenRouter, Firecrawl, Stripe) are requested when the corresponding skill runs.

**PhantomBuster** scripts load vars in-script rather than via export+inject — see `_shared/phantombuster.md`.

---

## Pipe0 API Helper

All Pipe0 calls must use curl. Standard helper:

```python
import subprocess, json, os

PIPE0_KEY = os.environ["PIPE0_API_KEY"]

def pipe0_request(method, path, body=None):
    cmd = ["curl", "-s", "-w", "\n__HTTP_CODE__%{http_code}",
           "-X", method, f"https://api.pipe0.com/v1{path}",
           "-H", f"Authorization: Bearer {PIPE0_KEY}",
           "-H", "Content-Type: application/json"]
    if body:
        cmd += ["-d", json.dumps(body)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    parts = result.stdout.rsplit("\n__HTTP_CODE__", 1)
    http_code = int(parts[1]) if len(parts) > 1 else 0
    if http_code >= 400:
        raise RuntimeError(f"API error {http_code}: {parts[0][:300]}")
    return json.loads(parts[0]) if parts[0] else {}
```

**Base URLs:**
- Searches (sync): `POST /v1/searches/run/sync`
- Searches (async): `POST /v1/searches/run`
- Pipes: `POST /v1/pipes/run`
- Check pipe status: `GET /v1/pipes/check/{task_id}`
- Sandbox mode: `"config": {"environment": "sandbox"}` — free, validates structure only

---

## Canonical Field Names

All CSV outputs use **snake_case**. When ingesting data from providers that use camelCase or different naming, map to canonical names on first contact.

| Canonical (snake_case) | PB / LinkedIn (camelCase) | FullEnrich / BetterContact | Pipe0 |
|------------------------|---------------------------|----------------------------|-------|
| `company_name` | `companyName` | `company_name` | `company_name` |
| `company_domain` | `companyUrl` (extract domain) | `company_domain` | `domain` |
| `company_linkedin_url` | `linkedInCompanyUrl` | `company_linkedin_url` | `linkedin_url` |
| `company_industry` | `linkedinCompanyIndustry` | `industry` | `industry` |
| `company_hq_location` | `linkedinCompanyHeadquarter` | `headquarters` | `hq_location` |
| `company_employee_count` | `linkedinCompanyEmployeesCount` | `employee_count` | `employees` |
| `company_specialities` | `linkedinCompanySpecialities` | — | — |
| `company_founded_year` | `linkedinCompanyFoundedYear` | `founded_year` | `founded` |
| `linkedin_profile_url` | `profileUrl` | `linkedin_url` | `profile_url` |
| `full_name` | `fullName` | `full_name` | `name` |
| `first_name` | `firstName` | `first_name` | `first_name` |
| `last_name` | `lastName` | `last_name` | `last_name` |
| `job_title` | `currentJob` / `title` | `contact_job_title` | `title` |
| `email` | — | `email` | `email` |
| `email_status` | — | `email_status` | `status` |
| `phone` | — | `phone_number` | `phone` |
| `location` | `location` | `location` | `location` |

**When a skill outputs CSV:** use canonical names. **When a skill ingests CSV from a provider:** map to canonical names before writing the intermediate file.

---

## Terminology

Use these preferred terms for consistency across skills, logs, and user-facing summaries.

| Preferred Term | Avoid |
|---------------|-------|
| Company-First workflow | "Workflow 1" |
| Signal-First workflow | "Workflow 2" |
| ICP score (company-level, 0–100) | `icpScore` (camelCase in code OK; prose uses snake_case) |
| Signal score (buying intent, 1–100) | `overallScore`, "lead score" |
| Contact tier (`job_tier`, 1–6) | "persona tier", "lead tier" |
| Demo mode | "webhook trigger", "demo flow" |
| Hard reject threshold | "kill threshold" |
| Working directory | "client folder", "client dir" |

---

## Provider Name Disambiguation

Several providers have similarly-named products. Be explicit about which is meant.

| Product | Skill | Purpose | Notes |
|---------|-------|---------|-------|
| **BetterContact Lead Finder** | people-search | Synchronous people discovery API | Returns contacts by company + role filters |
| **BetterContact async enrichment** | people-enrichment | Async email/phone enrichment | Slow due to multi-provider waterfall. Email hit rate is low (~14% in our tests) — **prefer FullEnrich for email**. Acceptable for phone if user has patience. |
| **FullEnrich Finder** | people-search | People discovery (returns LinkedIn URLs) | Required upstream of FullEnrich Enrich for email |
| **FullEnrich Enrich (v2)** | people-enrichment | Email + phone enrichment | Faster and more reliable than BC for email; has MCP support |
| **Pipe0 searches** | people-search, company-search | Discovery — finds new entities | `searches:profiles:*` |
| **Pipe0 pipes** | people-enrichment | Enrichment — augments existing entities | `pipes/run` waterfall |
