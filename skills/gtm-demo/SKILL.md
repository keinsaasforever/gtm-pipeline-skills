---
name: gtm-pipeline:demo
description: Generate a demo lead list of enriched contacts (10 per segment, 2 segments, 30 max) with personalized message examples. Use when a demo is requested interactively, someone asks to "create a demo for [client]", or a webhook prompt describes a target audience (for an unattended webhook run use gtm-demo-headless instead). Enforces demo mode restrictions (email only, no phone, 70-credit cap). Chains people-search → contact-filter → people-enrichment → (optional signal-search) → message generation. Pass `--with-signals` (or ask the user) to enable a buying-intent scoring pass before message generation — pricier but produces sharper, signal-anchored messages.
---

# Demo

Generate a demo lead list of enriched contacts with personalized message examples: **10 per segment,
2 segments, 30 hard maximum, 70 credits hard**.

This is the **interactive** variant: it may ask the user a clarifying question when a must-have is
genuinely ambiguous, and the operator can override any default. For an **unattended webhook run use
`gtm-demo-headless`**, which is the same pipeline with every decision pre-made and zero questions.

**Read `~/.claude/skills/gtm-pipeline/_shared/conventions.md` before executing.**

---

## When to Use

- Webhook trigger: user submits a free demo form describing their target audience
- Goal: prove the AI agent writes authentic, non-generic outreach using real leads
- Scope: 10 contacts per segment, enriched with LinkedIn + email, one message pair each

## Demo Restrictions

- **No phone enrichment** — email only
- **Size: 10 contacts per segment, 2 segments by default** (split evenly), 3 when the prompt names
  three customer groups (Step 1b), otherwise a third segment only if the first two came back short
  and coverage is there. **30 contacts is the hard maximum**, and
  **one contact per company** — a second contact at the same company only to fill a gap at the end.
  A bigger number the requester asks for does not raise the cap; it raises what you say in the
  hand-off ("this is a sample of a list we can extend").
