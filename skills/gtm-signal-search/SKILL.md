---
name: gtm-pipeline:signal-search
description: Find buying intent signals for target companies and score them for purchase intent. Runs a Python script (signal_search.py) that orchestrates Parallel web search (always on), a cheap site-search fallback restricted to the company's own domain for companies web search left without a signal (three interchangeable providers, selectable via --site-search: TinyFish, Firecrawl `/v2/search`, Tavily), Parallel structured enrichment (opt-in), and a Signal Assessment LLM that scores 1-100. Universal templates live in the script; client-specific prompts come from the working directory's context/ files. Runs standalone or in either pipeline workflow — does NOT require ICP scoring as input. Also triggers on "signal search", "find signals for", "buying intent".
---

# Signal Search

Find buying intent signals for target companies and score each 1–100. Universal extraction prompts, scoring rubric, and request shapes are baked into `signal_search.py` (ported from the live n8n workflow `lE1svjQ5TrgZ0bQy`). Anything client-specific — what we sell, who the ICP is, what kinds of signals matter — is loaded from `{client-slug}-gtm/context/` files at runtime.

**Read `~/.claude/skills/gtm-pipeline/_shared/conventions.md` before executing.**

---

## When to Use

- **Standalone:** Score signals on any company list (raw or pre-filtered)
- **Company-First workflow:** Run on ICP-scored companies (gate at `icp_score >= 70` to save credits)
- **Signal-First workflow:** Run as the discovery step

The skill does not require ICP scoring as input. It does require an ICP definition (text) so the scoring step understands fit.

---

## The Three Required Context Files

Before the script can run, the working directory must contain:

```
{client-slug}-gtm/context/
├── icp.md             ← ICP definition (industries, geography, size, roles, exclusions)
├── offering.md        ← What we sell, to whom, key value props (used in the scoring prompt)
└── signal_criteria.md ← What counts as a buying signal for THIS offering: an INCLUDE list + a short "not a signal" EXCLUDE list
```

If any of these are missing, **collect them from the user before running the script.** Do not invent them. Do not copy them from a previous client's gtm folder.

**Fallback:** If `offering.md` is missing but `profile.md` exists (written by `gtm-setup`), the script will use `profile.md` instead. Prefer `offering.md` when possible — `profile.md` is broader (includes tone, customer segments, etc.) and produces a noisier scoring prompt. If `profile.md` is the only thing available, consider asking the user to extract the offering-specific paragraphs into a dedicated `offering.md`.

### Step 1 — Check for context files

```bash
ls {client-slug}-gtm/context/
```

If `icp.md`, `offering.md`, and `signal_criteria.md` all exist, proceed to Step 4.

### Step 2 — Ask the user for what's missing

Use AskUserQuestion (or a direct prose ask) to collect each missing piece. Suggested wording for each:

**ICP (`icp.md`):**
- Industries (include / exclude)
- Geography
- Company size (employees, revenue)
- Decision-maker roles
- Anything else that disqualifies a company (e.g. "must have a public website", "exclude pure consultancies")

**Offering (`offering.md`):**
- What you sell (one paragraph)
- The 3–5 main capabilities
- Who it's for (target buyer profile)
- The primary outcome you deliver
- Any flagship product or differentiator

**Signal criteria (`signal_criteria.md`) — INCLUDE *and* EXCLUDE:**

This file is the heart of the prompt — it feeds the Parallel search objective and both extraction LLMs. **Unless the user hands you a ready-made list, help them build one** by walking the same dimensions the n8n workflow uses. Capture two blocks:

