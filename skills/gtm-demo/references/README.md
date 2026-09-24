# gtm-demo references — the scripts every demo run used to rewrite

Copy nothing: run them in place from `{client-slug}-gtm/`, e.g.
`python3 ~/.claude/skills/gtm-demo/references/check_messages.py`. They are the Sphere run (2026-09-24),
generalized; the perma-trade and Reduzer runs each hand-wrote the same five scripts.

| Step | Script | Reads | Writes |
|---|---|---|---|
| 3 | `bc_search.py <name> <body.json>` | a BetterContact Lead Finder body | `csv/intermediate/raw/bc_<name>.json` |
| 5 | `fe_enrich.py <in.csv> <out.csv>` | rows Kitt found nothing for (optional `email_domain`) | same rows + FE address |
| 6 | `check_messages.py` | contacts + `messages.json` + `deck.json` | CLEAN / problems |
| 7a | `build_output.py` | contacts + `signals.csv` + `messages.json` + `deck.json` | `csv/output/*.csv`, `deck_data.json`, `sanitize_report.json` |
| 7b | `render_deck.py <out.html>` | `deck_data.json` + `deck.json` + `../deck_template.html` | the deck |
| 7c | `qa_deck.py <out.html>` | the deck + the above | PASS / FAIL (exit 1) |

## Data contract

**`csv/intermediate/contacts_enriched.csv`** — one row per card, after the Kitt gate (Step 5). Required:
`company_name, company_domain, segment, full_name, first_name, last_name, linkedin_profile_url, email,
email_status, country`. `segment` is a key from `deck.json`; `country` is display text in the deck's
language ("Deutschland"). An address ships only with `email_status` `valid` or `valid-risky`.

**`csv/intermediate/signals.csv`** — signal-search output after scoring: `company_domain`, `scoredSignals`
(JSON list; the first item is the kept signal: `date` YYYY-MM-DD, `summary` in the deck language,
`source_url` = the article itself). `[]` = ICP-fit card.

**`csv/intermediate/messages.json`** — keyed by `linkedin_profile_url`:
```json
{"https://www.linkedin.com/in/…": {
  "job_title": "CTO", "why_they_fit": "timeless fit facts + the role, deck language",
  "lang": "de", "register": "sie", "cta_variant": "A",
  "email_subject": "…", "email_p1": "Guten Tag Herr X,\nhook", "email_p2": "bridge + offer",
  "email_p3": "CTA\nViele Grüße\nName", "li_p1": "Guten Tag Herr X,\nhook", "li_p2": "offer + CTA"}}
```
No kept address → the four `email_*` fields are empty. CTA `A` ends with "?", `B` does not.

**`context/deck.json`** — the deck's own copy:
```json
{"lang": "de", "client_name": "Acme", "client_slug": "acme",
 "hero_headline": "≤ 7 words", "hero_intro": "≤ 2 sentences, what they get",
 "stat4": {"n": "3", "label": "Branchen"},
 "segments": [{"key": "machinery", "title": "Maschinenbau", "intro": "who they are, who decides"}],
 "approach_signal": "…", "approach_icp": "…", "method_note": "…",
 "footer_headline": "…", "footer_body": "…", "footer_meta": "Erstellt für Acme von keinsaas · Monat Jahr",
 "cta_label": "Termin buchen", "signoff": {"de": "Viele Grüße\nName", "fr": "Meilleures salutations\nName"}}
```
The booking link is fixed in `render_deck.py` (keinsaas's, always). Labels exist for `de` and `en`.
