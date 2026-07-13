---
name: gtm-pipeline:setup
description: Onboarding skill — walks a new user through installation, API key configuration, PhantomBuster agent IDs, first client setup (auto-research from domain + 5 refinement questions), and a skill tour. Run this first after cloning the repo. Also triggers on "set up gtm skills", "configure gtm", "gtm onboarding", "first time setup".
---

# GTM Pipeline Setup

Welcome. This skill walks you through everything needed to start using the GTM pipeline skills — from installation to your first client ICP.

**Read `~/.claude/skills/gtm-pipeline/_shared/conventions.md` before executing.**

---

## When to Use

- First time after cloning the repo
- Adding a new API key or PhantomBuster agent
- Setting up a new client (use Step 4 only)
- Troubleshooting a missing config value

---

## Step 1 — Verify Installation

Check that the skills are symlinked into Claude's skills directory.

```bash
ls ~/.claude/skills/ | grep gtm
```

**Expected output:** 10 directories — `gtm-setup`, `gtm-company-search`, `gtm-company-enrichment`, `gtm-contact-filter`, `gtm-demo`, `gtm-outreach`, `gtm-people-enrichment`, `gtm-people-search`, `gtm-pipeline`, `gtm-signal-search`.

**If any are missing:**
- Navigate to the repo root
- Run `./install.sh`
- Re-run the check above

Confirm with the user before continuing.

---

## Step 2 — Environment Variables

Check whether an env file exists and which keys are already set.

### Where to look

1. Check `~/.claude/skills/gtm-pipeline/_shared/local.md` for `GTM_ENV_PATH`
2. Default location if not set: `~/.env.gtm`
3. If neither exists: offer to create `~/.env.gtm` now

### Required keys

Walk through each key. For each one, check if it's already set in the env file. Only prompt for missing ones.

| Key | Provider | Required For | Sign Up |
|-----|----------|--------------|---------|
| `PIPE0_API_KEY` | Pipe0 | People search, company search | pipe0.com |
| `FULLENRICH_API_KEY` | FullEnrich | Email enrichment (waterfall) | fullenrich.com |
| `BETTERCONTACT_API_KEY` | BetterContact | Phone enrichment (optional) | bettercontact.rocks |
| `SERPAPI_API_KEY` | SerpAPI | Domain lookup, web search | serpapi.com |
| `PARALLEL_API_KEY` | Parallel AI | FindAll, task enrichment | parallel.ai |
| `APIFY_API_KEY` | Apify | SimilarWeb traffic data | apify.com |
| `FIRECRAWL_API_KEY` | Firecrawl | Website crawl, signal search | firecrawl.dev |
| `PHANTOMBUSTER_API_KEY` | PhantomBuster | LinkedIn automation | phantombuster.com |
| `LINKEDIN_SESSION_COOKIE` | LinkedIn | PhantomBuster auth | Your browser (see below) |
| `LINKEDIN_USER_AGENT` | LinkedIn | PhantomBuster auth (browser user agent string) | Your browser (see below) |
| `OPENROUTER_API_KEY` | OpenRouter | Signal LLM — **legacy/optional** (only for `signal_search.py --llm-backend openrouter`) | openrouter.ai |

**Optional:** If user won't use PhantomBuster (no LinkedIn automation), skip `PHANTOMBUSTER_API_KEY`, `LINKEDIN_SESSION_COOKIE`, `LINKEDIN_USER_AGENT`. For the PhantomBuster Email Finder (Priority-1 email enrichment) also set `GOOGLE_CLIENT_SECRET_FILE` and `GOOGLE_AUTHORIZED_USER_FILE` (see `_shared/local.example.md`); without them the email waterfall simply starts at FullEnrich. `OPENROUTER_API_KEY` is **not needed by default**: signal-search's default `agent` backend has the Claude agent score in-context (see signal-search → Model Routing).

**For `LINKEDIN_SESSION_COOKIE`:** Tell the user to open LinkedIn in Chrome, go to DevTools → Application → Cookies → `li_at` value.

**For `LINKEDIN_USER_AGENT`:** the exact user agent string of that same browser (DevTools console: `navigator.userAgent`). PB scripts require it alongside the cookie.

**Minimum viable set (to run a basic demo):** `PIPE0_API_KEY`, `FULLENRICH_API_KEY`, `SERPAPI_API_KEY`, `PARALLEL_API_KEY`, `FIRECRAWL_API_KEY`. (No LLM key needed — the agent scores signals in-context. `OPENROUTER_API_KEY` only if you opt into the legacy `openrouter` signal backend.)

