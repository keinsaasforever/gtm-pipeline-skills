#!/usr/bin/env bash
# Copy shared/revenue.md into each revenue-intelligence skill as references/revenue.md.
#
# Why copies: in claude.ai chat and ChatGPT a skill only sees its own folder, so a
# rule file outside it can't be read there. shared/revenue.md is the one to edit;
# run this afterwards. `--check` exits 1 if any copy has drifted (use it in CI).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/shared/revenue.md"
SKILLS=(revenue-setup call-transcripts meeting-prep post-call live-assist daily-plan deal-review)

status=0
for s in "${SKILLS[@]}"; do
  dst="$ROOT/skills/$s/references/revenue.md"
  if [[ "${1:-}" == "--check" ]]; then
    if ! cmp -s "$SRC" "$dst"; then
      echo "out of date: skills/$s/references/revenue.md (run scripts/sync-shared.sh)" >&2
      status=1
    fi
  else
    mkdir -p "$(dirname "$dst")"
    cp "$SRC" "$dst"
  fi
done
exit $status
