# GTM Pipeline Skills

Seventeen Claude Code skills for B2B sales: ten for building lead generation pipelines (from company discovery to enriched contacts ready for outreach), and seven for revenue intelligence on the deals you already have (meeting prep, CRM updates and follow-ups from call transcripts, live call assist, daily plan, deal health). Using these get you Clay quality data for 10-20% of the price.

Each skill is a standalone Markdown instruction file that Claude reads and executes as an agent. Use them individually or chain them into a full pipeline.

We are using ONLY the best and latest data providers and enrichment services and are not associated or affiliated with any of them. 

---

## Quick Start

```bash
git clone https://github.com/Keinsaas/gtm-pipeline-skills
cd gtm-pipeline-skills
./install.sh
```

Then open a project in Claude Code and run:
```
/gtm-pipeline:setup
```

The setup skill walks you through API keys, PhantomBuster agent IDs (auto-looked-up via MCP if available), and your first client ICP — in under 10 minutes.

---

## Skills

| Skill | What It Does |
|-------|-------------|
| `/gtm-pipeline:setup` | Onboarding — install, configure keys, set up first client |
| `/gtm-pipeline:pipeline` | Orchestrator — plan and run the full pipeline end-to-end |
| `/gtm-pipeline:company-search` | Build a company list (Sales Navigator, Parallel FindAll, Firecrawl, web) |
| `/gtm-pipeline:company-enrichment` | Enrich companies with headcount, revenue, growth metrics + ICP scoring (0–100) |
| `/gtm-pipeline:signal-search` | Find buying intent signals (funding, hiring, leadership). Score each signal 1–100 |
| `/gtm-pipeline:people-search` | Find contacts by role at target companies, or prospect by persona |
| `/gtm-pipeline:contact-filter` | Rank and filter contacts before enrichment — saves credits |
| `/gtm-pipeline:people-enrichment` | Enrich contacts with verified work email and phone |
| `/gtm-pipeline:outreach` | Run LinkedIn connection requests and messages via PhantomBuster |
| `/gtm-pipeline:demo` | Generate a demo lead list (~10 contacts + messages) from an ICP description |

### Revenue intelligence

These work on the user's own connected tools (CRM, mail, calendar, meeting transcripts, team chat). Their steps need no local files, scripts or API keys, so they can run in claude.ai/Cowork and ChatGPT as well as Claude Code. For those hosts they need packaging as a plugin that bundles `_shared/revenue.md`; today they install like the others, via `install.sh`. Vexa is optional. Shared rules: `skills/_shared/revenue.md`. Routines: `docs/ROUTINES.md`.

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
company-search → company-enrichment → ICP scoring → signal-search → people-search → contact-filter → people-enrichment
```

**Signal-First** (discovering companies via buying intent):
```
signal-search (discovery) → company-enrichment → ICP scoring → people-search → contact-filter → people-enrichment
```

See `docs/ARCHITECTURE.md` for the full flow diagram with CSV handoffs and cost checkpoints.

---

## API Keys Required

Copy `.env.example` to your env file and fill in:

| Key | Provider | Cost Model |
|-----|----------|-----------|
| `PIPE0_API_KEY` | pipe0.com | Credits per task |
| `FULLENRICH_API_KEY` | fullenrich.com | Per enrichment |
| `SERPAPI_API_KEY` | serpapi.com | Per search |
| `PARALLEL_API_KEY` | parallel.ai | Per task (processor-based) |
| `FIRECRAWL_API_KEY` | firecrawl.dev | Per crawl / per page |
| `APIFY_API_KEY` | apify.com | Per actor run |
| `OPENROUTER_API_KEY` | openrouter.ai | Per token |
| `PHANTOMBUSTER_API_KEY` | phantombuster.com | Plan-based |
| `BETTERCONTACT_API_KEY` | bettercontact.rocks | Per enrichment (optional) |
| `VEXA_API_KEY` | vexa.ai (or self-hosted) | Per bot hour (optional, revenue-intelligence transcripts in Claude Code) |

You don't need all of them. See `/gtm-pipeline:setup` — it only asks for what your use case requires.

---

## Project Structure

Each project (your company, a client, a campaign) gets its own working directory:

```
{slug}-gtm/
├── context/
│   ├── profile.md          # What they sell, value prop, tone
│   ├── icp.md              # Job tiers, industry tiers, location tiers, size filter
│   └── provider_performance.md
├── csv/
│   ├── input/
│   │   └── companies_raw.csv
│   ├── intermediate/
│   │   ├── companies_enriched.csv
│   │   ├── companies_scored.csv
│   │   ├── signals.csv
│   │   ├── contacts_found.csv
│   │   └── contacts_filtered.csv
│   └── output/
│       └── contacts_enriched.csv
└── run_log.md
```

The setup skill creates this structure for you. See `examples/sample-client-gtm/` for a fully filled-out reference.

---

## Personal Configuration

Your API keys and PhantomBuster agent IDs stay on your machine:

```
skills/_shared/local.md     ← gitignored, created from local.example.md by install.sh
~/.env.gtm                  ← default API key location (or set GTM_ENV_PATH)
```

---

## What Not to Put in This Repo

- API keys or session cookies (use `~/.env.gtm` or your env manager)
- Contact lists, lead data, or CRM exports
- Client names, domains, or commercial terms
- PhantomBuster agent IDs (go in `_shared/local.md`, which is gitignored)

---

## For Production Integration

The skills handle data logic (enrichment, scoring, filtering). For automated production pipelines — webhook triggers, n8n orchestration, monitoring, scheduled runs — that's a separate integration layer. The skills are designed to compose with any orchestrator.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Fork the repo, make changes on a branch, submit a PR to `main`.

The `stable` branch is the maintainer's production copy — contributions go to `main`.

---

## License

MIT
