---
name: gtm-pipeline:pipeline
description: Plan and execute a full GTM lead generation pipeline, from company discovery to enriched contacts. Use when a client needs end-to-end orchestration spanning multiple GTM skills: determines Company-First vs Signal-First workflow, assesses starting data, plans the skill sequence with cost estimates for user approval, then chains skill outputs. Not for demo requests (use gtm-demo) or single-step requests (invoke that skill directly). Also triggers on "run the pipeline", "start pipeline for [client]", "full pipeline", "Stripe payment trigger".
---

# Pipeline

Plan and orchestrate a full GTM pipeline — from discovery to enriched contact list. Determines which skills to run, in what order, based on client requirements and starting data.

**Read `~/.claude/skills/gtm-pipeline/_shared/conventions.md` before executing.**

---

## When to Use

- Client needs a complete lead generation pipeline (not just one skill)
- You need to determine the right workflow based on what data exists
- Stripe payment trigger: execute full pipeline
- Any request that spans multiple GTM skills

---

## Step 1 — Assess Starting Point

Ask: **What data does the user have?**

| Starting Point | Available Data | Next Action |
|----------------|---------------|-------------|
| **Nothing** (just an ICP description) | ICP prompt only | Determine workflow → full pipeline |
| **Company list** | CSV with company names/domains | Skip company-search → company-enrichment |
| **Contacts CSV** | Names + companies, missing contact info | Skip to people-enrichment |
| **Signal data** | Companies found via signals | Skip to company-enrichment/scoring |
| **Demo webhook** | ICP prompt, ~10 contacts scope | Run demo skill |
| **SN search URL** | Sales Navigator saved search | Run company-search (SN+PB) → continue |

---

## Step 2 — Determine Workflow

### Company-First Workflow (Finite Markets)

**When:** Client provides a company list, known industry, or uses Sales Navigator. The market is bounded — you know (or can enumerate) the target companies.

**Full sequence:**
```
1. Company Search      → csv/input/companies_raw.csv
2. Company Enrichment  → csv/intermediate/companies_enriched.csv
3. ICP Scoring         → csv/intermediate/companies_scored.csv  (credit-saving gate: icp_score >= 70)
4. Signal Search       → csv/intermediate/signals.csv  (runs on gated set; doesn't read icp_score)
5. People Search       → csv/intermediate/contacts_found.csv
6. Contact Filter      → csv/intermediate/contacts_filtered.csv
7. People Enrichment   → csv/output/contacts_enriched.csv
```

The `icp_score >= 70` gate at step 3 is **for credit savings only** — signal-search itself doesn't depend on the ICP score. Skip the gate if you want to score signals on the full enriched set.

### Signal-First Workflow (Infinite Markets)

**When:** No company list — discover companies via buying intent signals. The market is unbounded — you find companies by their behavior.

**Full sequence:**
```
1. Signal-based Discovery  → companies found via signals (FindAll, Firecrawl Agent, LinkedIn Jobs)
                              writes csv/input/companies_raw.csv
2. Company Enrichment      → csv/intermediate/companies_enriched.csv
3. ICP Scoring             → csv/intermediate/companies_scored.csv  (optional gate)
4. People Search           → csv/intermediate/contacts_found.csv
5. Contact Filter          → csv/intermediate/contacts_filtered.csv
6. People Enrichment       → csv/output/contacts_enriched.csv
```

In Signal-First, signal-search runs on **raw company names from the discovery channels** (no enrichment needed yet). Company enrichment and ICP scoring happen after to filter the discovered set.

### Shortcut Flows

| Starting Point | Skills Invoked |
|----------------|---------------|
| Demo webhook (ICP prompt only) | **demo** skill (people-search → contact-filter → people-enrichment → messages, 10 contacts, no phone) |
| Company list provided | company-enrichment → (optional: signal-search) → people-search → contact-filter → people-enrichment |
| Contacts CSV provided | people-enrichment only |
| Persona prospecting (no companies) | people-search (persona mode) → contact-filter → people-enrichment |
| Full pipeline (Stripe payment) | Full Company-First or Signal-First workflow based on requirements |

---

## Step 3 — Clarify Requirements

Before executing, confirm with the user:

### ICP Definition
- Industry / vertical
- Target roles / job titles
- Company size (headcount range)
- Location / geography
- Revenue range (if relevant)
- Exclusions (e.g. no software companies, no enterprise)

### Scope & Budget
- How many contacts needed? (10 for demo, 100+, 500+?)
- Credit budget constraints?
- Enrichment scope: email only? email + phone?
- Message generation needed?

### Trigger Context
- Demo mode? (no phone, ~10 contacts)
- Stripe payment? (full pipeline, budget confirmed)
- Manual request? (flexible scope)

Save ICP to `{client-slug}-gtm/context/icp.md`.

---

## Step 4 — Plan the Sequence

Based on workflow + starting point, build the execution plan:

1. **List which skills run**, in what order
2. **Recommend providers** at each step (with costs from skill docs)
3. **Estimate total credits and cost** across all steps
4. **Identify per-client customizations** needed:
   - ICP Google Doc or `context/icp.md` (for ICP scoring in company-enrichment)
   - `context/offering.md` + `context/signal_criteria.md` (for signal-search; see Step 6, no n8n edits needed)
5. **Present plan for user approval** before executing anything

### Cost Estimation Template

