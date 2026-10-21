#!/usr/bin/env bash
# install.sh — Install the gtm-pipeline plugin into Claude Code from this checkout.
#
# The skills ship as a Claude Code plugin now. Most people don't need this script:
#   claude plugin marketplace add keinsaasforever/gtm-pipeline-skills
#   claude plugin install gtm-pipeline@keinsaas-gtm
# In claude.ai or Cowork: Customize > Plugins > add the GitHub repository.
#
# This script installs from the local checkout instead (for contributors), and removes
# the symlinks that earlier versions created in ~/.claude/skills/.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLD_DST="$HOME/.claude/skills"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "GTM Pipeline — Install (plugin)"
echo ""

# Earlier versions symlinked skills/gtm-* into ~/.claude/skills/. Those would load
# next to the plugin as duplicates, so remove them (symlinks only).
if [[ -d "$OLD_DST" ]]; then
  for link in "$OLD_DST"/gtm-*; do
    [[ -L "$link" ]] || continue
    rm "$link"
    echo -e "${YELLOW}  removed${NC} old symlink $(basename "$link")"
  done
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "Claude Code CLI not found. Install it, then run this script again." >&2
  exit 1
fi

claude plugin marketplace add "$REPO_DIR"
claude plugin install gtm-pipeline@keinsaas-gtm

echo ""
echo -e "${GREEN}Done.${NC} Start Claude Code and run /gtm-pipeline:setup."
echo "API keys go in ~/.env.gtm (or export GTM_ENV_PATH). See .env.example."