*Include — what counts as a buying signal for THIS offering.* Ask: *"What would a company be doing right now that suggests they need our product?"* Offer this category palette (adapt to the offering, don't paste verbatim):
- Funding / acquisitions tied to relevant budget
- New leadership in roles relevant to the offering
- Hiring for roles adjacent to the problem we solve
- Technology adoption / migration relevant to our offering
- Stated pains, transformation projects, or efficiency goals
- Expansion / growth plans, entry into new markets
- Product launches that imply the underlying need
- Vendor consolidation / SaaS-spend optimization

*Exclude — what must NOT be treated as a signal.* End the file with a short **"Not a signal:"** block.
**Only the include half reaches the search query** (`objective_bullets()` cuts the file at the first
"Not a signal" / "Exclude" line and drops markdown headings). That is deliberate: the exclude half
normally names the seller's own product ("evidence they already use X"), and the H1 normally carries
the client's name, so interpolating the whole file turned the seller into a search term — the
Reduzer run got reduzer.com and the vendor's own aggregator profile back as "evidence" for small
Norwegian contractors. The exclude half still reaches extraction and scoring. Keep the seller's name
out of the include bullets for the same reason. Typical excludes:
- Generic "we're growing" marketing copy or evergreen About-page text
- News older than the lookback window
- Developments unrelated to the offering
- Activity at a same-name-but-different-company or a different domain

**Tuning parameters — ask unless the user already specified them.** These mirror the knobs in the n8n Firecrawl / Parallel configs; only the client-specific ones are worth asking about (the rest are baked defaults):

| Parameter | Ask the user | Default | Where it goes |
|-----------|--------------|---------|---------------|
| Max age of signals | "How recent must a signal be?" | 4 months | `--lookback-months` (gates Parallel `after_date` *and* the source freshness filter on search results and crawled pages) |
| Web results per company | "How many web results per company should we scan?" | 12 | `--max-results` (raise for large/noisy companies, lower to save credits) |
| Site search | — (don't ask) | tinyfish | Recent pages from the company's own domain (subdomains included) for the companies still without a signal — `--site-search {tinyfish,firecrawl,tavily}`, see Step 5c |
| Enrichment on/off | "Do you need structured fields (funding stage, job URLs, tech stack) as their own columns?" | off | `--parallel-enrichment` |

**Baked defaults — don't ask, only change in the script if a client truly needs it:** the `excludePaths` that filter site-search hits (privacy/legal/cart/shop, careers/job ads, plus agent-directed files like `agents.md`/`llms.txt`), the `scrapeOptions` (markdown, main-content-only, ad-block), and the Parallel-enrichment JSON schema (funding / hiring / digital-initiatives / tech-stack).

### Step 3 — Save the context files

Write each user-supplied answer to its file. Keep them concise but complete — the LLM sees these on every scoring call.

### Step 4 — Pick which sources to enable

Use AskUserQuestion to confirm. Defaults:

| Source | Default | When to enable |
|--------|---------|----------------|
| Parallel web search | ON (always) | — |
| Site-search fallback | LAST RESORT | Runs after scoring on the companies web search left without a signal (Step 5c). Three interchangeable providers via `--site-search`: TinyFish (free, default recommendation), Firecrawl, Tavily (1 credit) — pick one per run, or run more than one to compare. Nothing to decide here unless comparing providers. |
| Parallel structured enrichment | OFF | Enable when **structured fields are required downstream** — funding stage, hiring signals with job URLs, tech stack indicators that need to live in their own CSV columns. Skip if the scored signals JSON is enough. |

### Step 5 — Run the script

```bash
# Resolve the .env path (from $GTM_ENV_PATH, else _shared/local.md, else ~/.env.gtm),
# then inject only the keys this run needs. Default backend "agent" needs ONLY PARALLEL_API_KEY.
source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh" && \
export $(grep -E '^(PARALLEL_API_KEY|FIRECRAWL_API_KEY)=' "$GTM_ENV_PATH" | xargs) && \
  python3 ~/.claude/skills/gtm-signal-search/signal_search.py \
    --client-dir {client-slug}-gtm \
    --limit 5 \
    --lookback-months 2 \
    --max-results 12 \
    [--parallel-enrichment]
```

**Backends (see Model Routing below):** the default `--llm-backend agent` makes the script
**collect-only** — it runs Parallel/Firecrawl and writes raw evidence per company to
`csv/intermediate/signals_raw/{domain}.json` (and inline in the CSV), leaving `overallScore`
empty with `overallSummary = PENDING_AGENT_PROCESSING`. **You (the agent) then extract + score
each company in-context** per the Agent Scoring Rubric below and write the scores back — no
third-party LLM, no nested `claude -p`. This is the path both interactively and under a deployed
`claude -p` webhook. For a fully autonomous run with no agent in the loop, pass
`--llm-backend claude-cli` (shells `claude -p --model opus`) or the legacy `--llm-backend openrouter`.

**Env path:** the `resolve_env.sh` helper finds your `.env` even when `GTM_ENV_PATH` isn't exported — it reads the `GTM_ENV_PATH=` line from `~/.claude/skills/gtm-pipeline/_shared/local.md`, falling back to `~/.env.gtm`. All GTM keys live in that one file.

`OPENROUTER_API_KEY`/`GEMINI_API_KEY` are needed **only** for `--llm-backend openrouter`. `FIRECRAWL_API_KEY` / `TINYFISH_API_KEY` / `TAVILY_API_KEY` are only needed for the matching `--site-search` provider, not for `--firecrawl-pages-dir`.

**Lookback default is 2 months (~60 days)** — signals older than that are not buying intent.

Start with `--limit 5` as a test batch. Review the output, then re-run without `--limit` for the full list.

### Step 5b — Agent Scoring Rubric (backend = `agent`)

After the collect-only run, score each company yourself (use the **opus** model per Model Routing —
directly, or an Opus subagent). Read the raw evidence from `csv/intermediate/signals_raw/{domain}.json`
(or the `webSearchSignals`/`websiteSignals` columns). Score each candidate on **two axes, in order**:

**Axis 1 — Attribution / proximity (the gate).** Does the development genuinely stem from *this*
company (or the named person at it), or is it a generic industry / peer / market story bent onto it?
- **Direct** (company or its named leader is the actor) → passes.
- **Adjacent** (a named partner/customer/competitor acts) → keep only if it forces an action *at this
  company*; otherwise drop.
- **Generic** (sector trend, "companies like this…", a trend piece that merely lists the company) →
  **not a signal. Score 0.** Never invent a connection between industry news and this company.

Only a signal that passes Axis 1 proceeds. Then apply the remaining keep-gates:
- **Fresh** — within the lookback window (≤ `--lookback-months`). No parseable date ⇒ not fresh ⇒ drop.
  **The date that counts is when the development happened or was announced, not when a page
  carrying it was published.** A fresh page that re-reports an older announcement carries the older
  date (HOCHTIEF, 2026-09-18: a 24 Jul article about a data-centre order announced on 7 Jul). The
  script already dropped every result without a date inside the window; this one is yours.
- **Sourced** — has a live `source_url` **and** a `date`. Drop unlinkable/undated signals. The URL
  is **the article or post itself**: a homepage, a news/press listing or a company profile (a
  LinkedIn company page) is not a source, and `sanitize.py` drops signals that cite one. When the
  evidence is a listing page, open it and cite the item's own URL.
- **Real & on-target** — the source text actually supports the claim (re-read it; a "CTO hiring" post
  can be a mislabeled lab role), and the geo/segment matches the ICP.
- **Intent ≠ incumbency** — "already owns a competing/adjacent solution" is neutral/negative, not hot;
  reposition as complement/ICP-fit.

**Axis 2 — Offering fit (priority + hook).** For signals that pass Axis 1, how tightly does the
development connect to what we sell? This sets the score band and the outreach hook: a company-real
signal that directly implies our need = high-priority; a company-real signal only loosely related =
low-priority ICP-fit, not hot intent. **Proximity decides *whether* to reach out; offering fit decides
*how hard* and *with what hook*.**

Then write `overallScore` (0–100), `signalCount`, `scoredSignals` (each with `source_url` + `date`
+ `attribution` of direct/adjacent/generic),
and a one-line actionable `overallSummary` back into `signals.csv`. Companies with **no** surviving
signal are demoted to ICP-fit (score reflects that) — never force-fit a stale/weak signal as intent.
**`overallSummary` restates kept signals only.** It feeds message hooks, so an event that failed a
gate must not come back through it (perma-trade, 2026-09-18: dropped news reached the hooks through
free-text fit fields). With no kept signal it says so and nothing else.
Downstream `sanitize.py` drops any signal still lacking a source/date, citing a non-article URL, or left `PENDING`.

### Step 5c — Site-search fallback (last resort): the companies still without a signal

Web search misses what a company publishes only on its own site: project news, branch openings,
press releases nobody syndicated. After 5b, write every company with **no kept signal** (none passed
the gates, or only loosely fitting ones did, per Axis 2) to `csv/input/companies_nosignal.csv` (same
columns as the input). Only these get the fallback; a company with a kept signal never does.

**Why no crawl.** A full site crawl takes pages in sitemap order — archives first, not newest first.
On leonhard-weiss.de (2026-09-21) crawling spent 9 credits on archived press releases and missed all
3 items inside the window. A search restricted to the company's own domain, with a date range, finds
the recent items directly and far cheaper. **Never crawl.**

**Run the script's own site search (recommended).** The script does the search-then-fetch itself —
no manual curl or MCP calls needed:

```bash
source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh" && \
export $(grep -E '^(TINYFISH_API_KEY|FIRECRAWL_API_KEY|TAVILY_API_KEY)=' "$GTM_ENV_PATH" | xargs) && \
python3 ~/.claude/skills/gtm-signal-search/signal_search.py --client-dir {client-slug}-gtm \
  --input-csv {client-slug}-gtm/csv/input/companies_nosignal.csv --crawl-only \
  --site-search tinyfish
```

Pick the provider with `--site-search {tinyfish,firecrawl,tavily}` — only export the key for the one
you picked. **`tinyfish` is the default recommendation:** free, and each search hit already carries
its own display date. `firecrawl` and `tavily` stay available to run the same companies through for
comparison. `--firecrawl` still works as a shorthand for `--site-search firecrawl` (old callers).

All three query `site:{domain}` (or the equivalent domain filter) + the news words (`news OR press OR
presse OR pressemitteilung OR aktuelles`), restricted to the company's own domain (subdomains
included) and the lookback window, then run the same hit filter (`keep_site_hits()`: drop
careers/legal/cart/PDF paths, dedupe, cap at 5 pages) before fetching content:
- **TinyFish — free.** `search` (`include_domains`, `after_date`) then one `fetch` call for the kept
  URLs. The search hit's own `date` is a localized display string ("22.09.2026", "vor 6 Tagen") and
  isn't parsed; `fetch`'s `published_date` (ISO or null) is used for freshness instead.
- **Tavily — 1 credit per company.** Content comes back in the same search call, no second fetch.
  `raw_content` was empty for roughly half the hits in a live test (2026-09-30), so the script falls
  back to `content`. Its `published_date` is Tavily's own estimate ("published or last updated"), not
  necessarily the article's own dateline — the 5b freshness rubric (the date the source prints for
  itself, read out of the text) is still what decides whether a page survives.
