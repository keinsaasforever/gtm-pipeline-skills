---
name: gtm-pipeline:demo
description: Generate a demo lead list of ~10 enriched contacts with personalized message examples. Use when a demo is requested, a webhook prompt describes a target audience, or someone asks to "create a demo for [client]". Enforces demo mode restrictions (email only, no phone, ~10 contacts). Chains people-search → contact-filter → people-enrichment → (optional signal-search) → message generation. Pass `--with-signals` (or ask the user) to enable a buying-intent scoring pass before message generation — pricier but produces sharper, signal-anchored messages.
---

# Demo

Generate a demo lead list of ~10 enriched contacts with personalized message examples, triggered by a webhook prompt.

**Read `~/.claude/skills/gtm-pipeline/_shared/conventions.md` before executing.**

---

## When to Use

- Webhook trigger: user submits a free demo form describing their target audience
- Goal: prove the AI agent writes authentic, non-generic outreach using real leads
- Scope: ~10 contacts, enriched with LinkedIn + email, 2–4 message examples

## Demo Restrictions

- **No phone enrichment** — email only
- **~10 contacts** (request 10–15, expect enrichment drop-off)
- Message generation is optional but recommended
- **Signal search is opt-in** — off by default. Enable via `--with-signals` flag or explicit user request. See Step 5.5.

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

## Step 2 — Create Working Directory

Create the `{client-slug}-gtm/` directory structure as defined in `conventions.md`. Write the ICP definition to `context/icp.md`.

---

## Step 3 — People Search (10 contacts)

Use the **people-search** skill to find ~10–15 contacts.

**Provider selection for demo:** follow the finder cadence in `conventions.md` → People-Source
Cadence — **FullEnrich Finder → BetterContact → Pipe0 → Amplemarket/Crustdata (last resort)**,
max 2 attempts/source, FE-first for SME/owner-led/non-English segments. Both FE and BC return
LinkedIn URLs directly (needed for email enrichment). If no company list (persona-based prompt),
use **Parallel FindAll** or **BC Search**. For directory/scrape-sourced company lists, search by
company **name** + location, never by exact domain (conventions #11).

**Key fields to collect:**
```
full_name, first_name, last_name,
job_title, company_name, company_domain,
linkedin_profile_url, location
```

Follow the people-search execution protocol: sandbox → test → review → run.

---

## Step 4 — Contact Filter (ICP Ranking)

Run **contact-filter** on the 10–15 contacts found. Even small batches benefit from ICP ranking — it ensures the enrichment step focuses on the best-fit contacts.

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

---

## Step 5.5 — Signal Search (Optional)

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

The message-generation step in Step 6 will then have `company_overall_summary` and `company_scored_signals` per contact — use the highest-scored signal as the message hook.

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
     box, no source link). Use `.approach` blocks to frame each group; `.seg-meta` for counts.
   - Each card = collapsible `<details class="lead">`: favicon, company + domain, attribute tags
     (`tag-sig`/`tag-icp` + language `tag-lang`), the signal/fit box, the decision-maker with
     LinkedIn + email and a deliverability badge (`est-ok` = verified email, `est-warn`
     "on request" when no email — in that case **drop the email draft, keep only the LinkedIn
     draft**), and the message draft (email subject + body, then LinkedIn) with an A/B `cta-chip`.
   - **List bar** carries a **Download-CSV button** (`.dl`) beside the Expand-all toggle; the
     footer carries a **big CTA button** (`.cta-btn`) linking to the client's booking URL
     (`{{CALENDAR_URL}}` — ask for it, or leave the token if unknown). These two elements are the
     grafted-in pieces; the rest is the nextbike combined-deck look.
   - **`{{CSV_DATA}}`**: embed the sanitized `csv/output/` rows as an escaped JS string (`\r\n`
     line endings; quote any field containing a comma) so the Download button emits a real CSV
     offline — no server. Set `{{CSV_FILENAME}}` to `{client-slug}_prospects.csv`.
   - Language DE or EN (`{{LANG}}` + swap the `{{LBL_*}}` button labels). In German: no em-dashes,
     start sentences with a pronoun. Keep it self-contained (one `<style>`, inline `<script>`).
3. **Google Sheet** (optional): formatted for review.

**Step 7c — Programmatic self-QA** (browser QA is often unavailable — never depend on a screenshot):
assert card count == contact count; **zero unfilled `{{TOKEN}}` placeholders remain** in the HTML;
every signal card has a live source link + date; **zero empty fields / placeholders**; zero
em-dashes; one email + one LinkedIn draft per verified-email card (LinkedIn-only for `est-warn`
cards) within char caps. Also assert the deck's plumbing survived templating: the **Download-CSV
button** (`id="dl"`) with a non-empty `CSV` string, the **footer CTA** (`.cta-btn`), and the
Expand-all toggle (`id="toggle"`) are all present, and the embedded CSV row count == card count.

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

**Webhook (demo form):** Free demo trigger — user describes their ICP in a text prompt. Run this skill with ~10 contacts and 2–4 message samples. See Deployment.

**Stripe payment (full list):** After successful payment, run the full pipeline via the `pipeline` skill. See pipeline skill for orchestration.

---

## Deployment (headless webhook)

When a website form submits a prompt (ICP/signals), the demo runs **headless** via the Claude
Code CLI. The skill is orchestrator-agnostic; a thin runner is provided at
`~/.claude/skills/gtm-pipeline/_shared/deploy/run_demo.sh` (see `_shared/deploy/README.md` for the full contract).

**Invocation:**
```bash
claude -p "/gtm-pipeline:demo $PROMPT" --model sonnet --permission-mode acceptEdits \
  --append-system-prompt "Headless demo run: never ask questions; infer per Step 1, record
  assumptions in context/icp.md, run end-to-end, sanitize, and emit result.json."
```

**Input contract:** free-text prompt describing the offering + target audience; the requester's
email (domain auto-resolved per Step 1). Optional JSON: `{ "prompt", "requester_email",
"with_signals": bool, "max_contacts": 10 }`.

**Output contract:** the run writes `{client-slug}-gtm/result.json`:
```json
{ "status": "ok", "client_slug": "...", "contacts": 10, "with_signals": true,
  "deck_path": "csv/output/… .html", "csv_path": "csv/output/contacts_enriched.csv",
  "assumptions": ["…"], "sanitize_report": { "...": 0 } }
```

**Headless rules:** never block on questions (Step 1); model routing per `conventions.md`
(Sonnet orchestration/filtering/deck, Opus extraction/scoring/messages — signal-search runs
`--llm-backend agent`, so the headless agent scores in-context, **no nested `claude -p`**);
always run Step 7a sanitization; delivery stays gated (produce the deck/email, do not send).

---

## What's Missing (To Document)

- LinkedIn post scraping via PhantomBuster API (launch, poll, download)
- Stripe payment trigger integration (paid full-pipeline path)
- Queue/concurrency layer in front of the webhook runner (the runner itself is provided under `deploy/`)