```
## Pipeline Cost Estimate

### Step 1: Company Search
- Provider: [recommended]
- Records: ~{n}
- Est. cost: {credits} credits (~${cost})

### Step 2: Company Enrichment
- Provider: [recommended]
- Records: ~{n}
- Est. cost: {credits} credits (~${cost})

### Step 3: ICP Scoring
- Scoring: done by the agent (see Model Routing in conventions.md), no third-party LLM cost
- Records: ~{n}

### Step 4: Signal Search (companies with icp_score >= 70 if gating)
- Sources: [which of the 4 sources]
- Scoring: done by the agent (opus, see Model Routing in conventions.md)
- Records: ~{n} (est. {pct}% pass ICP gate, or full set if no gate)
- Est. cost: {credits} credits

### Step 5: People Search
- Provider: [recommended]
- Records: ~{n} contacts across ~{m} companies
- Est. cost: {credits} credits (~${cost})

### Step 6: Contact Filter
- No API cost — local classification only
- Records: ~{n} contacts in → ~{n_filtered} contacts out (est. {pct}% pass ICP filter)
- ICP dimensions: job tier, industry tier, location tier, company size

### Step 7: People Enrichment
- Email provider: [recommended]
- Phone provider: [recommended or "skip — demo mode"]
- Records: ~{n}
- Est. cost: {credits} credits (~${cost})

### Total
- Credits: ~{total_credits}
- Cost: ~${total_cost}
```

---

## Step 5 — Execute and Chain

Invoke skills in order. After each step:

1. **Review output quality** — hit rates, data completeness, issues
2. **Log to run_log.md** — timestamp, provider, records, credits, duration
3. **Log provider performance** — to `context/provider_performance.md`
4. **Chain output → input** — each skill's output CSV becomes the next skill's input
5. **Decide whether to proceed** — if quality is poor, flag and discuss before continuing

### Chaining Rules

| Skill Output | Next Skill Input |
|-------------|-----------------|
| `csv/input/companies_raw.csv` | company-enrichment reads this |
| `csv/intermediate/companies_enriched.csv` | ICP scoring reads this |
| `csv/intermediate/companies_scored.csv` | signal-search reads this (optional credit-saving gate: `icp_score >= 70`) |
| `csv/intermediate/signals.csv` | Used for outreach context, not a direct input |
| `csv/intermediate/contacts_found.csv` | contact-filter reads this |
| `csv/intermediate/contacts_filtered.csv` | people-enrichment reads this |
| `csv/output/contacts_enriched.csv` | Final output — ready for outreach or message generation |

### After Each Step

Print the standardized Run Summary (from conventions.md) and ask:
- Results look good? Proceed to next step?
- Any issues to address first?
- Want to adjust providers or parameters?

---

## Step 6 — Customize Per Client

### ICP Scoring (company-enrichment Phase 2)
- Create/connect a Google Doc with the client's ICP definition
- Or write to `context/icp.md` and use that as the reference
- Adjust score threshold (default: >= 70) based on selectivity

### Signal Assessment (signal-search — script-based)

Signal-search runs `~/.claude/skills/gtm-signal-search/signal_search.py`. Universal templates (extraction prompts, scoring rubric, request shapes) are baked into the script. Client-specific prompts come from three context files:

- `context/icp.md` — ICP definition (typically written by `gtm-setup`)
- `context/offering.md` — what we sell, value props (used in the scoring prompt). If absent, the script falls back to `context/profile.md`.
- `context/signal_criteria.md` — what counts as a signal for this offering: an **include** list + a short **"not a signal"** exclude list (used in the web-search objective + both extraction prompts)

Before invoking signal-search:
1. Confirm all three files exist; collect any missing pieces from the user. If `signal_criteria.md` is thin, **help the user construct it** (include + exclude + tuning params like max-age and result count) — see the signal-search skill's Step 2 for the interview.
2. Pick which optional sources to enable (`--firecrawl` or `--firecrawl-pages-dir`, `--parallel-enrichment`) based on whether on-site content / structured fields matter for this client. Use `--firecrawl-pages-dir` (Firecrawl-via-MCP) when there is no `FIRECRAWL_API_KEY` in the env.

No n8n workflow edits are required for signal-search anymore — the script reads everything from `context/` at runtime. Keys are injected via `_shared/resolve_env.sh` (resolves `$GTM_ENV_PATH` on any machine).

---

## Working Directory

The pipeline creates and manages the full `{client-slug}-gtm/` directory structure. The authoritative tree and file paths are defined in `_shared/conventions.md` (Working Directory section); the key handoff files are listed in the Chaining Rules table above.

---

## Decision Logic Summary

```
IF demo mode:
  → Run demo skill directly

IF user has contacts CSV:
  → people-enrichment only

IF user has company list:
  → company-enrichment → (optional: signal-search) → people-search → contact-filter → people-enrichment

IF user has nothing (just ICP):
  → Ask: Company-First or Signal-First?
  → Company-First: company-search → company-enrichment → signal-search → people-search → contact-filter → people-enrichment
  → Signal-First: signal-search (discovery) → company-enrichment → people-search → contact-filter → people-enrichment

IF paid trigger (e.g. Stripe webhook):
  → Full pipeline based on workflow determination above
```

---

## What's Missing (To Document)

- Payment trigger integration (e.g. Stripe webhook → pipeline invocation)
- Automated webhook integration for demo triggers
- Orchestration platform (e.g. n8n) integration for creating client-specific flow copies
- Pipeline recovery: resuming a partially completed pipeline from the last successful step
- Cost tracking dashboard / running totals across multiple pipeline runs
