#!/usr/bin/env bash
# Resolve GTM_ENV_PATH so GTM pipeline skills find the user's .env on ANY machine.
#
# Why this exists: GTM_ENV_PATH is documented in _shared/local.md, but a doc line is
# not a shell variable — a fresh shell has it unset, so `"$GTM_ENV_PATH"` expands to
# empty and `grep KEY "$GTM_ENV_PATH"` reads nothing. This script fills the gap.
#
# Precedence:
#   1. An already-exported $GTM_ENV_PATH (CI / power users who set it in their profile)
#   2. The GTM_ENV_PATH= line in _shared/local.md (the documented setup step)
#   3. Fallback: $HOME/.env.gtm
#
# Usage (source it, then inject the keys you need):
#   source "$HOME/.claude/skills/gtm-pipeline/_shared/resolve_env.sh"
#   export $(grep -E '^(PARALLEL_API_KEY|OPENROUTER_API_KEY)=' "$GTM_ENV_PATH" | xargs) && python3 script.py

_gtm_local="$HOME/.claude/skills/gtm-pipeline/_shared/local.md"
if [ -z "${GTM_ENV_PATH:-}" ] && [ -f "$_gtm_local" ]; then
  GTM_ENV_PATH="$(grep -hoE '^GTM_ENV_PATH=.*' "$_gtm_local" | head -1 | cut -d= -f2- \
    | sed -e 's/^[[:space:]"]*//' -e 's/[[:space:]"]*$//')"
fi
: "${GTM_ENV_PATH:=$HOME/.env.gtm}"
export GTM_ENV_PATH
unset _gtm_local

if [ ! -f "$GTM_ENV_PATH" ]; then
  echo "warning: resolved GTM_ENV_PATH does not exist: $GTM_ENV_PATH" >&2
  echo "  set GTM_ENV_PATH in ~/.claude/skills/gtm-pipeline/_shared/local.md (see local.md.example)" >&2
fi