- **Firecrawl `/v2/search`:** `site:{domain} news OR press OR presse OR pressemitteilung OR
  aktuelles` with `tbs: "sbd:1,qdr:m{N}"` (past N months, newest first; `sources: ["web"]`,
  `limit: 10`; 2 credits), then `/v2/scrape` per kept hit (1 credit; `"parsers": []` so a PDF isn't
  billed per page). Hits carry no date. A custom range (`cdr:1,cd_min:…`) is ignored, and a bare
  `site:{domain}` query with no other words ignores any date filter and returns homepages, subdomain
  roots and legal pages — keep the news words.

Cost per company: **TinyFish free; Tavily 1 credit; Firecrawl ≤ 2 credits for the search + 1 per
scraped page (≤ 7 total).**

**Alternative — no API key: fetch the pages yourself (agent/MCP route).** When you only have TinyFish
or Firecrawl via MCP and no `*_API_KEY` in the env, run the search and fetch yourself instead of
letting the script call the provider. At most **5 fetched pages per company**; skip careers/job ads,
legal pages, product pages, and PDFs; fetch only hits whose title/snippet matches
`signal_criteria.md`. Map each fetched page to the shape `{"markdown", "metadata": {"title",
"sourceURL", optional "publishedTime"}}` (TinyFish: `text` → `markdown`; `title`, `final_url`,
`published_date` → `metadata.title`, `metadata.sourceURL`, `metadata.publishedTime`). Save the fetched
pages, unchanged, as one JSON array in `{client-slug}-gtm/firecrawl_pages/{domain}.json`, `{domain}`
being the row's `company_domain` (no `www.`). With `FIRECRAWL_API_KEY`, fetch straight to disk so the
markdown never passes through your context:

