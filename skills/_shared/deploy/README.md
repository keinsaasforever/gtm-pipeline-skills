# Demo Deployment (headless webhook)

Run the `/gtm-pipeline:demo` skill headless when a website form submits a prompt. The skills are
**orchestrator-agnostic** (README) — this is the thin runner your webhook layer calls. The website
never talks to Claude directly; your integration layer (n8n, a small server, a queue worker) shells
out to `run_demo.sh`.

```
website form ──▶ your webhook layer ──▶ run_demo.sh ──▶ claude -p "/gtm-pipeline:demo …" ──▶ result.json
```

## Why `claude -p` here but not interactively

`claude -p` is the **outer entrypoint** for a headless run — the agent it starts does all the
LLM work (extraction, scoring, filtering, messages) itself, exactly as in an interactive session.
So there is **no nested `claude -p`** and no third-party LLM on the default path. Interactively you
just run `/gtm-pipeline:demo` in the terminal; the same skill code runs. (See `conventions.md` →
Model Routing.)

## Invocation

```bash
# positional flags
~/.claude/skills/gtm-pipeline/_shared/deploy/run_demo.sh \
  --prompt "We sell warehouse automation to mid-size 3PLs in DACH" \
  --requester-email "ops@acme.com" --with-signals --max-contacts 10

# or JSON on stdin (from a webhook body)
echo '{"prompt":"…","requester_email":"ops@acme.com","with_signals":true,"max_contacts":10}' \
  | ~/.claude/skills/gtm-pipeline/_shared/deploy/run_demo.sh --json
```

### Input contract
| Field | Source | Notes |
|-------|--------|-------|
| `prompt` (required) | form free-text | the offering + target audience |
| `requester_email` | form | domain auto-resolved in Step 1 to establish what they sell |
| `with_signals` | form/config | enables the buying-intent pass (pricier, sharper) |
| `max_contacts` | config | default 10 |

### Output contract — `{client-slug}-gtm/result.json`
```json
{ "status": "ok", "client_slug": "acme",
  "contacts": 10, "with_signals": true,
  "deck_path": "csv/output/acme_demo_deck.html",
  "csv_path": "csv/output/contacts_enriched.csv",
  "assumptions": ["Interpreted 'ops leaders' as Head of Operations / COO"],
  "sanitize_report": { "rows_dropped_bad_email": 2, "signals_dropped": 3, "columns_dropped": ["source"] } }
```
The runner `exec`s `claude -p`; the skill prints the absolute path to `result.json` as its last
line. Your webhook layer reads that file.

## Environment
| Var | Default | Purpose |
|-----|---------|---------|
| `GTM_WORKROOT` | `$PWD` | where `{client-slug}-gtm/` is created |
| `CLAUDE_DEMO_MODEL` | `sonnet` | orchestration model (Opus is used per-task for extraction/scoring/messages) |
| `CLAUDE_PERMISSION_MODE` | `acceptEdits` | see below |

Provider keys resolve through `resolve_env.sh` / `GTM_ENV_PATH` as usual — the default `agent`
signal backend needs **no** LLM key (only `PARALLEL_API_KEY` for search).

## Permissions (read before deploying)

`acceptEdits` auto-approves file edits but still prompts for Bash/network — which will **hang** a
headless run that must call provider APIs. For an unattended server, either:
- run inside an **isolated, sandboxed environment** with `CLAUDE_PERMISSION_MODE=bypassPermissions`, or
- configure an allowed-tools policy (settings.json) that permits the specific Bash/network the
  providers need.

Only use `bypassPermissions` in an environment you control and isolate — never on a shared machine.
Delivery stays gated regardless: the skill builds the deck/email but never sends on the user's behalf.

## Not included (integration layer)
Queueing/concurrency, retries, the HTTP receiver, and Stripe (paid full-pipeline) are yours to
wire — the runner is deliberately just the skill entrypoint.
