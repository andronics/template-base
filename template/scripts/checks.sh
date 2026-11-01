#!/bin/sh
# Template-owned: template-base. The Definition of done's checks: every template's
# scripts/checks.d/*.sh, in name order (00-base first), stopping at the first failure.
# CI's `checks` job and AGENTS.md run this. A template adds checks by adding a file.
set -eu
cd "$(dirname "$0")/.."

ran=0
for check in scripts/checks.d/*.sh; do
    [ -e "$check" ] || continue
    sh "$check"
    ran=$((ran + 1))
done
[ "$ran" -gt 0 ] || { echo "error: scripts/checks.d/ has no checks"; exit 1; }