```bash
source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh" && \
export $(grep -E '^FIRECRAWL_API_KEY=' "$GTM_ENV_PATH" | xargs) && \
for u in "$HIT_URL_1" "$HIT_URL_2"; do
  curl -s -m 120 -X POST https://api.firecrawl.dev/v2/scrape -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
    -H "Content-Type: application/json" -d "{\"url\":\"$u\",\"formats\":[\"markdown\"],\"onlyMainContent\":true,\"parsers\":[]}"; echo
done | python3 -c "import json,sys; json.dump([json.loads(l)['data'] for l in sys.stdin if l.strip()], open('{client-slug}-gtm/firecrawl_pages/{domain}.json','w'), ensure_ascii=False)"
```

With TinyFish or Firecrawl only as MCP, run the search/fetch in sub-agents that write the result the
same way. Then run the filter pass over all of them:

```bash
python3 ~/.claude/skills/gtm-signal-search/signal_search.py --client-dir {client-slug}-gtm \
  --input-csv {client-slug}-gtm/csv/input/companies_nosignal.csv --crawl-only \
  --firecrawl-pages-dir {client-slug}-gtm/firecrawl_pages
```

`--crawl-only` skips the web search (these companies had theirs) and writes `signals_crawl.csv` and
`signals_raw_crawl/{domain}.json`, so the first pass stays as it was — true for either route above. A
page is kept only when its own date is inside the window: the date printed on the page first, its
metadata only when the text has none. `website_urls_crawled` lists every page fetched, the dropped
ones included. Score the kept pages with the 5b rubric. A listing/search-result page is never the
source: cite the item's own URL, as 5b says. Write the result into the company's row in `signals.csv`.
A company still without a kept signal stays ICP-fit.

