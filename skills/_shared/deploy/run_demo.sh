#!/usr/bin/env bash
# run_demo.sh — headless entrypoint for the GTM demo skill.
#
# A thin, orchestrator-agnostic wrapper. A webhook layer (n8n, a small server, etc.) calls this
# with the website form's prompt; it invokes /gtm-pipeline:demo-headless via the Claude Code CLI (`claude -p`)
# and the skill writes {client-slug}-gtm/result.json. `claude -p` is the OUTER entrypoint, so the
# agent does all LLM work itself — no nested `claude -p`, no third-party LLM on the default path.
#
# Usage:
#   run_demo.sh --prompt "we sell X to Y..." [--requester-email a@b.com] [--no-signals]
#               [--max-contacts 20] [--segments "contractors; developers"]
#   echo '{"prompt":"...","requester_email":"a@b.com","with_signals":false}' | run_demo.sh --json
#
# Leave out an option and the skill's own default applies (10 contacts per segment, 2 segments,
# 30 max; signals on). The skill clamps max_contacts to 30 and keeps its budget cap either way.
#
# Requires: gtm-pipeline skills installed (./install.sh) and the `claude` CLI on PATH.
# See deploy/README.md for the full input/output contract and permission notes.
set -euo pipefail

PERMISSION_MODE="${CLAUDE_PERMISSION_MODE:-acceptEdits}"   # see README: headless servers may need bypassPermissions
MODEL="${CLAUDE_DEMO_MODEL:-sonnet}"                        # orchestration model (Opus used for extraction/scoring/messages)
WORKROOT="${GTM_WORKROOT:-$PWD}"                            # where {client-slug}-gtm/ is created
PROMPT="" ; REQUESTER_EMAIL="" ; WITH_SIGNALS="" ; MAX_CONTACTS="" ; SEGMENTS="" ; JSON_MODE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt)          PROMPT="$2"; shift 2;;
    --requester-email) REQUESTER_EMAIL="$2"; shift 2;;
    --with-signals)    WITH_SIGNALS="on"; shift;;
    --no-signals)      WITH_SIGNALS="off"; shift;;
    --max-contacts)    MAX_CONTACTS="$2"; shift 2;;
    --segments)        SEGMENTS="$2"; shift 2;;
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
ws = d.get("with_signals")
print("WITH_SIGNALS=%s"    % ("" if ws is None else "on" if ws else "off"))
print("MAX_CONTACTS=%s"    % shlex.quote(str(d.get("max_contacts") or "")))
print("SEGMENTS=%s"        % shlex.quote("; ".join(map(str, d.get("segments") or []))))
')"
fi

[[ -z "$PROMPT" ]] && { echo "ERROR: no prompt provided (--prompt or --json)" >&2; exit 2; }

read -r -d '' SYS <<'EOF' || true
Headless demo run (no human in the loop). Never ask questions: follow the gtm-demo-headless skill's
defaults and record every assumption in context/icp.md. Write result.json exactly per the skill's
"Output contract" section, and print its absolute path as the last line.
EOF

USER_PROMPT="/gtm-pipeline:demo-headless ${PROMPT}"
[[ -n "$REQUESTER_EMAIL" ]] && USER_PROMPT+=$'\n'"Requester email: ${REQUESTER_EMAIL}"
[[ -n "$MAX_CONTACTS" ]]    && USER_PROMPT+=$'\n'"max_contacts: ${MAX_CONTACTS}"
[[ -n "$SEGMENTS" ]]        && USER_PROMPT+=$'\n'"segments: ${SEGMENTS}"
[[ -n "$WITH_SIGNALS" ]]    && USER_PROMPT+=$'\n'"with_signals: ${WITH_SIGNALS}"

cd "$WORKROOT"
exec claude -p "$USER_PROMPT" \
  --model "$MODEL" \
  --permission-mode "$PERMISSION_MODE" \
  --append-system-prompt "$SYS"
