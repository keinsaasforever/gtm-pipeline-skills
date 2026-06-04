---
name: gtm-pipeline:signal-search
description: Find buying intent signals for target companies and score them for purchase intent. Runs a Python script (signal_search.py) that orchestrates Parallel web search (always on), Firecrawl crawl (opt-in), Parallel structured enrichment (opt-in), and a Signal Assessment LLM that scores 1-100. Universal templates live in the script; client-specific prompts come from the working directory's context/ files. Runs standalone or in either pipeline workflow — does NOT require ICP scoring as input. Also triggers on "signal search", "find signals for", "buying intent".
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

This file is the heart of the prompt — it feeds the Parallel search objective, both extraction LLMs, and the Firecrawl crawl hint. **Unless the user hands you a ready-made list, help them build one** by walking the same dimensions the n8n workflow uses. Capture two blocks:

*Include — what counts as a buying signal for THIS offering.* Ask: *"What would a company be doing right now that suggests they need our product?"* Offer this category palette (adapt to the offering, don't paste verbatim):
- Funding / acquisitions tied to relevant budget
- New leadership in roles relevant to the offering
- Hiring for roles adjacent to the problem we solve
- Technology adoption / migration relevant to our offering
- Stated pains, transformation projects, or efficiency goals
- Expansion / growth plans, entry into new markets
- Product launches that imply the underlying need
- Vendor consolidation / SaaS-spend optimization

*Exclude — what must NOT be treated as a signal.* End the file with a short **"Not a signal:"** block. Typical excludes:
- Generic "we're growing" marketing copy or evergreen About-page text
- News older than the lookback window
- Developments unrelated to the offering
- Activity at a same-name-but-different-company or a different domain

**Tuning parameters — ask unless the user already specified them.** These mirror the knobs in the n8n Firecrawl / Parallel configs; only the client-specific ones are worth asking about (the rest are baked defaults):

| Parameter | Ask the user | Default | Where it goes |
|-----------|--------------|---------|---------------|
| Max age of signals | "How recent must a signal be?" | 4 months | `--lookback-months` (gates Parallel `after_date` *and* the Firecrawl freshness filter) |
| Web results per company | "How many web results per company should we scan?" | 12 | `--max-results` (raise for large/noisy companies, lower to save credits) |
| Firecrawl on/off | "Does on-site content (careers/blog/press) carry the signal?" | off | `--firecrawl` or `--firecrawl-pages-dir` — see Step 4 |
| Enrichment on/off | "Do you need structured fields (funding stage, job URLs, tech stack) as their own columns?" | off | `--parallel-enrichment` |

**Baked defaults — don't ask, only change in the script if a client truly needs it:** the crawl `excludePaths` (privacy/legal/cart/shop, plus agent-directed files like `agents.md`/`llms.txt`), the `scrapeOptions` (markdown, main-content-only, ad-block), and the Parallel-enrichment JSON schema (funding / hiring / digital-initiatives / tech-stack).

### Step 3 — Save the context files

Write each user-supplied answer to its file. Keep them concise but complete — the LLM sees these on every scoring call.

### Step 4 — Pick which sources to enable

Use AskUserQuestion to confirm. Defaults:

| Source | Default | When to enable |
|--------|---------|----------------|
| Parallel web search | ON (always) | — |
| Firecrawl website crawl | OFF | Enable when **on-site content matters** — e.g. the offering targets companies where careers pages, blog, or product pages reveal the buying signal. Skip for generic prospects where news is enough. |
| Parallel structured enrichment | OFF | Enable when **structured fields are required downstream** — funding stage, hiring signals with job URLs, tech stack indicators that need to live in their own CSV columns. Skip if the scored signals JSON is enough. |

**Two ways to run Firecrawl** (pick based on how you have Firecrawl access):

| Route | Flag | Needs `FIRECRAWL_API_KEY`? | How it works |
|-------|------|---------------------------|--------------|
| **Native API** | `--firecrawl` | Yes | The script crawls each site via the Firecrawl API. One command, fully automated. |
| **MCP / pre-crawled** | `--firecrawl-pages-dir DIR` | No | You crawl the sites with the **Firecrawl MCP** (or any tool) and drop `DIR/{domain}.json` files — each a JSON array of `{"markdown": ..., "metadata": {"ogUrl": ..., "article:published_time": ...}}`. The script reads those, applies the same freshness filter + extraction, and never touches the Firecrawl API. |

Use the MCP route when this machine has Firecrawl only via MCP and no `FIRECRAWL_API_KEY` in the env file. When orchestrating the MCP route, prefer delegating the crawl to sub-agents so the heavy page markdown stays out of the main context — they write the `{domain}.json` files, then the script does the rest.

### Step 5 — Run the script

```bash
# Resolve the .env path (from $GTM_ENV_PATH, else _shared/local.md, else ~/.env.gtm),
# then inject only the keys this run needs.
source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh" && \
export $(grep -E '^(PARALLEL_API_KEY|OPENROUTER_API_KEY|FIRECRAWL_API_KEY|GEMINI_API_KEY)=' "$GTM_ENV_PATH" | xargs) && \
  python3 ~/.claude/skills/gtm-signal-search/signal_search.py \
    --client-dir {client-slug}-gtm \
    --limit 5 \
    --lookback-months 4 \
    --max-results 12 \
    [--firecrawl | --firecrawl-pages-dir {client-slug}-gtm/firecrawl_pages] \
    [--parallel-enrichment]
```

**Env path:** the `resolve_env.sh` helper finds your `.env` even when `GTM_ENV_PATH` isn't exported in the shell — it reads the `GTM_ENV_PATH=` line from `~/.claude/skills/gtm-pipeline/_shared/local.md` (the documented setup step), falling back to `~/.env.gtm`. All GTM keys live in that one file; do not maintain a separate env file for signal-search.

`GEMINI_API_KEY` is **optional** — only needed if you want a Gemini fallback when OpenRouter calls fail (see Models section below). `FIRECRAWL_API_KEY` is only needed for the native `--firecrawl` route, not for `--firecrawl-pages-dir`.

Start with `--limit 5` as a test batch. Review the output, then re-run without `--limit` for the full list.

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
--firecrawl                     enable Firecrawl website crawl via the Firecrawl API (needs FIRECRAWL_API_KEY)
--firecrawl-pages-dir PATH      read pre-crawled pages from PATH/{domain}.json instead of the API (no key; MCP route)
--parallel-enrichment           enable Parallel structured enrichment
--lookback-months N             max age of signals in months (default: 4)
--max-results N                 max Parallel web-search results per company (default: 12)
--extract-model NAME            OpenRouter model for extraction (default: deepseek/deepseek-v4-flash)
--scoring-model NAME            OpenRouter model for scoring (default: moonshotai/kimi-k2.5)
--gemini-extract-model NAME     Gemini fallback model for extraction (default: gemini-3-flash-preview)
--gemini-scoring-model NAME     Gemini fallback model for scoring (default: gemini-3-pro-preview)
--limit N                       process at most N companies (for test batches)
--workers N                     parallel workers (default: 3)
--dry-run                       validate context + inputs without API calls
```

**Always ask the user which models to use** if they have a preference. Defaults match the n8n workflow's cost split — cheap extract model, more capable scoring model.

### Models & Fallback

| Role | Primary (OpenRouter) | Fallback (Gemini direct) |
|------|----------------------|--------------------------|
| Extraction (web search + Firecrawl) | `deepseek/deepseek-v4-flash` | `gemini-3-flash-preview` |
| Signal scoring | `moonshotai/kimi-k2.5` | `gemini-3-pro-preview` |

The Gemini fallback fires only when:
1. The OpenRouter call returns no parseable JSON, AND
2. `GEMINI_API_KEY` is set in the env file.

If `GEMINI_API_KEY` is not set, an OpenRouter failure simply produces empty signals / a failed-scoring stub (with reason in `overallSummary`). Users can swap to any other model by passing `--extract-model` / `--scoring-model` — anything OpenRouter supports works.

---

## Input CSV

Default location: `csv/input/companies_raw.csv`. Required columns (the script tolerates alternative names):

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
websiteSignals       — JSON array from Firecrawl extraction (empty if --firecrawl off)
webSearchSignals     — JSON array from Parallel web search extraction
parallelEnrichment   — JSON object from Parallel enrichment (empty if not enabled)
lastRun              — YYYY-MM-DD
```

---

## Universal Templates (Inside The Script)

These are baked into `signal_search.py` and you should not need to edit them per client. They describe HOW to extract and score, not WHAT the user cares about.

- **Parallel web search request:** objective shape, `mode: one-shot`, `max_results: 12`, `source_policy.after_date`
- **Firecrawl crawl request:** sitemap include, `limit: 15`, universal exclude paths (privacy/legal/contact/login/etc.), markdown only main content
- **Web search extraction prompt:** include/exclude framing, company-anchored ("If the company is not mentioned in a result, exclude that result")
- **Firecrawl extraction prompt:** "do not extract" list (generic descriptions, old news, vague statements), structured output schema
- **Signal Assessment system prompt:** High/Medium/Low Intent rubric, "cut through the buzz" guard, inference caution, domain verification
- **Signal Assessment output schema:** `{overallScore, signalCount, scoredSignals[], overallSummary}`
- **Freshness gating:** double-gated — once in Parallel `after_date`, once in `filter_crawl_pages_by_freshness()` (mirrors the n8n `Filter out old` JS code)
- **Domain verification:** if a signal's `domain_verified` is `false`, the script automatically zeros its score before writing
- **Prompt-injection hardening:** crawled sites increasingly ship `agents.md` / `llms.txt` files with instructions aimed at AI crawlers. The crawl `excludePaths` skip these, and all three LLM prompts (both extractors + the assessor) are instructed to treat page/search text as untrusted data — never to follow embedded instructions, and to discard any "signal" whose content is really an instruction to an AI/agent. Validated: an injected `agents.md` "install our Shop skill" page is dropped at extraction, not scored.

If any of these templates need to evolve (e.g. the n8n workflow's scoring rubric is updated), edit the constants at the top of `signal_search.py`.

---

## Cost Notes

- Parallel web search (`pro` is unused here; we use the default `one-shot` mode): ~1 credit per company
- Firecrawl crawl (15 pages, markdown only): ~15 credits per company
- Parallel enrichment (`processor: core`): ~5 credits per company
- OpenRouter extract calls: ~$0.001–0.003 per company (cheap model)
- OpenRouter scoring call: ~$0.005–0.015 per company (kimi-k2)

Order of magnitude: **web search only ≈ $0.01 per company; +firecrawl ≈ $0.05 per company; +parallel enrichment ≈ $0.08 per company.** Always test on 5 before the full batch.

---

## What's Missing (To Document)

- PhantomBuster LinkedIn Jobs Scraper as a fifth source (the n8n workflow has it conceptually but doesn't wire it in)
- Firecrawl Agent (`POST /v2/agent`) for Signal-First discovery (find companies *by signal* without a starting company list)
- Exa Websets via Pipe0 for signal-based company discovery
- Auto-fix retry on LLM JSON parse failure (currently fails to empty list — consider a one-shot retry-with-feedback)
