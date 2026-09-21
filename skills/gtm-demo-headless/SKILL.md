---
name: gtm-pipeline:demo-headless
description: Unattended version of the GTM demo — builds a demo lead list (10 contacts per segment, 2 segments, 30 max) with personalized messages and a deck, asking the user nothing. Use when the run is triggered by a webhook, a cron/scheduled task, `claude -p`, or any context with no human to answer questions. For an interactive run where the operator can be asked, use gtm-demo instead.
---

# Demo — headless

Same pipeline as **gtm-demo**, with every decision pre-made. Nobody is watching this run: it never
asks, never waits, and never exceeds its budget.

**Read `~/.claude/skills/gtm-pipeline/_shared/conventions.md` and `~/.claude/skills/gtm-demo/SKILL.md`
first.** Execute gtm-demo's steps exactly as written, with the overrides below replacing its
decision points. Everything not listed here (directory layout, contact-filter, enrichment waterfall,
signal rubric, message structure, sanitization, deck anatomy, QA) is unchanged, so the two skills
cannot drift.

---

## The three rules that make it headless

1. **Never ask.** No AskUserQuestion, no "confirm before proceeding", no waiting. Every ambiguity is
   resolved by the defaults below and recorded in `context/icp.md` under `## Assumptions`.
2. **Never exceed the budget: 70 credits + $3 of web research per run.** Read each provider's own
   credit figure as you go (`metadata.credits`, `credits_consumed`, account balance) and keep a
   running total in `run_log.md`. At the cap: stop buying, finish with what you have, log the
   shortfall in `result.json`. Do not "just top up a little".
3. **Never widen a pull to fix quality.** Fix the filters and re-pull small (once), or switch to the
   research route. `target ÷ pass rate`, then stop.

---

## Fixed decisions (these replace the questions gtm-demo may ask)

| Decision | Headless default |
|---|---|
| Size | 10 contacts per segment, **2 segments**, even split (3 when the prompt names three). A third segment only if the first two end short, never past **30 total**. One contact per company. |
| Segments | **The customer groups the prompt names**, 10 each, at most 3. If it names none: the top 2 buyer types by prominence on the client's own site (Step 1b), ties breaking toward the segment the client's customer quotes come from. |
| Existing customers | Excluded (gtm-demo Step 1, item 3): the client's reference/customer pages and partner or dealer finder, matched by **domain**, parent and sister companies included. |
| Companies named in the prompt | Treated as existing customers (gtm-demo Step 1, item 4): excluded with their group, lookalikes shown, recorded under `## Assumptions`. |
| Personas | Derived in Step 1b from the client site. Never search before `## Personas` exists in `context/icp.md`. |
| Route | Filtered people search (gtm-demo 3b), BetterContact first with `limit_per_company: 1`, FullEnrich second. Switch to the research route (3c) when no industry value fits, or after **two** probe queries return <½ the target or mostly off-segment rows. |
| Countries / regions | Exactly what the prompt names. Never add a neighbouring market. If it names none, use the client's own home market. |
| Draft language | Each contact's own market language (bokmål for Norway, Swedish for Sweden, German for DACH…), English only when the market is English-speaking or the contact's own profile is English. Deck copy: English, unless the whole audience shares one non-English market, then that language. |
| Signals | ON, but only for the **final selected companies**, after enrichment, and only while budget remains. Fresh ≤60 days, sourced from the article itself, verified per the signal rubric. Companies web search leaves without a kept signal get the Firecrawl fallback (signal-search Step 5c): **10 pages per company at most**, counted in `spend.firecrawl_pages`, not in the $3. Still no signal → ICP-fit card built from timeless fit facts only (gtm-demo Step 6 → Hook sources). |
| Phones | Never. |
| Email waterfall | FullEnrich first (it returns a deliverability grade), PhantomBuster only for the misses and only if it is available. Drop any address whose domain is not the target company's. |
| Deck CTA | keinsaas's booking link (gtm-demo Step 7b `{{CALENDAR_URL}}`). Never the prospect's own booking link. |
| Delivery | Never send anything. Write the deck, the CSV and the cover email to files. |
| Failure of any single step | Log it, continue with the next step, and report it in `result.json`. A missing signal, a missing email or a failed provider never aborts the run. |

---

## Output contract

Write `{client-slug}-gtm/result.json` as the last action:

```json
{ "status": "ok" | "partial",
  "client_slug": "...",
  "segments": ["contractor", "developer"],
  "contacts": 20,
  "companies": 20,
  "with_signal": 7,
  "with_email": 18,
  "with_signals_enabled": true,
  "deck_path": "csv/output/... .html",
  "csv_path": "csv/output/contacts_enriched.csv",
  "spend": { "credits": 41.5, "web_usd": 1.2, "firecrawl_pages": 90, "cap_hit": false },
  "assumptions": ["…"],
  "shortfalls": ["…"],
  "sanitize_report": { "…": 0 } }
```

`status: "partial"` whenever a target was missed, the cap was hit, or a step was skipped — with the
reason in `shortfalls`. A partial run that ships 14 good contacts is a success; a run that quietly
buys its way to 30 is not.

---

## Invocation

```bash
claude -p "/gtm-pipeline:demo-headless $PROMPT" --model sonnet --permission-mode acceptEdits
```

Input: free-text prompt describing the offering + target audience, plus the requester's email (the
domain is resolved in Step 1). Optional JSON: `{ "prompt", "requester_email", "with_signals": bool,
"max_contacts": 30, "segments": ["…"] }` — an explicit `segments` or `max_contacts` overrides the
defaults above, but `max_contacts` is still clamped to 30 and the budget cap still applies.

Model routing per `conventions.md`: Sonnet orchestrates, Opus does extraction/scoring/messages via
subagents. Signal-search runs `--llm-backend agent` (no nested `claude -p`).