With no agent in the loop (`claude-cli` backend), `--crawl-only --site-search {tinyfish,firecrawl,tavily}`
runs the chosen provider's site search itself (cost ceilings above).

### Step 6 — Review and log

Open `csv/intermediate/signals.csv`. Inspect actual rows for 2–3 companies:
- Do `scoredSignals` cite real news/website content, not hallucinations?
- Are `domain_verified=false` signals correctly zeroed?
- Does `overallSummary` give an actionable outreach hook?

Append a run summary to `run_log.md` per `conventions.md` (records processed, hit rate, sources enabled, cost notes, quality observations).

---

## Script Arguments

```
--client-dir PATH               {client-slug}-gtm working directory (required)
--input-csv PATH                override input (default: csv/input/companies_raw.csv)
--output-csv PATH               override output (default: csv/intermediate/signals.csv)
--site-search {tinyfish,firecrawl,tavily}   site-search fallback provider (last-resort with --crawl-only; needs the matching *_API_KEY)
--firecrawl                     alias for --site-search firecrawl (old callers)
--firecrawl-pages-dir PATH      read fetched pages from PATH/{domain}.json instead of calling a site-search API (no key; TinyFish/MCP route)
--crawl-only                    site-search fallback pass (Step 5c): no web search; writes signals_crawl.csv + signals_raw_crawl/
--parallel-enrichment           enable Parallel structured enrichment
--llm-backend {agent,claude-cli,openrouter}   where extraction+scoring happen (default: agent)
--raw-evidence-dir PATH         where the agent backend writes raw evidence (default: csv/intermediate/signals_raw/)
--lookback-months N             max age of signals in months (default: 2 ≈ 60 days)
--max-results N                 max Parallel web-search results per company (default: 12)
--claude-extract-model NAME     claude-cli backend: extraction model (default: opus)
--claude-scoring-model NAME     claude-cli backend: scoring model (default: opus)
--extract-model NAME            openrouter backend only: extraction model (legacy)
--scoring-model NAME            openrouter backend only: scoring model (legacy)
--gemini-extract-model NAME     openrouter backend only: Gemini fallback for extraction
--gemini-scoring-model NAME     openrouter backend only: Gemini fallback for scoring
--limit N                       process at most N companies (for test batches)
--workers N                     parallel workers (default: 3)
--dry-run                       validate context + inputs without API calls
```

