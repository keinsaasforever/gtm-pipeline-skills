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
2. **Test a few leads before the full batch** — 5–15 records, never the full list. If the primary source returns 0 on the probe, switch source before spending the full batch (see People-Source Cadence).
3. **Review results after each run** — inspect actual data rows (names, titles, locations, URLs), not just hit counts
4. **LLM/judgement work is done by the agent** — extraction, scoring, filtering, and message generation run in-context (or via model-routed subagents), never via a third-party LLM API on the default path. See **Model Routing**. Do not silently swap models.
5. **Never re-run before reviewing** — do not waste credits on duplicate runs
6. **Save all API output fields in `intermediate/`** — never drop columns from API responses there. The **lead-facing `output/` view is sanitized** (see Output Sanitization): provenance, statuses, and empty columns are stripped there, not in intermediate.
7. **API keys via runtime injection** — never read `.env` files into context. Use: `export $(grep KEY_NAME /path/.env | xargs) && python3 script.py`
8. **Cloudflare-fronted APIs: use curl** — Pipe0, BetterContact, and FullEnrich reject Python `requests`/`urllib` (Cloudflare blocks the TLS/UA signature, error 1010). Always call them with `curl` + a browser `User-Agent`. Never regenerate a urllib-based provider script.
9. **Max 100 contacts per batch** — all enrichment providers (Pipe0, BC, FE)
10. **Global domains require location filter** — BetterContact with `.com` for global brands returns worldwide results. Always add `lead_location` filter. Local ccTLD domains (`.co.za`, `.de`) are safe without it.
11. **Directory/scrape-sourced company lists: search by NAME, validate by domain-root** — never filter enrichment providers by exact domain (a directory `acme.de` won't match a provider-indexed `acme.com` → both BC and FE return 0). Search by company name + location, then confirm each candidate against the target by domain-root or name token (`fe_company_name` cross-check) to guard generic names. See People-Source Cadence.
12. **Delivery is gated** — writing a message/email to a file is fine; **sending on the user's behalf needs explicit go-ahead** every time.
13. **Ask when critical input is missing** — if an input essential to a correct result is missing or ambiguous (skill-specific: e.g. ICP/target audience, offering & value prop, provider choice or credit budget, tone/language, a required ID or path), ask the user with the **AskUserQuestion** tool rather than guessing. Low-stakes defaults (poll interval, batch size within limits) don't need a prompt.

---

## Model Routing

LLM/judgement work (signal extraction, signal scoring, contact filtering, message generation,
presentation assembly) is done by **the Claude agent**, not by a third-party LLM API. The same
logic runs whether a human invokes a skill interactively or a webhook runs it headless — the
only difference is how the agent is started.

| Task | Model (alias → latest) | How it runs |
|------|------------------------|-------------|
| Contact filtering / ICP ranking | **sonnet** | agent or Sonnet subagent |
| Signal extraction (from Parallel/Firecrawl output) | **opus** | agent or Opus subagent |
| Signal scoring (buying intent 1–100) | **opus** | agent or Opus subagent |
| Message generation | **opus** | agent or Opus subagent |
| Presentation / deck assembly + copy polish | **sonnet** | agent or Sonnet subagent |

- **Interactive (terminal):** the orchestrating agent does the work in-context, or spawns
  model-routed subagents (Sonnet for filtering/presentation, Opus for extraction/scoring/messages).
  **Never shell out to `claude -p`** from inside an interactive session (no nested CLI).
- **Deployed (webhook):** a thin runner calls `claude -p "/gtm-pipeline:demo <prompt>"`. The
  headless agent does the same work — `claude -p` is the *outer entrypoint*, so still no nesting.
- **Fully autonomous scripts (cron/n8n, no agent):** may pass `--llm-backend claude-cli` to shell
  `claude -p`. `--llm-backend openrouter` is a **dormant** legacy path kept on `main` — the code is
  present but **inert**: the flag alone won't run it, `GTM_ALLOW_OPENROUTER=1` must also be set, else
  the script errors out. No deepseek/OpenRouter/Gemini models run on any normal invocation.
- Use model **aliases** (`sonnet`, `opus`) so runs track the latest tier without version-pinning.

Scripts (`signal_search.py`, provider search/enrich, deck builder, `sanitize.py`) do only
**deterministic** work: provider APIs, CSV I/O, dedup, scoring math, sanitization. Default
`signal_search.py --llm-backend agent` collects evidence and leaves scoring to the agent.

---

## Search Routing: where to spend first

Decide this **before the first paid search** (pipeline Step 2, demo Step 3). First split every ICP /
prompt requirement into two kinds and write the split to `context/icp.md` under `## Search routing`:
requirement → kind → provider + filter key + values, or the step that scores it.

- **Filter:** a finder's filter expresses it (matrix below). **Always prefer the filter, even if it
  means a different finder:** "raised a round in the last 6 months" and "hiring SDRs" are
  BetterContact / Amplemarket filters, not research.
- **Score:** no filter expresses it; it needs reading or judgement. Revenue from filings, website
  traits (runs a shop, sells a category), a project or leadership change, "fits our offer", ranking.

**Every finder returns the lead's company, so a people search produces the company list for free.**
A Score requirement therefore does **not** justify searching companies first: screening a company
you then discard costs the same either way, and the company step adds a second charge for the
survivors' people. Per kept contact, with company-row price `c_co`, person-row price `c_p`, pass
rate `p` and `k` contacts per company: people-first `c_p·k/p` vs company-first `c_co/p + c_p·k`.
Company-first only wins when **`k > c_co / (c_p·(1-p))`**:
- FullEnrich both ends (0.25 / 0.25): 2+ contacts per company at a 20–30% pass rate, 3+ at 50%.
- BetterContact people (0.10) under FullEnrich companies (0.25): 4+ at 30%, 6+ at 50%.

People-first also never pays for a company whose people the index doesn't carry.

**The math above assumes a bounded universe.** It compares prices per kept contact; it does not say
how many rows you buy. A people search against an unbounded ICP ("contractors in Norway and Sweden")
is a market-wide pull billed per row, and the filtering happens after you have paid. Bound the
universe *before* the first paid search, in this order:
1. **Filters bound it** — industry + HQ country + headcount + titles resolved against each finder's
   own value list. This is the normal case and costs nothing extra.
2. **No value list fits, or the filtered pull comes back slim or off-segment** → bound it by
   enumerating companies instead: a public ranking, a directory, an association member list, a
   client CSV (free), then one people search per company. This is how the emmy (18 named brands)
   and nextbike (21 clinics from a public hospital list) runs stayed at a 1.3:1 and 2.6:1
   pulled-to-delivered ratio.
Cost of ignoring it (Reduzer, 2026-09-17): an unbounded two-country persona pull bought 311 rows to
deliver 30, a 10:1 ratio, and 59.5 of the run's credits went to rows that were filtered away.

Routes:

1. **Default — people first, screen after.** Search people with the company filters, take the
   companies out of the results, run the Score pass on them (signal-search, research, agent
   scoring), and drop the contacts whose company fails. Pull `target ÷ expected pass rate`.
   To get the most distinct companies per credit use BetterContact `limit_per_company: 1`;
   FullEnrich has no per-company cap, so its persona searches can cluster.
2. **Company first** when one of these holds, not because a requirement needs scoring:
   **≥2 contacts per company** (the math above), the **account list is itself a deliverable** the
   client reviews or the pipeline gates on, or **discovery is already company-shaped** (a directory,
   Sales Navigator, FindAll, a client CSV). Then people search keyed to those companies
   (FullEnrich: `fe_company_id`; others: domain, then company LinkedIn URL).
3. **Signal first** only when a signal is **mandatory and is the entry point** — companies without
   it must never be contacted and no filter expresses it. Start from the signal source (FindAll,
   news, job boards), derive companies, then people. A signal that a finder filters (funding,
   hiring) belongs to the default route, and a signal used to *check* companies we already picked,
   or as a message hook, runs after the search in either of the routes above.

Headless runs decide alone and record the routing in `icp.md`.

### Filter matrix (what each finder can express)

`P` = FullEnrich People Search, `C` = FullEnrich Company Search, `BC` = BetterContact Lead Finder,
`CD` = Pipe0 `crustdata@3`, `AM` = Pipe0 `amplemarket@2`. `parallel@1` / FindAll take everything
as prose and validate nothing.

| Requirement | P | C | BC | CD | AM |
|---|---|---|---|---|---|
| Industry | ✓ | ✓ | ✓ | ✓ | ✓ |
| Headcount | ✓ | ✓ | ✓ | ✓ | ✓ |
| Company HQ location | ✓ | ✓ | ✓ | – | ✓ |
| Company type (private / public / nonprofit…) | ✓ | ✓ | public only | – | – |
| Founded year | ✓ | ✓ | – | – | ✓ |
| Technologies used | ✓ | ✓ | ✓ | – | – |
| Specialties / profile keywords | ✓ | ✓ | ✓ | – | – |
| Company description text | – | ✓ | ✓ | – | – |
| Revenue | – | – | ✓ | – | ✓ |
| Funding (round, date, amount / investors) | – | – | ✓ | – | ✓ |
| Hiring (open job posts) | – | – | ✓ | – | ✓ |
| B2B / B2C | – | – | ✓ | – | ✓ |
| Person title / seniority / function or department | ✓ | – | ✓ | ✓ | ✓ |
| Person location | ✓ (often null) | – | ✓ | ✓ | ✓ |
| Skills | ✓ | – | ✓ | ✓ | – |
| Languages | ✓ | – | – | ✓ | – |
| New in role / tenure / recent job change | ✓ | – | – | ✓ | – |
| Past employer or title | ✓ | – | – | ✓ | – |
| Max leads per company | – | – | ✓ | – | – |

Exact keys, value lists and gotchas: people-search **Provider A** (FullEnrich), **Provider B**
(BetterContact), **Provider E** (Pipe0), company-search → FullEnrich. **Values are not portable
between finders:** FullEnrich uses LinkedIn industries (`_shared/fe_industries.txt`, case-insensitive),
BetterContact uses 120 Landbase industries (case-sensitive, and an off-list value silently matches
nothing), and Pipe0 uses its own catalog.

---

## People-Source Cadence

Finder/enricher waterfall — stop as soon as a source yields enough **relevant, identity-verified**
contacts. **Max 2 attempts per source** (e.g. a title-token query then a name-only query), then
fall through:

0. **Companies came from FullEnrich Company Search?** Query people by `current_company_ids`
   (`_shared/fe_search.py people`). It's an exact id join, so no name or domain matching is needed.
   Only the companies that come back empty enter the waterfall below.
1. **FullEnrich Finder** (0.25 credits per person returned; re-exports free) — lead for SME / owner-led / non-English-market
   segments (FE indexes these better than BC). Run union queries (title tokens, full titles,
   name-only), dedupe by LinkedIn URL, filter locally.
2. **BetterContact Lead Finder** (0.10 credits per lead returned — the cheapest finder per row;
   4 searches returning 74 leads on 2026-09-17 billed **0.0**, `credits_consumed` and the account
   balance both unchanged, so treat 0.10 as the ceiling and read `credits_consumed` per run) —
   for broader / English-market / larger-company segments, and **first in a demo**, where its
   `limit_per_company` is what spreads a fixed pull across distinct accounts.
3. **Pipe0 searches** — last-resort finder when FE+BC return 0 relevant candidates for a company
   (keyed on the real domain, it recovers companies the others miss). Order within Pipe0:
   `amplemarket@2` (3.00 flat for up to 100 rows) → `crustdata@3` (0.15/result, 3.75 worst case at
   `limit: 25`) → `parallel@1` (0.50, prose objective). Max 2 attempts each.

**Fallback trigger = zero *relevant* contacts, not zero rows.** A provider can return many rows
that are all a *different* company (fuzzy name collision) — cross-check each candidate's returned
company (`fe_company_name`) against the target and count only identity-matches before deciding to
fall through. Probe 3 companies before the full batch; if the primary source returns 0 on the
probe, switch source first.

---

## Signal Quality

Signals are scored on **two axes, in order** — proximity gates, offering-fit prioritizes — and only
count as buying intent if **all** gates hold (enforced by the agent per the signal-search rubric,
and re-checked by `sanitize.py`):

- **Attributable / proximate (Axis 1 — the gate):** the development must genuinely **stem from this
  specific company or the named person at it** — its own funding, hire, product, or stated project.
  A generic industry/market/peer story that merely mentions or could apply to any similar company is
  **not a signal** (score 0). Never invent a connection between sector news and the company; do not
  bend a trend onto a lead. An adjacent actor (partner/customer/competitor) counts only if it forces
  an action *at this company*.
- **Fresh:** within the lookback window (demo default ≤ 60 days / `--lookback-months 2`). Undated
  signals never count as fresh. Stale-signal companies are **demoted to ICP-fit**, never force-fit.
  The date is the event's, not the page's: a fresh article re-reporting an older announcement is
  stale. `signal_search.py` drops undated and stale-only evidence before anyone reads it, and a
  stale event never re-enters through a fit text or summary (demo Step 6 → Hook sources).
- **Sourced:** carries a live `source_url` **and** a parseable `date`. Drop anything unlinkable.
  The URL is the article or post itself, never a homepage, listing page or company profile
  (`sanitize.is_article_url`).
- **Real:** the source snippet actually supports the claim (re-verify — a "CTO hiring" post can be
  a mislabeled lab role). Geo/segment must match the ICP, not just be recent.
- **Intent, not incumbency:** "already owns a competing/adjacent solution" is **neutral/negative**,
  not hot intent — reposition as a complement/ICP-fit, don't score it as buying intent.

**Offering fit (Axis 2 — priority + hook):** among signals that pass the gates, how tightly the
development ties to what we sell sets the score band, the outreach priority, and the hook. Proximity
decides *whether* to reach out; offering fit decides *how hard* and *with what hook*.

---

## Output Sanitization

`csv/intermediate/` keeps everything. The lead-facing `csv/output/` (and any deck/email built from
it) is sanitized by **`_shared/sanitize.py`** — a deterministic, no-LLM step every demo/outreach run
applies before producing the deliverable:

- **Drop bad emails** — keep only allowed deliverability statuses (default policy `standard`:
  Deliverable + High-probability + Catch-all + Kitt's `valid` and `valid-risky`; `strict` also drops
  catch-all and `valid-risky`). Kitt's `unknown`, `invalid` and `unverified` are in no policy, so
  an address the gate rejected or never checked cannot reach a lead. The real anti-"made-up-address"
  guard is the upstream **domain-identity cross-check** (people-enrichment): a `DELIVERABLE` email
  on a domain that isn't the target's is a wrong-company hit — drop it.
- **Pull wrong-person addresses** — one mailbox on two contacts means at most one owner, so
  `sanitize.py` keeps it on the contact whose name the local part matches and blanks it on the
  others (`emails_wrong_person`); when no name matches, all of them lose it. A *lone* address whose
  local part matches no part of the name is only reported (`emails_name_mismatch`) — check those by
  hand. Role mailboxes (`info@`, `kontakt@`, `sales@`…) are exempt. **A blanked address never drops
  the contact** when `require_email=False`: the row ships with LinkedIn only.
- **Drop stale/sourceless signals** — per Signal Quality above.
- **Strip provenance** — provider/source labels (`source`, `fullenrich_finder`, `ccv_directory`),
  internal status codes (`email_status`, `HIGH_PROBABILITY`), and technical columns never ship.
- **Drop empty columns** — any column blank across all rows is removed (a demo CSV must never look
  like failed enrichment).
- **Message hygiene** — em-dashes → commas; enforce length caps at write time (LinkedIn ≤ 400,
  email ≤ 450/500) by trimming at a sentence/word boundary, not by hand afterward.

```python
import sys; sys.path.insert(0, os.path.expanduser("~/.claude/skills/gtm-pipeline/_shared"))
from sanitize import sanitize_rows
clean, report = sanitize_rows(rows, email_policy="standard", max_signal_age_days=60)
```

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
  export $(grep -E '^(PIPE0_API_KEY|FULLENRICH_API_KEY|BETTERCONTACT_API_KEY|PARALLEL_API_KEY|SERPAPI_API_KEY|APIFY_API_KEY)=' "$GTM_ENV_PATH" | xargs) && python3 script.py
```

| Variable | Service | Used by |
|----------|---------|---------|
| `KITT_API_KEY` | Kitt (trykitt.ai) | people-enrichment (first email finder + the verifier gate), demo, demo-headless |
| `PIPE0_API_KEY` | Pipe0 | people-search, people-enrichment, company-enrichment |
| `BETTERCONTACT_API_KEY` | BetterContact | people-search, people-enrichment |
| `FULLENRICH_API_KEY` | FullEnrich | company-search, people-search, people-enrichment |
| `SERPAPI_API_KEY` | SerpAPI | company-search, people-search (domain lookup) |
| `PARALLEL_API_KEY` | Parallel AI | people-search (FindAll), signal-search, company-search, company-enrichment |
| `APIFY_API_KEY` | Apify | company-enrichment (SimilarWeb traffic) |
| `PHANTOMBUSTER_API_KEY` | PhantomBuster | company-enrichment (SN scraper), people-search (employees), outreach |
| `LINKEDIN_SESSION_COOKIE` | LinkedIn li_at cookie | all PhantomBuster agents |
| `LINKEDIN_USER_AGENT` | Browser user agent | all PhantomBuster agents |

Other credentials (Firecrawl, Stripe) are requested when the corresponding skill runs. `OPENROUTER_API_KEY` is **legacy/optional** — needed only for `signal_search.py --llm-backend openrouter`; the default `agent` path needs no LLM key (see Model Routing).

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
- Searches (sync): `POST /v1/search/run/sync` — **singular `search`**
- Searches (async): `POST /v1/search/run`
- Pipes: `POST /v1/pipes/run`
- Check pipe status: `GET /v1/pipes/check/{task_id}`
- Sandbox mode: `"config": {"environment": "sandbox"}` — free, validates structure only

**Search bodies are built, not written.** The three searches we use (`people:profiles:crustdata@3`, `people:profiles:amplemarket@2`, `people:entitysearch:parallel@1`), their filters, enums, costs and response paths are documented in the **people-search skill, Provider E**; the implementation is `scaleway-jobs/_shared/pipe0_payload.py` + its TS twin `src/lib/contacts/pipe0-payload.ts` with the vendored catalog in `scaleway-jobs/_shared/pipe0_catalog/`. Four rules apply to every Pipe0 search call, and each cost real money to learn:

1. **Unknown filter keys are silently dropped** — 200, fully billed, key ignored. Validate keys against the catalog; when probing whether a key exists, send it alone (a bogus key 422s with "You must set at least one filter").
2. **Free-text filter values are NOT validated** — an unrecognised region string is accepted and silently widens the search instead of erroring. Resolve regions/industries against the catalog; drop and warn on anything unresolved, never send it raw.
3. **Every filter is advisory** — out-of-range headcounts and off-target titles come back anyway. Filters are a cost optimisation; the local re-verification pass is the only guarantee.
4. **Filter enums carry thousands separators (`501-1,000`), responses do not (`501-1000`)** — never compare the two forms directly.

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

**Pipe0 search rows are wrapped** — every output field is `{"value": …}`, so read `row["profile_url"]["value"]`, not `row["profile_url"]`. The Pipe0 column above is the enrichment-pipe vocabulary; search rows expose far fewer fields (`crustdata@3` has no `job_title` at all — title and company come out of `person_profile_match`). Per-search field maps: people-search skill, Provider E → Response shapes.

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
| **Kitt find_email** | people-enrichment | **Priority-1 email enrichment** | Live finder: full name + company domain, $0.005 per address found, misses free. Its hits come back verified. Engine: `_shared/kitt.py` |
| **Kitt verify_email** | people-enrichment | **The verifier gate** | Checks every *other* provider's address before it is kept. `valid` / `valid-risky` / `unknown` / `invalid`; a demo ships `valid` and `valid-risky`. Same engine, `--no-find` |
| **PhantomBuster Email Finder** | people-enrichment | **Priority-1 email enrichment** | PB's built-in email waterfall (BetterContact et al.) via the "Email Finder" phantom. Input staged from a Google Sheet by `_shared/pb_email_finder.py`. **Runs after Kitt, on its misses; if N/A (no PB key / staging sheet / Google OAuth → exit 3), skip to FullEnrich.** Grades nothing, so every PB address goes through the Kitt gate. |
| **BetterContact Lead Finder** | people-search | Synchronous people discovery API | Returns contacts by company + role filters |
| **BetterContact async enrichment** | people-enrichment | Async email/phone enrichment | Slow due to multi-provider waterfall. Email hit rate is low (~14% in our tests) — **prefer FullEnrich for email**. Acceptable for phone if user has patience. |
| **FullEnrich Company Search** | company-search | Firmographic company discovery (`POST /v2/company/search`) | Default company source. 0.25 cr per company returned. Its `id` joins exactly to the Finder's `current_company_ids`. Script: `_shared/fe_search.py` |
| **FullEnrich Finder** | people-search | People discovery (returns LinkedIn URLs) | Required upstream of FullEnrich Enrich for email. 0.25 cr per person returned, **not free** |
| **FullEnrich Enrich (v2)** | people-enrichment | Email + phone enrichment | Faster and more reliable than BC for email; has MCP support |
| **Pipe0 searches** | people-search, company-search | Discovery — finds new entities | `people:profiles:crustdata@3`, `people:profiles:amplemarket@2`, `people:entitysearch:parallel@1` |
| **Pipe0 pipes** | people-enrichment | Enrichment — augments existing entities | `pipes/run` waterfall |