- Message generation is optional but recommended
- **Signal search is opt-in** — off by default. Enable via `--with-signals` flag or explicit user request. See Step 5.5.
- **Budget: 70 credits + $3 of web research per run, hard.** This covers everything: finder rows,
  email enrichment, signal/web calls. Track the spend in `run_log.md` as you go (each provider
  returns its own credit count — read it, don't estimate). **On reaching the cap the run stops
  buying, ships what it already has, and logs the shortfall.** It never asks for more, and it never
  buys "a few more rows to rank from".
- **Cost gate:** before the first paid provider call, state the expected spend (finders bill per person returned — BetterContact 0.10, FullEnrich 0.25 — so ~15 people is 1.50 to 3.75 cr; ~10-15 email enrichment credits; signals <$0.50 if enabled; a screening pass multiplies the search by 1 ÷ pass rate, since discarded contacts are billed too). Interactive: confirm with the user first. Headless: log the estimate in `run_log.md` and proceed, never block.
- **Pull enough, not best.** Buy `target ÷ expected pass rate` rows (≈1.5× with resolved filters),
  then stop. Ranking a large pool down to a small list means paying for every discarded row: the
  Reduzer run bought 311 rows to deliver 30. If the first pull is off-segment, fix the *filters*
  and re-pull small; never widen the pull to compensate.

---

## Step 1 — Parse the Prompt & Establish the ICP

The webhook prompt describes the user's target audience. Extract:

**Must have:**
- What do you sell / offer?
- Who is your ideal customer? (industry, role, company size, location)
- What's your value proposition?
- What tone? (formal vs. casual, examples if possible)
- Is this for recruiting OR selling to customers?

**If not in the prompt, infer (do not stall):**
- Target job titles, location, company size/type

**Auto-resolve the requester before interpreting the audience** (fixes the recurring "what do
they even sell / why do they want this audience" gap):
1. **Resolve the requester's own domain** from their email (e.g. `name@acme.de` → `acme.de`),
   scrape/enrich it, and establish what *they* sell. Multi-offering companies: confirm **which
   product line** the demo is for — the prompt's stated product can mismatch the real one.
2. **Determine the relationship to the target audience** — a target term (e.g. "call centers")
   is usually a segment they *sell to*, not what they are. Classify: sell-to / buy-from /
   acquire / partner / recruit. Persona keywords derive from this, not from a guess.
3. **List who they already work with, and keep them out of the demo.** A demo that pitches the
   client's own customers back to them is worse than a short one. Sources, all free: customer and
   reference pages, case studies, logos and quotes, and a partner/dealer/installer finder (often a
   public JSON feed behind the map). Save the list to `csv/input/client_existing.csv` and exclude by
   **domain**, never by name: a name match flagged Weber u. Sohn, Schatten and Bühring for Weber HS,
   Schatte and Bühr (perma-trade, 2026-09-18). A parent or sister company of a customer counts as
   the customer.
4. **Companies the prompt names as examples of its customers** ("Kunden wie Goldbeck, Züblin") are
   treated as existing customers: exclude them and their group, show lookalikes, and record the
   assumption. They are the best description of the segment, not leads.

**Interactive vs deployed (headless):**
- **Interactive:** if a must-have is genuinely ambiguous after auto-resolution, ask one concise
  clarifying question. Otherwise proceed.
- **Deployed / headless** (invoked via `claude -p` from the webhook — see Deployment): **never
  block on questions.** Infer every field from the prompt + requester-domain research, record
  assumptions in `context/icp.md` under an "Assumptions" heading, and proceed end-to-end.

Do NOT proceed to search until the ICP is clear enough to build a meaningful filter.

**Save ICP to:** `{client-slug}-gtm/context/icp.md` (include the offering, the relationship
classification, and any headless assumptions).

---

## Step 1b — Derive the Personas (before any paid call)

**A prompt almost never names job titles.** "We sell LCA software to the construction industry in
Norway and Sweden" says nothing about who signs. Deriving that is this step's job, not the search's:
without it the search falls back to broad title guesses and buys a market-wide pool.

Work it out from the client's own site (the pages scraped in Step 1 — customer/solution pages,
case studies and quotes are the best source; a customer quote names the buyer's exact title) plus
the offering:

1. **Segments** — **when the prompt names its customer groups, those are the segments**, 10
   contacts each, up to 3 within the 30 cap (perma-trade named SHK firms, general contractors and FM
   firms: three segments). Only when the prompt names none: which buyer types the client sells to,
   in *their* words (reduzer.com: contractor, architect, developer, consultant), ranked by how
   prominently the site sells to each, **top 2** (Demo Restrictions). Record why the others were dropped.
2. **Tier 1 titles per segment** — the role that owns the problem day to day and would answer the
   message. Reference-check it: Reduzer's own quotes are from an "Environmental manager" at a
   contractor and a "Sustainability Manager" at a developer, which *is* the tier-1 list.
3. **Tier 2 titles** — the adjacent roles that own it when tier 1 does not exist (tender/estimating,
   design/BIM, technical, project development), plus leadership at small companies.
4. **Write them in the market's language, in the forms a title index actually stores.** Nordic and
   German titles are compounds: `miljøleder`, `bærekraftssjef`, `hållbarhetschef`, `KMA-chef`,
   `Nachhaltigkeitsmanager`. A token (`miljø`) does not match a compound in most indexes, so list
   the full compound forms, and add the English equivalents international staff use.
5. **Exclude tokens** — the look-alikes that waste rows: `student`, `praktikant`, `lærling`,
   `assistent`, `trainee`, plus offering-specific ones (for building carbon: comms-only
   sustainability roles, `ytre miljø` / soil-contamination roles, `social hållbarhet`).

Write all of it to `context/icp.md` under `## Personas` (segments, tier 1, tier 2, excludes, and one
line of evidence per tier-1 list). **No paid call before this block exists** — it is what makes the
Step 3 filters narrow, and it is the difference between the emmy run (one query per company, 16
candidates for 12 leads) and a market-wide pull.

---

## Step 2 — Create Working Directory

Create the `{client-slug}-gtm/` directory structure as defined in `conventions.md`. Write the ICP definition to `context/icp.md`.

---

## Step 3 — People Search (10 per segment)

Use the **people-search** skill. Target = 10 per segment × the segments picked in Step 1b.

**Provider selection:** the general cadence is `conventions.md` → People-Source Cadence —
**FullEnrich Finder → BetterContact → Pipe0 → Amplemarket/Crustdata (last resort)**, max 2 attempts
per source, FE-first for SME / owner-led / non-English segments. **A demo inverts the first two:
BetterContact leads here** (0.10/lead against FE's 0.25/person, and `limit_per_company: 1` is what
spreads one fixed pull across distinct accounts, which a one-contact-per-company demo needs), with
FullEnrich second for what BC's index misses and for the filters only it has. Outside a demo, or
once several contacts per company are wanted, the general cadence applies unchanged. Both FE and BC
return LinkedIn URLs directly (needed for email enrichment). If no company list and a persona search
cannot bound the market, use the research route (3c) rather than **Parallel FindAll** / **BC
Search**. For directory/scrape-sourced company lists, search by company **name** + location, never
by exact domain (conventions #11).

### 3a — Resolve the filters against each finder's own value list (free, do it first)

The personas from Step 1b are filter *inputs*; every finder validates them against its own
vocabulary, and **an off-list value silently matches nothing** — a 0-lead result then reads as "this
market is empty" when it means "that word is not in the list".

| What | BetterContact | FullEnrich | Pipe0 |
|---|---|---|---|
| Industry | 120 Landbase values, **case-sensitive**, `company_industry` | LinkedIn industries, `_shared/fe_industries.txt` (490, case-insensitive) | catalog `industries.json` (435/501) |
| Region | country / "City, Country" | country / region string | `regions.json`, resolved or dropped |
| Headcount | `company_headcount_min/_max` integers | `current_company_headcounts` {min,max} | bracket enums |
| Titles | `lead_job_title` (contains), `lead_seniority`, `lead_department` | `current_position_titles`, `seniority` | per-search keys |
| Per-company cap | **`limit_per_company`** | none (persona pulls cluster) | none |

Grep the lists, never type a value from memory (`grep -i "construction" _shared/fe_industries.txt`;
BetterContact's is at https://doc.bettercontact.rocks/api-reference/taxonomies). Write the resolved
values into `context/icp.md` next to the personas.

**If no industry value fits the request, or the resolved filters come back slim or off-segment
(<½ the target, or most rows in the wrong segment), stop filtering and switch to broad research**
(3c). Two probe queries decide this — don't spend a third.

### 3b — Default route: filtered people search

**BetterContact first** (0.10/lead, cheapest per row, and `limit_per_company: 1` is what spreads a
fixed pull across distinct accounts, which a one-contact-per-company demo needs), **FullEnrich
second** for what BC's index misses (SME / owner-led / non-English segments) and for filters only it
has (tenure, recent job change). Max 2 attempts each, then fall through. Both return LinkedIn URLs,
which Step 5 needs.

Pull `target ÷ expected pass rate` (≈1.5×), per segment, and stop at the target. Re-verify titles
and segment locally — every provider filter is advisory.

### 3c — Broad research route (when 3a says the filters don't fit)

This is the emmy/nextbike route, and it is cheap because the company list is free:
1. Enumerate a **finite company pool** from public sources: an industry ranking, a trade-association
   member list, a public register, a directory, a Wikipedia list, or a client-supplied CSV. Cap it
   at ~2× the target companies. Verify each domain.
2. Then one people search **per company** (`limit` 5–8, tier-1 titles, no person-location filter),
   and pick one contact per company.
   Precedent: emmy 18 named brands → 16 candidates → 12 delivered; nextbike 21 clinics from a public
   hospital list → 47 candidates → 18 delivered.

**Route before searching** (`conventions.md` → Search Routing). Write the requirement split to
`context/icp.md`. A demo wants one contact per company, so **people first is the cheaper route
whenever the universe is bounded by filters** — the companies come out of the people search for
free. When the filters cannot bound it, 3c bounds it instead.

- **Pick the finder by the filters the ICP needs** (funding, hiring, revenue, B2B/B2C →
  BetterContact; tenure or a recent job change → FullEnrich). A filter beats research.
- **Any requirement that needs judgement** (a signal, a website trait, revenue from filings) is
  screened **after** the people search, on the companies it returned: pull `target ÷ expected pass
  rate` contacts, screen, drop the ones whose company fails. **Screen before Step 5** so email
  credits are only spent on survivors.
- **Company search first only** when the demo is meant to show the account list itself, or the
  prompt already comes with a company list. (3c is a different trigger: there the filters cannot
  express the segment at all, so the pool is enumerated from free public sources.)
- **Signal search first only** when a signal is mandatory *and* is the only way in (no filter
  covers it). Then: signal discovery → companies → people at those companies. A signal used to
  *rank* or to *hook* companies we already picked runs after the search, in Step 5.5.

**Key fields to collect:**
```
full_name, first_name, last_name,
job_title, company_name, company_domain,
linkedin_profile_url, location
```

Follow the people-search execution protocol: sandbox → test → review → run.

---

## Step 4 — Contact Filter (ICP Ranking)

Run **contact-filter** on the contacts found. Even small batches benefit from ICP ranking — it ensures the enrichment step focuses on the best-fit contacts, and it is where the Step 1b exclude tokens are enforced (provider title filters are advisory).

- Applies job tier, industry tier, location tier, and company size classification
- Rejects hard non-ICP contacts
- Ranks passed contacts by priority
- Output: `csv/intermediate/contacts_filtered.csv`

For demos: use a relaxed hard-reject threshold (allow tiers 1–5 to pass), prioritize ranking over filtering.

---

## Step 5 — People Enrichment (Email Only)

Run **people-enrichment** on the filtered contacts. **Demo mode: email only, no phone.**

Recommended flow (email waterfall — same hierarchy as people-enrichment):
1. **PhantomBuster Email Finder** — all contacts, **if available**. PB's built-in email waterfall (BetterContact et al.); needs `PHANTOMBUSTER_API_KEY` + Google OAuth (the engine creates a fresh staging sheet per run automatically). See people-enrichment **Provider 0**. **If N/A (engine exits 3), skip it** and start at FullEnrich — a ~10-contact demo must never block on PB.
2. FullEnrich v2 (email) — contacts still missing an email after step 1
3. Pipe0 waterfall — for remaining misses only

Every kept email must pass the **domain-identity cross-check** (the engine drops wrong-company hits automatically). On a ~10-contact demo, PB is a single async batch (~3–6 min).

Additional enrichment for message personalization (if available):
- LinkedIn headline and summary (from LinkedIn scrape via PhantomBuster)
- Recent LinkedIn posts (2–3 per contact) — significantly improves message quality

**Minimum viable fields for message generation:**
```
name, job_title, company_name, linkedin_profile_url,
headline (optional), summary (optional), recent_posts (optional)
```

**Low yield:** if fewer than ~8 contacts survive filtering + enrichment, run one additional finder pass (next source in the People-Source Cadence) before proceeding to messages.

---

## Step 5.5 — Signal Search (Optional)

**If signals gate this run** (per Step 3 routing), run this step **before Step 5**, on the companies
the people search returned, and enrich only the contacts whose company keeps a signal. As a message
hook (the default when it's on), it stays here, after enrichment.

**Default: OFF.** Enable when:
- The user explicitly asks for signal-anchored messages
- The webhook prompt mentions buying triggers (funding, hiring, transformation, recent news)
- The client's offering depends on timing signals to make sense (e.g. "we help post-Series-A companies scale ops")
- A `--with-signals` flag is passed to the demo invocation

**Cost note:** adds ~$0.01–0.05 per unique company (web search + scoring). On a 10-contact demo, that's typically 5–10 unique companies, so <$0.50.

### Required inputs for signal-search

Signal-search needs three context files:
- `context/icp.md` — already collected in Step 1
- `context/offering.md` — the value-prop block from Step 1 (write it now if not already saved)
- `context/signal_criteria.md` — bulleted list of signal types relevant to the offering

If `signal_criteria.md` doesn't exist, ask the user: *"What would a company be doing right now that suggests they need what you offer?"* — capture 5–10 bullets and save.

### Run

```bash
# Build company list from unique companies in the enriched contacts
python3 -c "
import csv, sys
seen = set()
with open('csv/output/contacts_enriched.csv') as f, open('csv/input/companies_raw.csv', 'w', newline='') as out:
    reader = csv.DictReader(f)
    writer = csv.DictWriter(out, fieldnames=['company_name', 'company_domain', 'company_website'])
    writer.writeheader()
    for row in reader:
        c = row.get('company_name') or row.get('company') or ''
        if c and c not in seen:
            seen.add(c)
            writer.writerow({
                'company_name': c,
                'company_domain': row.get('company_domain') or '',
                'company_website': row.get('company_website') or row.get('website') or '',
            })
"

# Run signal-search on the unique companies
source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh" && \
export $(grep -E '^(PARALLEL_API_KEY|OPENROUTER_API_KEY|FIRECRAWL_API_KEY|GEMINI_API_KEY)=' "$GTM_ENV_PATH" | xargs) && \
  python3 ~/.claude/skills/gtm-signal-search/signal_search.py \
    --client-dir {client-slug}-gtm
```

The `resolve_env.sh` source line ensures `$GTM_ENV_PATH` is set even in a fresh shell (see signal-search SKILL.md / conventions). For the demo, leave Firecrawl and Parallel enrichment **OFF** — web search + scoring is enough for a ~10-contact lead list. Enable Firecrawl only if on-site content (careers, blog) is the primary signal source; if this machine has Firecrawl only via MCP (no `FIRECRAWL_API_KEY`), use the `--firecrawl-pages-dir` route documented in the signal-search skill.

### Merge signals back into contacts

```python
import csv, json
signals = {}
with open('csv/intermediate/signals.csv') as f:
    for row in csv.DictReader(f):
        signals[row['company_name']] = {
            'overall_score': row.get('overallScore', ''),
            'scored_signals': row.get('scoredSignals', ''),
            'overall_summary': row.get('overallSummary', ''),
        }

rows_out = []
with open('csv/output/contacts_enriched.csv') as f:
    for row in csv.DictReader(f):
        s = signals.get(row.get('company_name') or row.get('company') or '', {})
        row['company_overall_score'] = s.get('overall_score', '')
        row['company_scored_signals'] = s.get('scored_signals', '')
        row['company_overall_summary'] = s.get('overall_summary', '')
        rows_out.append(row)

with open('csv/output/contacts_enriched.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
    w.writeheader()
    w.writerows(rows_out)
```

The message-generation step in Step 6 will then have `company_overall_summary` and `company_scored_signals` per contact — use the highest-scored **kept** signal as the message hook (Step 6 → Hook sources).

---

## Step 6 — Generate Message Examples

Generate **2–4 sample messages** before committing to the full batch.

### Message Structure

Every message must follow: **Hook → Bridge → Offer → Soft CTA**

| Part | Purpose | Length |
|------|---------|--------|
| Hook | Reference something specific to this person (post, career move, company signal) | 1 sentence |
| Bridge | Connect their situation to your offer | 1 sentence |
| Offer | What you provide, clearly stated | 1 sentence |
| CTA | Soft ask — not "let's schedule a call" | 1 sentence |

**Total: 320–450 characters.** No blank line after greeting. Paragraphs separated by single line break.

### Quality Rules

**Must have:**
- Specific hook (post reference OR career insight OR scored buying signal — not generic)
- Clear value proposition
- Natural, conversational tone
- Soft CTA

**Must avoid:**
- Repeating profile info they already know ("You work as X at Y")
- Generic observations ("impressive background", "I noticed you're in [industry]")
- Corporate jargon or buzzwords
- Pushy CTAs ("Let's schedule a call this week")

**If Step 5.5 ran:** for each contact, prefer the highest-scored signal from `company_scored_signals` as the hook over generic LinkedIn-post references. A score >= 70 signal anchored in real recent news is the strongest hook the demo can produce.

**Hook sources — exactly two.** (1) A **kept signal**: dated inside the window, citing its article.
(2) A **timeless fit fact**: what the company does, where, for whom and at what size, from its own
site, plus the person's role. A dated event (a project, contract, acquisition, report, sale, post)
that is not a kept signal never goes into a hook, a "why they fit" text or any other field, however
it reached you. Cost of skipping it (perma-trade, 2026-09-18): the scorers wrote stale news into
free-text fit fields, the signal gate never saw it, and drafts at five companies plus one fit text
used events that had failed the gate (May to early July, and a post with no live link), which a
deck-side fix then had to strip out.

### Generation Process

1. Write a client-specific system prompt (save to `prompts/message_prompt.md`)
2. Generate 2–4 samples — include contacts with and without LinkedIn posts
3. Review against quality checklist above
4. If issues found, refine the system prompt and regenerate
5. **Only batch generate once quality is approved**

### System Prompt Template (key sections)

```
- Client context: what they sell, who they target, their value prop, tone
- Forbidden rules: no profile repetition, no generic flattery
- Message structure: hook → bridge → offer → CTA
- Hook examples: with posts / without posts
- Character limit: 320–450
```

---

## Step 7 — Sanitize & Output

**Step 7a — Sanitize (mandatory, deterministic, no LLM).** `csv/intermediate/` keeps every field.
Before building anything lead-facing, run the shared sanitizer so the recurring hand-scrubbing
(provider labels, empty columns, bad emails, stale signals) happens automatically:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/gtm-pipeline/_shared"))
from sanitize import sanitize_rows
clean, report = sanitize_rows(rows, email_policy="standard", max_signal_age_days=60)
# report → rows_dropped_bad_email, signals_dropped, columns_dropped, messages_trimmed
```

It drops bad-status emails (default keeps Deliverable/High-prob/Catch-all), strips provider/source
labels + internal status codes, removes all-empty columns, drops stale/sourceless signals, and
enforces message length + em-dash rules. See `conventions.md` → Output Sanitization. Write the
result to `csv/output/`.

**Step 7b — Deliverables** (build from the sanitized `csv/output/` only):
1. **CSV** at `csv/output/contacts_enriched.csv`: lead data + generated messages (post-sanitize).
2. **Card deck** (HTML): the parameterized keinsaas-style deck — one card per contact with
   signal (source + date), decision-maker, and ready message. **Start from the canonical
   template `deck_template.html`** (in this skill's directory) and fill every `{{TOKEN}}`; do
   not hand-copy a prior client's deck or restyle from scratch. Drive it from the sanitized CSV +
   `context/` files. Assemble with the **sonnet** model. Deck anatomy (all baked into the template):
   - **Header + hero + 4 stat tiles**, then segment blocks. Group contacts into **Signal-first**
     (fresh, sourced buying signal ≤ 60d → `sig-hot` red signal box with a live `.sigsrc` source
     link + date) and **ICP-first** (strong fit, no live signal → `sig-fit` blue "why they fit"
     box, no source link, built only from timeless fit facts: Step 6 → Hook sources). Use
     `.approach` blocks to frame each group; `.seg-meta` for counts.
   - Each card = collapsible `<details class="lead">`: favicon, company + domain, attribute tags
     (`tag-sig`/`tag-icp` + language `tag-lang`), the signal/fit box, the decision-maker with
     LinkedIn + email and a deliverability badge (`est-ok` = verified email, `est-warn`
     "on request" when no email — in that case **drop the email draft, keep only the LinkedIn
     draft**), and the message draft (email subject + body, then LinkedIn) with an A/B `cta-chip`.
   - **List bar** carries a **Download-CSV button** (`.dl`) beside the Expand-all toggle; the
     footer carries a **big CTA button** (`.cta-btn`) linking to **keinsaas's** booking page, always
     (the deck is a keinsaas pitch to the prospect, never the prospect's own demo link):
     `{{CALENDAR_URL}}` = https://calendar.google.com/calendar/appointments/schedules/AcZssZ3kHmy2kw6fePg6tqmkoaFnj8AKGN2Baq3rRyfo4ItozAv2BfXF3Gh2-oMjYDxWIc7P_hEfMZTi
     (the schedule embedded on keinsaas.com/sales-agent; re-check there if it 404s). These two elements are the
     grafted-in pieces; the rest is the standard combined-deck look.
   - **`{{CSV_DATA}}`**: embed the sanitized `csv/output/` rows as an escaped JS string (`\r\n`
     line endings; quote any field containing a comma) so the Download button emits a real CSV
     offline — no server. Set `{{CSV_FILENAME}}` to `{client-slug}_prospects.csv`.
   - **Hero = hook, not manual.** `{{HERO_HEADLINE}}` short (≤ ~7 words), outcome-first, no jargon;
     `{{HERO_INTRO}}` 1–2 short sentences on what they *get* (ready-to-send outreach to the right
     people), never how the pipeline works. Intrigue, don't overwhelm with technical detail.
   - **Never name a third-party tool or data provider** anywhere in the rendered deck (no enrichment
     vendor, search/scrape provider, or phone/email finder). A signal's source link cites the
     *original publication* (press release, careers page, news outlet), not the tool that found it.
     The lead's own LinkedIn link is fine. Sanitize (7a) already strips provider labels — this keeps
     hand-written hero/footer/method copy clean too.
   - Language DE or EN (`{{LANG}}` + swap the `{{LBL_*}}` button labels). **German uses Du-form**
     (informal *du/dein*, not *Sie*), no em-dashes, start sentences with a pronoun. Keep it
     self-contained (one `<style>`, inline `<script>`).
3. **Google Sheet** (optional): formatted for review.

**Step 7c — Programmatic self-QA** (browser QA is often unavailable — never depend on a screenshot):
assert card count == contact count; **zero unfilled `{{TOKEN}}` placeholders remain** in the HTML;
every signal card has a live source link + date; **zero empty fields / placeholders**; zero
em-dashes; one email + one LinkedIn draft per verified-email card (LinkedIn-only for `est-warn`
cards) within char caps. **No third-party tool / data-provider name** appears in the rendered text
(grep the visible copy for enrichment/search/scrape vendor names — none allowed; the lead's own
LinkedIn link is the only exception). **German decks use Du-form** — flag any `Sie/Ihr/Ihnen`
formal-address forms in the deck's own copy (the drafts follow the message prompt's register).
**ICP-fit cards carry no dates:** the fit box and both drafts of every card without a kept signal
contain no full date (`2026-07-07`, `07.07.2026`, `7. Juli 2026`, `July 7, 2026`) and no month
followed by a year; a hit means a stale event slipped in, so rewrite that sentence from timeless
fit facts. **Hero is tight** — `{{HERO_HEADLINE}}` ≤ ~7 words and `{{HERO_INTRO}}` ≤ 2
sentences with no pipeline/sourcing detail. Also assert the deck's plumbing survived templating: the
**Download-CSV button** (`id="dl"`) with a non-empty `CSV` string, the **footer CTA** (`.cta-btn`),
and the Expand-all toggle (`id="toggle"`) are all present, and the embedded CSV row count == card
count.

### Output CSV Columns (post-sanitize; empty/internal columns auto-dropped)

```
name, first_name, last_name, location, headline, summary,
linkedin_url, email, company_name, job_title,
post_1_content, post_1_date, post_2_content, post_2_date,
generated_message, char_count, has_posts
```

Messages saved separately to `csv/output/messages.csv`. **Delivery is gated** — write the cover
email to a file; never send on the user's behalf without explicit go-ahead (`conventions.md` #12).

---

## Quality Checklist (Before Delivering)

- [ ] Messages feel personal, not templated
- [ ] No profile info repetition
- [ ] Clear value proposition in every message
- [ ] Proper formatting (line breaks, character count 320–450)
- [ ] Hook differs between contacts (no copy-paste structure)
- [ ] All data fields populated correctly
- [ ] Client-specific context incorporated

---

## Trigger Context

**Webhook (demo form):** Free demo trigger — user describes their ICP in a text prompt. An unattended webhook runs **gtm-demo-headless** (same steps, zero questions, fixed defaults). See Deployment.

**Stripe payment (full list):** After successful payment, run the full pipeline via the `pipeline` skill. See pipeline skill for orchestration.

---

## Deployment (headless webhook)

When a website form submits a prompt, the run is unattended and belongs to **`gtm-demo-headless`**
(`~/.claude/skills/gtm-demo-headless/SKILL.md`): same steps as this skill, every decision pre-made,
zero questions, `result.json` as the output contract. A thin runner is provided at
`~/.claude/skills/gtm-pipeline/_shared/deploy/run_demo.sh` (see `_shared/deploy/README.md`).

```bash
claude -p "/gtm-pipeline:demo-headless $PROMPT" --model sonnet --permission-mode acceptEdits
```

Use **this** skill when a person is present to answer: it may ask one clarifying question, and the
operator can override the defaults. Use the headless skill for webhooks, cron and any `claude -p`
run with nobody watching. Keep step logic in this file; the headless skill only overrides decision
points, so fixes here reach both.

---

## What's Missing (To Document)

- LinkedIn post scraping via PhantomBuster API (launch, poll, download)
- Stripe payment trigger integration (paid full-pipeline path)
- Queue/concurrency layer in front of the webhook runner (the runner itself is provided under `deploy/`)