### Model Routing

Scoring/extraction is **agent work** — no third-party LLM on the default path. Models via aliases
(`opus`/`sonnet` → always latest, no version pinning):

| Backend | When | How extraction + scoring run |
|---------|------|------------------------------|
| **`agent`** (default) | Interactive, or deployed via `claude -p "/gtm-pipeline:…"` | Script collects evidence; **you (the agent)** score it in-context with **opus** (or an Opus subagent) per the Agent Scoring Rubric. No LLM key, no nested `claude -p`. |
| **`claude-cli`** | Cron/webhook with no agent in the loop | Script shells `claude -p --model opus`. Self-contained. |
| **`openrouter`** | Dormant legacy (kept on `main`, **inert**) | `deepseek`/`kimi` via OpenRouter + optional Gemini fallback. **Disabled by a kill switch:** the flag errors out unless `GTM_ALLOW_OPENROUTER=1` is also set. Needs `OPENROUTER_API_KEY`. Unreliable for small/German orgs (returned empty/JSON-None across past runs) — prefer `agent`. |

Do not silently swap models; the routing above is the convention (see `_shared/conventions.md` → Model Routing).

---

## Input CSV

Default location: `csv/input/companies_raw.csv`. In the Company-First workflow the input is the gated scored list, not the raw list: filter `csv/intermediate/companies_scored.csv` to `icp_score >= 70` (if gating) and pass that file via `--input-csv`. Required columns (the script tolerates alternative names):

| Canonical | Alternatives accepted |
|-----------|----------------------|
| `company_name` | `name` |
| `company_website` | `website` |
| `company_domain` | (derived from website if missing) |

All other columns in the input CSV are preserved in the output.

---

## Output CSV

`csv/intermediate/signals.csv` — original columns + these signal columns:

```
overallScore         — 0–100 aggregate buying intent
signalCount          — number of distinct scored signals
scoredSignals        — JSON array of {date, summary, score, domain_verified, reasoning, keyInsight}
overallSummary       — one-line actionable take
websiteSignals       — JSON array from site-search extraction (empty if --site-search off)
webSearchSignals     — JSON array from Parallel web search extraction
parallelEnrichment   — JSON object from Parallel enrichment (empty if not enabled)
lastRun              — YYYY-MM-DD
```

---

## Universal Templates (Inside The Script)

These are baked into `signal_search.py` and you should not need to edit them per client. They describe HOW to extract and score, not WHAT the user cares about.

