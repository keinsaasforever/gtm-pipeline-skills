#!/usr/bin/env bash
# Resolve GTM_ENV_PATH so the skills' scripts find the user's API keys on any machine.
#
# Precedence:
#   1. An already-exported $GTM_ENV_PATH (set it in your shell profile to use another file)
#   2. Fallback: $HOME/.env.gtm
#
# Usage (source it, then inject only the keys a command needs):
#   source "${CLAUDE_PLUGIN_ROOT}/shared/resolve_env.sh"
#   while IFS= read -r line; do export "$line"; done < <(grep -E '^(PARALLEL_API_KEY|FIRECRAWL_API_KEY)=' "$GTM_ENV_PATH") && python3 script.py

: "${GTM_ENV_PATH:=$HOME/.env.gtm}"
export GTM_ENV_PATH

if [ ! -f "$GTM_ENV_PATH" ]; then
  echo "warning: no env file at $GTM_ENV_PATH" >&2
  echo "  create it from .env.example in the plugin, or export GTM_ENV_PATH to point at yours" >&2
fi
