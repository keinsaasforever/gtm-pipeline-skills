---
name: gtm-pipeline:people-enrichment
description: Enrich contacts with work email, phone number, and/or LinkedIn URL. Use when you have a contact list that needs enrichment before outreach. Email waterfall (FullEnrich → Pipe0), phone (BetterContact → FullEnrich). Enforces demo mode (email only, no phone). Also triggers on "enrich contacts", "find emails for", "get phone numbers for".
---

# People Enrichment

Enrich contacts with work email, phone number, and/or LinkedIn URL. Returns an updated CSV.

**Read `~/.claude/skills/gtm-pipeline/_shared/conventions.md` before executing.**

---

## When to Use

- You have a contact list and need emails and/or phone numbers
- Contacts from people-search need enrichment before outreach
- A user-provided CSV has names + companies but missing contact info

## Inputs

| Input | Required | Source |
|-------|----------|--------|
| Contact CSV | Yes | People Search output or user-provided |
| LinkedIn profile URLs | Recommended | In CSV or from People Search |
| Company domains | Recommended | In CSV |
| Enrichment type | Yes | `email`, `phone`, or `both` |

## Demo Mode

When invoked from the demo flow: **email only, skip all phone providers entirely.**

**Cloudflare:** BC and FE (like Pipe0) are Cloudflare-fronted — call them with `curl` + a browser `User-Agent` (conventions rule #8); never Python `requests`/`urllib`.

---

## Provider Selection

### Email

**Ask the user which provider to use. Default recommendation:**

| Priority | Provider | Hit Rate | Cost | Speed | Notes |
|----------|----------|----------|------|-------|-------|
| **1st** | **PhantomBuster Email Finder** | account-dependent | ~1 cr/email found | ~3–6 min/batch (async container) | **Run first if available.** PB's built-in email waterfall (BetterContact et al.). Needs a Google Sheet to stage input + `PHANTOMBUSTER_API_KEY`. **If N/A, skip — fall through to FullEnrich.** See Provider 0. |
| 2nd | **FullEnrich v2** | 80% (SA), 83% (DACH) | 0.8 cr/contact | instant | Strong direct-API fallback; email-first among the JSON providers |
| 3rd | **Pipe0 waterfall** | 60% (SA), 83% (DACH) | 1.0–3.5 cr/contact | ~3 min/20 contacts | Solid backup |
| 4th | **BetterContact** (email-only) | ~60% test / **14% production SA** | 0.35 cr/contact | 30–90 min | Not recommended — slow, unreliable production |

**Recommended flow (email waterfall):** **PB Email Finder (Provider 0, if available) → FE Enrich (v2) → BC → Pipe0 pipes → Amplemarket/Crustdata (last resort).** PB runs first because it wraps a multi-provider waterfall in one call; when PB is **N/A** (no `PHANTOMBUSTER_API_KEY`, no staging sheet, or no Google OAuth — the engine exits 3) simply **skip it** and start at FE. FE is **email-first** among the direct-API providers because BC async email hit rate is low (~14% production SA). **Max 2 attempts per source**, then fall through. Mirrors conventions **People-Source Cadence**. Every provider's output — PB included — must pass the **Domain-Identity Cross-Check** below before it ships.

### Domain-Identity Cross-Check (critical)

Deliverability status is **blind to identity.** Providers return `DELIVERABLE` emails on the **wrong company's domain** (a genuine wrong-company hit — the exact "made-up address" failure clients fear). Provider status alone is **not** enough.

**MANDATORY** before an enriched email is kept:
- The email's domain must **belong to the target company** — match by **domain-root** against the target's known domain / company name.
- If the domain is unfamiliar, **verify what it actually is** (e.g. scrape its title) before trusting it.
- **Drop identity mismatches** even when status is `DELIVERABLE`.

This is the real anti-"made-up-address" guard; the `sanitize.py` deliverability filter (below) is only the last net.

### Phone

**Skip entirely in demo mode.**

| Priority | Provider | Hit Rate | Cost | Speed | Notes |
|----------|----------|----------|------|-------|-------|
| 1st | **FullEnrich v2** | ~60% DACH | ~0.8 cr/contact | instant | Good DACH coverage. Prefer `most_probable_phone.number` over `phones[0]` (phones[0] can be landline, most_probable is mobile) |
| 2nd | **Pipe0 phone waterfall** | **~92% DACH (n=74)** · 0% SA | 2–7 cr/contact | ~30s/batch | Response field: `mobile` (not `phone`). Works reliably as FE fallback — on 7 FE contacts missing phones, recovered 5 (71%). Also strong as primary when contacts come from Pipe0 search (68/74 = 92%) |
| 3rd | **BetterContact** | 13–74% (~22% SA, ~53% DACH) | ~1–2 cr/contact | **5–10+ min** for small batches | Unreliable speed — took 10+ min for 2 contacts in DACH test. Retest before production |

### LinkedIn URL (when missing)

- **Pipe0 `people:profileurl:name@1`** — 0.60 cr/person, needs name + company_name + location_hint
- **PhantomBuster Profile Scraper** (config key: `PB_AGENT_PROFILE`) — scrape full profile data from existing LinkedIn URL; use `/phantombuster` skill with phantom name "LinkedIn Profile Scraper" and CSV path. See `_shared/phantombuster.md`.

---

## Execution Protocol

### 1. Assess Input Data
- Check what fields are available (LinkedIn URL, domain, name, company)
- Determine which enrichment types are needed
- Estimate credit cost: `n_contacts × max_cost_per_record`
- Confirm credit balance with user before proceeding

### 2. Test Batch (5–10 contacts)
- Run chosen provider on 5–10 contacts in production
- Inspect every result: email validity status, phone format, match accuracy
- Check hit rate — if below 10%, investigate before proceeding

### 3. Review with User
- Present test results with hit rate, status breakdown, sample data
- Confirm provider choice and credit spend for full batch
- Get approval

### 4. Full Batch
- Split into chunks of **max 100 contacts** per request (all providers)
- **Save request/task IDs immediately**
- Poll with appropriate timeouts:
  - FE: 15s interval, 600s timeout (usually instant)
  - Pipe0: 30s interval, 600s timeout (≤100 contacts)
  - BC phone: 30s interval, 900s timeout
  - BC email: 60s interval, 3600s timeout
- Save results incrementally after each batch

### 5. Fallback Pass
- Identify contacts with missing email/phone after primary provider
- Run fallback provider on misses only
- Merge results

### 6. Final Output
- Merge all provider results into `csv/intermediate/contacts_enriched.csv` — **keep every field** (`email_source`/`phone_source`, `email_status`, provider labels), per conventions rule #6
- Confirm each email passed the **domain-identity cross-check** above before it can ship
- **Sanitize before the lead-facing view** — run the shared sanitizer (do **not** reimplement); it drops bad emails, strips provider/source labels + internal status codes, and drops empty columns. See conventions **Output Sanitization**:
```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/gtm-pipeline/_shared"))
from sanitize import sanitize_rows
clean, report = sanitize_rows(rows, email_policy="standard")  # "strict" also drops catch-all
```
- **Deliverability policy** is applied by `sanitize.py` via `email_policy`: default `standard` keeps DELIVERABLE + HIGH_PROBABILITY + CATCH_ALL and drops UNKNOWN/RISKY/invalid; `strict` additionally drops catch-all
- Write the sanitized rows to `csv/output/contacts_enriched.csv`

---

## Provider 0: PhantomBuster Email Finder (Email — Priority 1)

The **first** email provider in the waterfall when it's available. Uses the PhantomBuster "Email Finder" phantom (`emailChooser: "phantombuster"`), which resolves a professional email from **first name + last name + company domain** via PB's own multi-provider email waterfall (BetterContact et al.). It is a **data** phantom — **no LinkedIn session cookie needed** (unlike Connect/Message agents).

**Key difference from the other providers:** input is read from a **Google Sheet**, not a JSON POST body. The engine **creates a fresh blank sheet for each run** (so rows from different projects/runs never mix), link-shares it read-only so PhantomBuster can read it, stages the contacts, runs the phantom, then **trashes the sheet** (recoverable) on success. You don't manage any sheet yourself.

### Prerequisites (all three, else it's N/A → skip)
- `PHANTOMBUSTER_API_KEY` in the env
- Google OAuth available to `gspread` — `GOOGLE_CLIENT_SECRET_FILE` (+ optional `GOOGLE_AUTHORIZED_USER_FILE`). The engine creates/shares/trashes its own sheet, so **no pre-existing sheet ID is needed.**
- Agent ID resolved via `PB_AGENT_EMAIL` (env / `_shared/local.md`), or by phantom name "Email Finder" through the PB API/MCP. See `_shared/phantombuster.md`.

**If any prerequisite is missing the engine exits `3` — a clean "not available" signal. Treat exit 3 as "skip PB, start the waterfall at FullEnrich."** Do not treat it as an error.

### Run
```bash
source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh" && \
export $(grep -E '^(PHANTOMBUSTER_API_KEY|GOOGLE_CLIENT_SECRET_FILE|GOOGLE_AUTHORIZED_USER_FILE|PB_AGENT_EMAIL)=' "$GTM_ENV_PATH" | xargs) && \
python3 ~/.claude/skills/gtm-pipeline/_shared/pb_email_finder.py \
  --input  csv/intermediate/contacts_filtered.csv \
  --output csv/intermediate/contacts_pb_email.csv \
  --client-slug {client-slug}     # names the fresh staging sheet for identifiability
rc=$?   # rc==3 → PB N/A, skip to FullEnrich on the SAME input CSV
```

Then run the FullEnrich pass (Provider 1) on the rows that still have **no email** — the engine leaves those blank and preserves every original column, so `contacts_pb_email.csv` becomes the input to FE.

### Behaviour
- **Fresh sheet per run.** A new blank spreadsheet `gtm-pb-email-staging {slug} {date}` is created, link-shared read-only (so PB can read it), used, then trashed on success (kept on failure or with `--keep-staging`; `--no-share` if your PB reads Drive via a Google connection instead).
- Column names default to the GTM people schema (`first_name`, `last_name`, `company_name`, `company_domain`, `email`, `email_status`, `email_source`) — all overridable via flags.
- Only rows with **first + last + domain** are sent to PB; the rest fall through untouched.
- Batches of 50. Per batch: stage → launch → wait 180s → poll (10s, 600s cap) → fetch `resultObject` (console-log regex fallback).
- **Domain-identity cross-check is applied automatically.** An email whose domain doesn't belong to the target company is **dropped** (left blank → falls through to FE), honouring the MANDATORY cross-check below. Use `--keep-mismatch` only if you deliberately want to keep them.
- Sets `email_source = "phantombuster"` and `email_status` = `match` / `subdomain` on kept emails. `~1 credit per email found`.

### Notes
- Agent ID is account-specific; the engine's built-in default is the keinsaas account's — **resolve your own** via `PB_AGENT_EMAIL`.
- Because PB is async (~3–6 min/batch), on a large batch it is slower wall-clock than FE but wraps several providers in one call. For a ~10-contact demo it's one batch.
- The fresh staging sheet briefly holds lead names + domains on an "anyone-with-link: reader" link while PB reads it; it's trashed right after. If that transient exposure isn't acceptable, connect your Google account inside PhantomBuster and pass `--no-share`.
- Legacy: pass `--staging-spreadsheet-id <id>` to reuse one sheet's `pb_email_staging` tab instead of creating fresh (not recommended — risks cross-project row mixing).

---

## Provider 1: FullEnrich v2 (Email + Phone)

**Endpoint:** `POST https://app.fullenrich.com/api/v2/contact/enrich/bulk`
**Auth:** `Authorization: Bearer $FULLENRICH_API_KEY`

### Submit (max 100 contacts/batch)
```json
{
  "name": "My enrichment job",
  "data": [
    {
      "firstname": "Jane",
      "lastname": "Doe",
      "domain": "example.com",
      "linkedin_url": "https://www.linkedin.com/in/janedoe",
      "enrich_fields": ["contact.emails"],
      "custom": {"row_id": "0"}
    }
  ]
}
```

For phone: `"enrich_fields": ["contact.phones"]` or both: `["contact.emails", "contact.phones"]`

### Poll
```
GET https://app.fullenrich.com/api/v2/contact/enrich/bulk/{enrichment_id}
```
Done when: `response["status"] == "FINISHED"`
Speed: **usually instant** — often finished before first poll. Use 15s interval, 600s timeout.

### Parse
```python
for entry in result.get("data", []):
    row_id = str(entry.get("custom", {}).get("row_id", ""))
    ci = entry.get("contact_info", {})
    # Email
    best = ci.get("most_probable_work_email", {})
    email = best.get("email", "") or ""
    if not email:
        for e in ci.get("work_emails", []):
            if e.get("email"):
                email = e["email"]; break
    email_status = best.get("status", "")  # DELIVERABLE / HIGH_PROBABILITY / CATCH_ALL
    # Phone
    phone_list = ci.get("phones", [])
    phone = phone_list[0].get("number", "") if phone_list else ""
```

### Key Notes
- Cloudflare-fronted — call with `curl` + a browser `User-Agent` (conventions rule #8); never Python `requests`/`urllib`
- Base URL is `app.fullenrich.com` (NOT `api.fullenrich.com`)
- Use v2 (not v1)
- Max 100 contacts per batch
- Submit response key is `enrichment_id` (UUID)
- Email: `contact_info.most_probable_work_email.email`
- Phone: `contact_info.phones[0].number`
- If credits run out mid-batch: `status = "CREDITS_INSUFFICIENT"`, partial results returned
- Email status values: `DELIVERABLE`, `HIGH_PROBABILITY`, `CATCH_ALL`

### Cost
~0.8 credits/contact

### Docs
https://docs.fullenrich.com

---

## Provider 2: Pipe0 Email Waterfall

**Pipe ID:** `people:workemail:profileurl:waterfall@1`
**Auth:** `Authorization: Bearer $PIPE0_API_KEY`
**Use curl** — Python requests blocked by Cloudflare.

### Submit
```json
{
  "config": {"environment": "production"},
  "pipes": [{"pipe_id": "people:workemail:profileurl:waterfall@1"}],
  "input": [
    {"id": "1", "profile_url": "https://linkedin.com/in/janedoe"}
  ]
}
```

### Key Notes
- **Submit response key is `id`** (not `task_id`) — use this value for polling: `GET /pipes/check/{id}`
- `email_validation_status` field is also returned alongside `work_email` in each record
- **Email quality: ~15–25% of hits may be stale** (old employer email) for EU audiences. Waterfall picks up the most recent known email regardless of current role. Always post-filter: remove personal domains (gmail, yahoo, etc.) and cross-check email domain against current company. In EU SME test: 37/43 raw hits, 30/43 valid after filtering 7 stale/personal.

### Poll
```
GET https://api.pipe0.com/v1/pipes/check/{id}
```
Done when: `status == "completed"`. Use 30s interval, 600s timeout (~3 min for 43 contacts). Keep batches ≤100 contacts.

### Parse
```python
records = result.get("records", {})
for rid, rec in records.items():
    fields = rec.get("fields", {})
    email  = (fields.get("work_email", {}) or {}).get("value", "") or ""
    status = (fields.get("email_validation_status", {}) or {}).get("value", "") or ""
    # work_email.value is a plain string, NOT nested
```

### Post-filtering (Recommended)
After enrichment, filter out stale/personal emails:
```python
PERSONAL_DOMAINS = {'gmail.com','yahoo.com','hotmail.com','outlook.com','icloud.com'}
df['email'] = df['email'].apply(
    lambda e: "" if (e and e.split('@')[-1].lower() in PERSONAL_DOMAINS) else e
)
# Also manually flag emails where domain doesn't match current company
```

### Waterfall Providers & Cost
| Provider | Cost |
|----------|------|
| HunterMail | 1.00 cr |
| LeadMagic | 2.00 cr |
| FindyMail | 2.00 cr |
| Crustdata | 3.50 cr |
Stops at first hit. Total: 1.00–3.50 cr/contact.

---

## Provider 3: BetterContact (Email or Phone)

**Endpoint:** `POST https://app.bettercontact.rocks/api/v2/async`
**Auth:** `X-API-KEY: $BETTERCONTACT_API_KEY`

### Submit (max 100 contacts/batch)
```json
{
  "enrich_email_address": false,
  "enrich_phone_number": true,
  "data": [
    {
      "first_name": "Jane",
      "last_name": "Doe",
      "company_domain": "example.com",
      "linkedin_url": "https://www.linkedin.com/in/janedoe",
      "custom_fields": {"row_id": "0"}
    }
  ]
}
```

### Poll
```
GET https://app.bettercontact.rocks/api/v2/async/{request_id}
```
Done when: `response["status"] == "terminated"` (NOT "completed")
- Phone only: ~3–5 min/100 contacts. Use 900s timeout.
- Email only or both: 30–90 min. Use 3600s timeout.
- `on hold` = credits exhausted, batch paused — no cancel endpoint.

### Parse
```python
for entry in result.get("data", []):
    cf = entry.get("custom_fields", [])  # ARRAY, not dict
    row_id = next((f["value"] for f in cf if f.get("name") == "row_id"), "")
    phone = entry.get("contact_phone_number") or ""
    email = entry.get("contact_email_address") or ""
    email_status = entry.get("contact_email_address_status") or ""
```

### Key Notes
- Cloudflare-fronted — call with `curl` + a browser `User-Agent` (conventions rule #8); never Python `requests`/`urllib`
- Base URL: `app.bettercontact.rocks` (not `api.`)
- Max 100 contacts per batch
- Submit response key: `id` (not `task_id` or `request_id`)
- `status` for completion: `"terminated"`, not `"completed"`
- `custom_fields` sent as object `{"key": "val"}`, returned as **array**: `[{"name": "key", "value": "val", "position": 0}]`
- Email field: `contact_email_address`, status: `contact_email_address_status`
- Phone field: `contact_phone_number`
- `enriched: False` entries can still have email values — these are low-confidence (catch_all_not_safe). Count but flag.
- Summary `total` field excludes `not_found` — use `len(data)` for verification

### Cost
- Email only: ~0.35 cr/contact
- Phone only: ~1–2 cr/contact
- Can spike to 7+ cr/contact for enterprise audiences (complex email infra)

### Docs
https://doc.bettercontact.rocks

---

## Provider 4: Pipe0 LinkedIn URL (When Missing)

**Pipe ID:** `people:profileurl:name@1`

### Request
```json
{
  "config": {"environment": "production"},
  "pipes": [{"pipe_id": "people:profileurl:name@1"}],
  "input": [
    {"id": "1", "name": "John Smith", "company_name": "Example Inc", "location_hint": "United States"}
  ]
}
```

### Cost
0.60 credits/operation

---

## Provider 5: Pipe0 Phone Pipes

**Pipe IDs:**
- `people:phone:profile:waterfall@1` — input: `profile_url` (LinkedIn URL)
- `people:phone:workemail:waterfall@1` — input: `work_email`

### Cost
2.00–7.00 credits/operation

### Known Coverage
- **DACH:** **~92% hit rate (n=74)**, April 2026 DACH e-commerce SME run — response field is `mobile`, not `phone`
- **SA:** 0% hit rate observed — skip for SA audiences
- Solid as both **primary** (when contacts come from Pipe0 search → no FE phone available) and **FE-fallback** (71% recovery on FE contacts missing phones, n=7). Use FE first if the contact already went through FE search/enrich (you've paid for it); use Pipe0 waterfall on the remainder.

---

## Output

Updated CSV at `csv/output/contacts_enriched.csv` with added columns:
```
email, email_status, email_source,
phone, phone_source
```

All original columns preserved.

---

## Troubleshooting

### Pipe0: Task processing timeout
Batch too large. Keep batches ≤100 contacts. Re-poll task_id — partial results may be in `records`.

### Pipe0: CreditBalanceInsufficient
Batch fails but credits for provider responses are consumed. Top up, save task_id, do NOT resubmit. New batch for failed records only.

### BetterContact: Job never terminates
Timeout too short. Phone: 900s min. Email: 3600s min.

### BetterContact: custom_fields parse error
`custom_fields` is an array `[{"name": "row_id", "value": "0"}]`, not a dict.

### FullEnrich: 404 on results
Wrong path. Correct: `https://app.fullenrich.com/api/v2/contact/enrich/bulk/{enrichment_id}`

### FullEnrich: Phone field empty
Prefer `contact_info.most_probable_phone.number` (typically mobile) over `phones[0].number` (can be landline). If `most_probable_phone` is absent, fall back to `phones[0]`. If both empty, fall back to Pipe0 `people:phone:profile:waterfall@1` on the LinkedIn URL.

---

## What's Missing (To Document)

- Pipe0 phone pipe coverage by geography (currently only DACH/SA tested)
- FullEnrich v2 phone hit rates by geography
- BetterContact email-only production hit rates outside SA