- **Parallel web search request:** objective shape, `mode: one-shot`, `max_results: 12`, `source_policy.after_date`
- **Site-search requests (three interchangeable providers, `--site-search`):** all three search `site:{domain}` / `include_domains=[domain]` + the same news words (`news OR press OR presse OR pressemitteilung OR aktuelles`), restricted to the lookback window. Firecrawl `/v2/search` — `tbs: "sbd:1,qdr:m{lookback_months}"`, `sources: ["web"]`, `limit: 10` (2 credits) then `/v2/scrape` per kept hit (1 credit each). TinyFish `search` (free) — `include_domains`, `after_date` — then one `fetch` call (free) for the kept URLs. Tavily `search` (1 credit) — `include_domains`, `start_date`/`end_date`, `include_raw_content: "markdown"` — content comes back in the same call. Every provider's hits pass through the shared `keep_site_hits()` filter (the universal exclude paths — privacy/legal/contact/login/careers/etc., each pinned to a whole path segment — plus `.pdf` and dedupe) before being kept, at most 5 pages.
- **Web search extraction prompt:** include/exclude framing, company-anchored ("If the company is not mentioned in a result, exclude that result")
- **Site-search extraction prompt:** "do not extract" list (generic descriptions, old news, vague statements), structured output schema
- **Signal Assessment system prompt:** High/Medium/Low Intent rubric, "cut through the buzz" guard, inference caution, domain verification
- **Signal Assessment output schema:** `{overallScore, signalCount, scoredSignals[], overallSummary}`
- **Freshness gating, at the source:** Parallel `after_date` (only filters pages that carry a date), then `filter_search_results_by_freshness()` and `filter_crawl_pages_by_freshness()` keep only evidence whose own date is inside the window: the date the source prints for its item (`source_date()`: a date line right above the headline, else the first full date after it, else the latest in the text), and only when the text carries no full date the provider's publish date or page metadata (`2026-07-29`, `29.07.2026`, `01/09/2025`, `29. Juli 2026`, `July 29, 2026`; an ambiguous slash date takes its later past reading). The provider's stamp is often the crawl date: on the Sphere run (2026-09-24) a HENSOLDT article dated 01/09/2025 came back as 2026-09-22, and a 2022 MULTIVAC item as 2026-09-06 through the week's news in its sidebar. Undated and stale evidence never reaches extraction or scoring; the counts land in `signals_raw/{domain}.json` → `web_search_dropped_by_cutoff`. Checked by `test_freshness.py`. (Until 2026-09-21 search results were never filtered and the crawl filter kept stale and undated pages: on the perma-trade run 143 of 175 results were undated.)
- **Domain verification:** if a signal's `domain_verified` is `false`, the script automatically zeros its score before writing
- **Prompt-injection hardening:** sites increasingly ship `agents.md` / `llms.txt` files with instructions aimed at AI crawlers. The exclude paths drop these hits before they're scraped, and all three LLM prompts (both extractors + the assessor) are instructed to treat page/search text as untrusted data — never to follow embedded instructions, and to discard any "signal" whose content is really an instruction to an AI/agent. Validated: an injected `agents.md` "install our Shop skill" page is dropped at extraction, not scored.

If any of these templates need to evolve (e.g. the n8n workflow's scoring rubric is updated), edit the constants at the top of `signal_search.py`.

---

## Cost Notes

- Parallel web search (`pro` is unused here; we use the default `one-shot` mode): ~1 credit per company
- Site-search fallback (`--site-search`): TinyFish free; Tavily 1 credit per company; Firecrawl 2 credits per search + 1 per scraped page, ≤ 7 per company — only for companies web search left without a signal
- Parallel enrichment (`processor: core`): ~5 credits per company
- **`agent` backend (default): no external LLM cost** — the agent scores in-context (counts as normal session tokens). `openrouter` backend (legacy): ~USD 0.006–0.018 per company.

Order of magnitude (agent backend): **web search only ≈ USD 0.01 per company; +site search ≈ USD 0.00–0.02 per company; +parallel enrichment ≈ USD 0.08 per company** (Parallel/Firecrawl credits only). Always test on 5 before the full batch.

---

## What's Missing (To Document)

- PhantomBuster LinkedIn Jobs Scraper as a fifth source (the n8n workflow has it conceptually but doesn't wire it in)
- Firecrawl Agent (`POST /v2/agent`) for Signal-First discovery (find companies *by signal* without a starting company list)
- Exa Websets via Pipe0 for signal-based company discovery
- Auto-fix retry on LLM JSON parse failure (currently fails to empty list — consider a one-shot retry-with-feedback)
