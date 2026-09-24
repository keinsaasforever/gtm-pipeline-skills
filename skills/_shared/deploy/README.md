# Demo Deployment (headless webhook)

Run the `/gtm-pipeline:demo-headless` skill when a website form submits a prompt. It is the
unattended twin of `/gtm-pipeline:demo`: same steps, every decision pre-made, zero questions, and a
hard budget (70 credits + $3). The skills are
**orchestrator-agnostic** (README) — this is the thin runner your webhook layer calls. The website
never talks to Claude directly; your integration layer (n8n, a small server, a queue worker) shells
out to `run_demo.sh`.

```
website form ──▶ your webhook layer ──▶ run_demo.sh ──▶ claude -p "/gtm-pipeline:demo-headless …" ──▶ result.json
```

## Why `claude -p` here but not interactively

`claude -p` is the **outer entrypoint** for a headless run — the agent it starts does all the
LLM work (extraction, scoring, filtering, messages) itself, exactly as in an interactive session.
So there is **no nested `claude -p`** and no third-party LLM on the default path. Interactively you
just run `/gtm-pipeline:demo` in the terminal: it shares every step with the headless twin and only
differs where a decision could be asked about. (See `conventions.md` → Model Routing.)

## Invocation

```bash
# positional flags
~/.claude/skills/gtm-pipeline/_shared/deploy/run_demo.sh \
  --prompt "We sell warehouse automation to mid-size 3PLs in DACH" \
  --requester-email "ops@acme.com"

# or JSON on stdin (from a webhook body)
echo '{"prompt":"…","requester_email":"ops@acme.com","segments":["3PLs","retailers"]}' \
  | ~/.claude/skills/gtm-pipeline/_shared/deploy/run_demo.sh --json
```

### Input contract
| Field | Source | Notes |
|-------|--------|-------|
| `prompt` (required) | form free-text | the offering + target audience |
| `requester_email` | form | domain auto-resolved in Step 1 to establish what they sell |
| `with_signals` | form/config | default on; `false` / `--no-signals` turns the buying-intent pass off |
| `max_contacts` | config | default: 10 per segment × 2 segments; the skill clamps it to 30 |
| `segments` | form/config | default: the customer groups the prompt names (`--segments "a; b"` on the CLI) |

Leave a field out and the skill's own default applies; the runner forwards only what you set.

### Output contract — `{client-slug}-gtm/result.json`
The shape lives in one place: `gtm-demo-headless/SKILL.md` → **Output contract** (`status`,
`segments`, `contacts`, `with_signal`, `with_email`, `spend`, `shortfalls`, …). `status: "partial"`
is a normal outcome, with the reason in `shortfalls`.

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
