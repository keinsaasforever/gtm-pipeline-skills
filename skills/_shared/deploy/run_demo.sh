#!/usr/bin/env bash
# run_demo.sh — headless entrypoint for the GTM demo skill.
#
# A thin, orchestrator-agnostic wrapper. A webhook layer (n8n, a small server, etc.) calls this
# with the website form's prompt; it invokes /gtm-pipeline:demo via the Claude Code CLI (`claude -p`)
# and the skill writes {client-slug}-gtm/result.json. `claude -p` is the OUTER entrypoint, so the
# agent does all LLM work itself — no nested `claude -p`, no third-party LLM on the default path.
#
# Usage:
#   run_demo.sh --prompt "we sell X to Y..." [--requester-email a@b.com] [--with-signals] [--max-contacts 10]
#   echo '{"prompt":"...","requester_email":"a@b.com","with_signals":true}' | run_demo.sh --json
#
# Requires: gtm-pipeline skills installed (./install.sh) and the `claude` CLI on PATH.
# See deploy/README.md for the full input/output contract and permission notes.
set -euo pipefail

PERMISSION_MODE="${CLAUDE_PERMISSION_MODE:-acceptEdits}"   # see README: headless servers may need bypassPermissions
MODEL="${CLAUDE_DEMO_MODEL:-sonnet}"                        # orchestration model (Opus used for extraction/scoring/messages)
WORKROOT="${GTM_WORKROOT:-$PWD}"                            # where {client-slug}-gtm/ is created
PROMPT="" ; REQUESTER_EMAIL="" ; WITH_SIGNALS="" ; MAX_CONTACTS="10" ; JSON_MODE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt)          PROMPT="$2"; shift 2;;
    --requester-email) REQUESTER_EMAIL="$2"; shift 2;;
    --with-signals)    WITH_SIGNALS="1"; shift;;
    --max-contacts)    MAX_CONTACTS="$2"; shift 2;;
    --json)            JSON_MODE="1"; shift;;
    -h|--help)         grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

# JSON payload on stdin → shell vars (values shell-quoted, so eval is safe).
if [[ -n "$JSON_MODE" ]]; then
  eval "$(cat | python3 -c '
import sys, json, shlex
d = json.load(sys.stdin)
print("PROMPT=%s"          % shlex.quote(str(d.get("prompt", ""))))
print("REQUESTER_EMAIL=%s" % shlex.quote(str(d.get("requester_email", ""))))
print("WITH_SIGNALS=%s"    % ("1" if d.get("with_signals") else ""))
print("MAX_CONTACTS=%s"    % shlex.quote(str(d.get("max_contacts", 10))))
')"
fi

[[ -z "$PROMPT" ]] && { echo "ERROR: no prompt provided (--prompt or --json)" >&2; exit 2; }

SIGNAL_FLAG=""; [[ -n "$WITH_SIGNALS" ]] && SIGNAL_FLAG="--with-signals"

read -r -d '' SYS <<'EOF' || true
Headless demo run (no human in the loop). Rules:
- Never ask the user questions. Infer every field per Step 1 — resolve the requester's email domain,
  classify the relationship to the target audience — and record assumptions in context/icp.md.
- Model routing (conventions.md): Sonnet for filtering + deck assembly, Opus for signal extraction,
  scoring, and message generation.
- signal-search runs with --llm-backend agent; score signals in-context. Never spawn a nested `claude -p`.
- Always run Step 7a sanitization (sanitize.py) before any deliverable. Delivery is gated: build the
  deck/email, do NOT send.
- On completion write {client-slug}-gtm/result.json {status, client_slug, contacts, with_signals,
  deck_path, csv_path, assumptions[], sanitize_report{}} and print its absolute path as the last line.
EOF

USER_PROMPT="/gtm-pipeline:demo ${PROMPT}"
[[ -n "$REQUESTER_EMAIL" ]] && USER_PROMPT="${USER_PROMPT}
Requester email: ${REQUESTER_EMAIL}"
USER_PROMPT="${USER_PROMPT}
Scope: ${MAX_CONTACTS} contacts. ${SIGNAL_FLAG}"

cd "$WORKROOT"
exec claude -p "$USER_PROMPT" \
  --model "$MODEL" \
  --permission-mode "$PERMISSION_MODE" \
  --append-system-prompt "$SYS"