### Writing keys

If the env file doesn't exist yet:
```bash
touch ~/.env.gtm
```

For each missing key, append it:
```bash
echo 'KEY_NAME=value' >> ~/.env.gtm
```

Then set `GTM_ENV_PATH` in `_shared/local.md`:
```
GTM_ENV_PATH=/Users/{username}/.env.gtm
```

---

## Step 3 — PhantomBuster Agent IDs

Only needed if user will use PhantomBuster for LinkedIn automation.

### Option A — Auto-lookup via PhantomBuster MCP

If the PhantomBuster MCP is available, use `PHANTOMBUSTER_GET_AGENTS_FETCH_ALL` to list all agents. Match agent names to config keys:

| Config Key | Agent Script Name |
|------------|------------------|
| `PB_AGENT_CONNECT` | LinkedIn Auto Connect |
| `PB_AGENT_MESSAGE` | LinkedIn Message Sender / Sales Navigator Message Sender |
| `PB_AGENT_SN_ACCOUNT` | Sales Navigator Account Scraper |
| `PB_AGENT_EMPLOYEES` | LinkedIn Company Employee Finder / LinkedIn Search Export |
| `PB_AGENT_SN_SEARCH` | Sales Navigator Search Export |
| `PB_AGENT_EMAIL` | Email Finder |
| `PB_AGENT_PROFILE` | LinkedIn Profile Scraper |
| `PB_AGENT_JOB_SEARCH` | LinkedIn Search Export (jobs mode) |
| `PB_AGENT_LIKER` | LinkedIn Auto Liker |
| `PB_AGENT_COMMENTER` | LinkedIn Auto Commenter |
| `PB_AGENT_WITHDRAWER` | LinkedIn Invitation Auto Withdraw |
| `PB_AGENT_INBOX` | LinkedIn Inbox Scraper |
| `PB_AGENT_CONNECTIONS` | LinkedIn Connections Export |

Write all matched IDs to `_shared/local.md`:
```markdown
## PhantomBuster Agent IDs

| Config Key | Agent ID |
|------------|----------|
| PB_AGENT_CONNECT | 123456789 |
| PB_AGENT_SN_ACCOUNT | 987654321 |
...
```

### Option B — Manual

If PB MCP is not available, show the user `_shared/local.example.md` and instruct them to:
1. Log in to PhantomBuster dashboard
2. Find each agent and copy its ID from the URL or settings panel
3. Fill in `_shared/local.md` (copy from `local.example.md`)

### Skip entirely

If user doesn't plan to use PhantomBuster, skip this step.

---

## Step 4 — First Client Setup

Ask: "Do you want to set up your first client now? If yes, provide the client's domain (e.g. acme.com)."

If user declines, skip to Step 5.

### 4.1 Create client directory

Ask for a client slug (e.g. `acme` for acme.com). Create the working directory:
```
{slug}-gtm/
├── context/
├── prompts/
└── csv/
    ├── input/
    ├── intermediate/
    └── output/
```

### 4.2 Auto-research the domain

Before asking any questions, research the client's domain automatically. Run three sources in parallel:

**Firecrawl — scrape homepage + about/careers pages:**
Use `firecrawl_scrape` or `firecrawl_crawl` on the domain. Extract:
- What they sell / core product or service
- Target customer (explicit or implied)
- Industries served
- Key value propositions
- Company size / funding stage signals
- Tone of voice from copy

**SerpAPI — recent news and announcements:**
Search: `"{company name}" OR site:{domain}` with recent date filter. Extract:
- Funding rounds
- Company description from third-party sources
- Customer segments mentioned in press

**Parallel web search (if Parallel API key set):**
Query: `"{company}" {domain} — what they sell, who they target, key customers, industries served`

### 4.3 Draft profile.md and icp.md immediately

Do not wait for user input. Draft both files from research findings now. Mark inferred fields with `[INFERRED]`.

**Draft `context/profile.md`:**
```markdown
# {Company Name} — Client Profile

## What They Sell
{product/service description from research}

## Target Buyer
{who buys from them — role, company type, industry}

## Value Proposition
{how they describe their own value}

## Reference Customers / Segments
{any named customers or segments found}

## Tone of Voice
{formal/casual, technical/plain — inferred from website copy}

## Notes
- Profile auto-researched from {domain} on {date}
- Fields marked [INFERRED] should be confirmed with the client
```

