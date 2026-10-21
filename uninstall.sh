#!/usr/bin/env bash
# uninstall.sh — Remove the gtm-pipeline plugin and any symlinks from older versions.
set -euo pipefail

OLD_DST="$HOME/.claude/skills"

if command -v claude >/dev/null 2>&1; then
  claude plugin uninstall gtm-pipeline@keinsaas-gtm || true
fi

if [[ -d "$OLD_DST" ]]; then
  for link in "$OLD_DST"/gtm-*; do
    [[ -L "$link" ]] || continue
    rm "$link"
    echo "  removed old symlink $(basename "$link")"
  done
fi

echo "Done. Your ~/.env.gtm is untouched."
