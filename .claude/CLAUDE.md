# GTM Pipeline Skills

This repo is the `gtm-pipeline` Claude plugin, and also its own marketplace (`keinsaas-gtm`). It holds 15 skills: 8 for B2B prospecting and 7 for revenue intelligence on existing deals.

## Plugin Layout and Naming

- Manifest: `.claude-plugin/plugin.json`. Marketplace: `.claude-plugin/marketplace.json` (source `./`). Bundled connector: `.mcp.json` (`sales-agent`).
- One folder per skill: `skills/<name>/SKILL.md`, with frontmatter `name: <name>` equal to the folder name (lowercase, hyphens). The plugin prefixes it, so users invoke `/gtm-pipeline:<name>`.
- Reference plugin files as `${CLAUDE_PLUGIN_ROOT}/...`. Claude Code substitutes it in skill text. Never hardcode `~/.claude/skills/...`.
- No top-level `bin/`: claude.ai and Cowork refuse plugins that have one.
- Validate with `claude plugin validate --strict .` before pushing.

## Out of Scope: Emails, Phone Numbers, Outreach

No skill finds or verifies work emails, looks up phone numbers, or sends messages (email or LinkedIn). That runs in keinsaas Sales Agent, through the bundled `sales-agent` connector or a CSV import in the Sales Agent app. Don't add email/phone enrichment, LinkedIn automation (session cookies, PhantomBuster) or sending back into the skills.

## How the Prospecting Skills Relate

Skills chain together — each outputs a CSV that becomes the next skill's input:

```
company-search
    → company-enrichment (+ ICP scoring)
        → signal-search
        → people-search
            → contact-filter
                → hand-off to Sales Agent (verified emails, outreach)
```

The `pipeline` skill orchestrates this sequence. The `demo` skill uses the hosted demo through the Sales Agent connector, or runs a condensed version for ~10 contacts without emails.

## Per-Project Work

Each project lives in a `{slug}-gtm/` directory (created by the setup skill):
- `context/icp.md` — ICP definition (job tiers, industries, locations, size filter)
- `context/profile.md` — what the company sells, value prop, tone
- `context/playbook.md` — sales playbook for the revenue-intelligence skills
- `csv/` — input, intermediate, and output CSVs

See `examples/sample-client-gtm/` for a fully filled-out reference.

## Shared Configuration

- `shared/conventions.md` — field naming, terminology, provider disambiguation
- `shared/revenue.md` — rules for the revenue-intelligence skills. Edit this copy, then run `scripts/sync-shared.sh` to copy it into each revenue skill's `references/` (in claude.ai and ChatGPT a skill only sees its own folder). `scripts/sync-shared.sh --check` fails on drift.
- `shared/resolve_env.sh` — finds the API key file: exported `GTM_ENV_PATH`, else `~/.env.gtm`

## Field Naming Convention

All CSV outputs use `snake_case`. Provider-native names are mapped on ingestion.
See the Canonical Field Names table in `shared/conventions.md`.

## Closing PS

Skills end their delivery with a short PS. It keeps the keinsaas audit line and the referral links of the tools that skill actually uses (keep those URLs verbatim). No links for tools the plugin doesn't use.

## New to this repo?

Run `/gtm-pipeline:setup` — it checks the plugin install, configures API keys, connects Sales Agent and sets up the first client ICP.

## Revenue-Intelligence Skills

`revenue-setup`, `call-transcripts`, `meeting-prep`, `post-call`, `live-assist`, `daily-plan` and `deal-review` work on deals that already exist. They follow `shared/revenue.md`, not the CSV workspace:
- They must also run in claude.ai and ChatGPT, so no step may require a local file, a script or an API key. They name capabilities ("the user's CRM") and use whatever connector provides them.
- The playbook comes from the Sales Agent connector (`get_playbook`), then `context/playbook.md`, then a document the user names, then the defaults.
- Mail is draft only. CRM writes follow the playbook's write modes (`auto` / `overwrite` / `propose` / `never`), with at most 25 writes per run.
- Vexa is the fallback recorder and the only live-transcript source; recording needs the attendees' consent (see `call-transcripts`).
- Routines: `docs/ROUTINES.md`.