**Draft `context/icp.md`:**
```markdown
# {Company Name} — ICP Definition

## Company ICP

### Target Industry
{industries from research} [INFERRED]

### Company Size
- Min employees: [INFERRED — ask to confirm]
- Max employees: [INFERRED — ask to confirm]

### Location
{geography signals from research} [INFERRED]

### Revenue Range
[INFERRED — ask to confirm]

## Contact ICP

### Target Job Titles / Roles
{roles from research} [INFERRED]

### Seniority
[INFERRED]

## Contact Filter Configuration

### Job Tier Definitions
[To be filled after Step 5 refinement questions]

### Industry Tiers
[To be filled after Step 5 refinement questions]

### Location Tiers
[To be filled after Step 5 refinement questions]

### Company Size Filter
[To be filled after Step 5 refinement questions]

### Sort Order
job_tier → industry_tier → comp_loc_tier → person_loc_tier → employee_count_missing → icp_kw_score (desc)
```

Show the user what was auto-filled vs. inferred, then ask **5 refinement questions**:

### 4.4 Five Refinement Questions

1. **Who are your hardest-to-replace customers?**
   (This defines your real ICP — not who you want to sell to, but who gets the most value and keeps paying)

2. **Who should we NOT target?** (Anti-ICP)
   (Industries, company types, roles, or geographies that are a bad fit, take too long to close, or drain support)

3. **Which job titles actually convert?**
   (Not who answers the phone — who signs the contract or champions the deal internally)

4. **What's your geographic priority?**
   (Which countries/regions come first? Are there any we should skip entirely?)

5. **What tone do you use in outreach?**
   (Formal or casual? Any message examples you love or hate? Languages?)

### 4.5 Update files with refinement answers

After collecting answers, update `context/profile.md` and `context/icp.md` with confirmed values. Remove `[INFERRED]` markers where confirmed. Fill in the Contact Filter Configuration section in `icp.md`.

---

## Step 5 — Skill Tour

Show available skills with a one-line summary:

```
## GTM Pipeline Skills

/gtm-pipeline:setup            You are here — onboarding and first client config

/gtm-pipeline:pipeline         Orchestrator — plan and run the full pipeline end-to-end

/gtm-pipeline:company-search   Build a company list from Sales Navigator, Parallel FindAll,
                                Firecrawl Agent, or web scraping

/gtm-pipeline:company-enrichment  Enrich companies with headcount, revenue, growth metrics.
                                   Run ICP scoring (0–100) against your icp.md

/gtm-pipeline:signal-search    Find buying intent signals (funding, hiring, leadership changes).
                                Scores each signal 1–100 for purchase intent

/gtm-pipeline:people-search    Find contacts at target companies by job title, or discover
                                people by persona (no company list needed)

/gtm-pipeline:contact-filter   Classify and rank contacts before enrichment — saves credits
                                by rejecting non-ICP contacts early

/gtm-pipeline:people-enrichment  Enrich contacts with verified work email and phone number

/gtm-pipeline:outreach         Run LinkedIn connection requests and personalized messages
                                via PhantomBuster — one profile at a time

/gtm-pipeline:demo             Generate a demo lead list (~10 enriched contacts + messages)
                                from an ICP description — no company list needed
```

**Suggested first run:**
```
/gtm-pipeline:demo
```
Runs a mini end-to-end pipeline for 10 contacts. Good way to verify keys are working and see the output format before committing credits to a full run.

**For a full pipeline:**
```
/gtm-pipeline:pipeline
```
Assesses your starting data, picks Company-First or Signal-First workflow, estimates costs, and walks you through execution.

---

## Configuration Reference

### Files written by this skill

| File | Purpose |
|------|---------|
| `~/.env.gtm` (or `$GTM_ENV_PATH`) | API keys |
| `~/.claude/skills/gtm-pipeline/_shared/local.md` | PB agent IDs, env path |
| `{slug}-gtm/context/profile.md` | Client profile (what they sell, tone) |
| `{slug}-gtm/context/icp.md` | ICP definition (job tiers, industries, locations, size) |

### Re-running setup

This skill is safe to re-run at any time:
- It only appends missing keys — won't overwrite existing ones
- It will update local.md agent IDs if PB MCP is available
- It will ask before overwriting existing profile.md or icp.md

---

## What's Missing (To Document)

- Automated key validation (test API calls to confirm each key works before writing)
- Multi-client batch setup (configure several clients at once)
- Upgrade path: re-run setup to add new skills after pulling from the repo
