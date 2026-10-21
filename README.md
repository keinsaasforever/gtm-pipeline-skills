# GTM Pipeline Skills

A Claude plugin with fifteen skills for B2B sales:
- **Eight for prospecting**: from company discovery and buying signals to a ranked contact list. Using these gets you Clay-quality data for 10-20% of the price.
- **Seven for revenue intelligence on the deals you already have**: meeting prep, CRM updates and follow-up drafts from call transcripts, live call assist, daily plan and deal health.

Work emails, phone numbers and outreach (email and LinkedIn) run in [keinsaas Sales Agent](https://www.keinsaas.com/sales-agent). The plugin bundles its connector, and the prospecting skills hand their ranked list to it.

Each skill is a standalone Markdown instruction file that Claude reads and executes as an agent. Use them individually or chain them into a full pipeline.

We use ONLY the best and latest data providers and are not associated or affiliated with any of them.

---

## Install

**Claude Code:**
```bash
claude plugin marketplace add keinsaasforever/gtm-pipeline-skills
claude plugin install gtm-pipeline@keinsaas-gtm
```

**claude.ai / Cowork:** Customize > Plugins > add the `keinsaasforever/gtm-pipeline-skills` repository, then install `gtm-pipeline`.

Then run:
```
/gtm-pipeline:setup
```

The setup skill walks you through API keys, the Sales Agent connector and your first client ICP, in under 10 minutes.

Contributors working from a checkout can run `./install.sh`. It installs the plugin from the local folder and removes the `~/.claude/skills/gtm-*` symlinks that earlier versions created. Update with `claude plugin update gtm-pipeline@keinsaas-gtm`.

### Where the skills run

| Skills | Claude Code | claude.ai / Cowork | ChatGPT |
|---|---|---|---|
| Prospecting (scripts + your API keys) | Yes | No (needs local scripts and keys) | No |
| Revenue intelligence (your connectors) | Yes | Yes | Same skill format; packaging for ChatGPT is not set up yet |

---

## Skills

### Prospecting

| Skill | What It Does |
|-------|-------------|
| `/gtm-pipeline:setup` | Onboarding: plugin check, API keys, Sales Agent connector, first client |
| `/gtm-pipeline:pipeline` | Orchestrator: plan and run the full pipeline end-to-end, then hand off to Sales Agent |
| `/gtm-pipeline:company-search` | Build a company list (Parallel FindAll, Firecrawl, Pipe0, web) |
| `/gtm-pipeline:company-enrichment` | Enrich companies with headcount, revenue and more, plus ICP scoring (0–100) |
| `/gtm-pipeline:signal-search` | Find buying intent signals (funding, hiring, leadership) and score each 1–100 |
| `/gtm-pipeline:people-search` | Find contacts by role at target companies, or prospect by persona |
| `/gtm-pipeline:contact-filter` | Rank and filter contacts before they go to Sales Agent (fewer, better contacts) |
| `/gtm-pipeline:demo` | Demo lead list (~10 contacts + messages) from an ICP description; with the Sales Agent connector it includes verified emails |

### Revenue intelligence

These work on the user's own connected tools (CRM, mail, calendar, meeting transcripts, team chat), with no local files, scripts or API keys required. Vexa is optional. Shared rules: `shared/revenue.md`, copied into each skill's `references/` by `scripts/sync-shared.sh`. Routines: `docs/ROUTINES.md`.

| Skill | What It Does |
|-------|-------------|
| `/gtm-pipeline:revenue-setup` | Sales playbook: stages and exit criteria, CRM field standards and write modes, method, follow-up style, transcript source |
| `/gtm-pipeline:call-transcripts` | Find a call transcript (notetaker, Google Meet, Teams, Zoom, Drive) or record one with a Vexa bot (fallback) |
| `/gtm-pipeline:meeting-prep` | One-page brief before a meeting: deal status, open commitments, news, gaps and questions to ask |
| `/gtm-pipeline:post-call` | CRM updates under the playbook's write rules, next-step tasks, follow-up email as a draft, change log |
| `/gtm-pipeline:live-assist` | In-call coaching from the live Vexa transcript: open questions, gaps, objection answers |
| `/gtm-pipeline:daily-plan` | Today's meetings and the 5–10 actions that matter, ranked |
| `/gtm-pipeline:deal-review` | Momentum score and source-backed risks per deal, one action each |

---

## Pipeline Architecture

Two workflows depending on what you start with:

**Company-First** (you have a company list or bounded market):
```
company-search → company-enrichment → ICP scoring → signal-search → people-search → contact-filter → Sales Agent
```

**Signal-First** (discovering companies via buying intent):
```
signal-search (discovery) → company-enrichment → ICP scoring → people-search → contact-filter → Sales Agent
```

See `docs/ARCHITECTURE.md` for the full flow diagram with CSV handoffs and cost checkpoints.

---

## API Keys

Copy `.env.example` to `~/.env.gtm` (or export `GTM_ENV_PATH` to use another file) and fill in what you need:

| Key | Provider | Cost Model |
|-----|----------|-----------|
| `PIPE0_API_KEY` | pipe0.com | Credits per task |
| `FULLENRICH_API_KEY` | fullenrich.com | Per search result (Finder) |
| `BETTERCONTACT_API_KEY` | bettercontact.rocks | Per request (Lead Finder, optional) |
| `SERPAPI_API_KEY` | serpapi.com | Per search |
| `PARALLEL_API_KEY` | parallel.ai | Per task (processor-based) |
| `FIRECRAWL_API_KEY` | firecrawl.dev | Per crawl / per page |
| `APIFY_API_KEY` | apify.com | Per actor run (optional) |
| `OPENROUTER_API_KEY` | openrouter.ai | Per token (legacy, optional) |
| `VEXA_API_KEY` | vexa.ai (or self-hosted) | Per bot hour (optional, meeting transcripts in Claude Code) |

You don't need all of them. `/gtm-pipeline:setup` only asks for what your use case requires. The revenue-intelligence skills need none.

---

## Project Structure

Each project (your company, a client, a campaign) gets its own working directory:

```
{slug}-gtm/
├── context/
│   ├── profile.md          # What they sell, value prop, tone
│   ├── icp.md              # Job tiers, industry tiers, location tiers, size filter
│   ├── playbook.md         # Sales playbook for the revenue-intelligence skills
│   └── provider_performance.md
├── csv/
│   ├── input/
│   │   └── companies_raw.csv
│   ├── intermediate/
│   │   ├── companies_enriched.csv
│   │   ├── companies_scored.csv
│   │   ├── signals.csv
│   │   ├── contacts_found.csv
│   │   └── contacts_filtered.csv   # hand-off to Sales Agent
│   └── output/
│       └── contacts.csv            # demo contacts + messages
└── run_log.md
```

The setup skill creates this structure for you. See `examples/sample-client-gtm/` for a fully filled-out reference.

---

## Plugin Layout

```
.claude-plugin/plugin.json       # plugin manifest (name: gtm-pipeline)
.claude-plugin/marketplace.json  # this repo is also its own marketplace (keinsaas-gtm)
.mcp.json                        # bundled connector: sales-agent → https://mcp.keinsaas.com/mcp
skills/<name>/SKILL.md           # one folder per skill
shared/                          # conventions, revenue rules, sanitizer, env resolver, deploy runner
scripts/sync-shared.sh           # copies shared/revenue.md into the revenue skills (--check for CI)
```

---

## What Not to Put in This Repo

- API keys (use `~/.env.gtm` or your env manager)
- Contact lists, lead data, or CRM exports
- Client names, domains, or commercial terms

---

## For Production Integration

The skills handle data logic (search, scoring, filtering, messages). Automated production runs (webhook triggers, monitoring, scheduled runs) need a separate integration layer, and the skills compose with any orchestrator. See `shared/deploy/` for a headless demo runner and `docs/ROUTINES.md` for scheduled tasks.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Fork the repo, make changes on a branch, submit a PR to `main`.

The `stable` branch is the maintainer's production copy — contributions go to `main`.

---

## License

MIT
