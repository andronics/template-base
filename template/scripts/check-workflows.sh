#!/usr/bin/env bash
# Template-owned: template-base. Lint the workflows: what CI's Workflow lint job runs (it calls
# this script). Uses actionlint 1.7.12 when it is installed (on PATH or in the runner's tools
# folder; it runs shellcheck on `run:` blocks when that is on PATH), else the pinned Docker
# image. With neither it skips locally, but is an error in CI.
#
#   scripts/check-workflows.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# The tool itself, pinned by version: on PATH first, then in the runner's tools folder
# ($CI_TOOLS_BIN, default the desktop runner's), and used only when it reports exactly the
# pinned version; otherwise the pinned Docker image below (A42: binary first, Docker as fallback).
find_tool() {
    local name="$1" want="$2" flag="$3" cand
    for cand in "$(command -v "$name" 2> /dev/null || true)" \
        "${CI_TOOLS_BIN-${HOME:-/nonexistent}/.local/share/actions-runner/tools/bin}/$name"; do
        [ -n "$cand" ] && [ -x "$cand" ] || continue
        if "$cand" "$flag" 2> /dev/null | head -n 1 | grep -Eq "(^|[ v])${want//./\\.}( |$)"; then
            echo "$cand"
            return 0
        fi
    done
    return 1
}

ACTIONLINT_VERSION=1.7.12
if bin="$(find_tool actionlint "$ACTIONLINT_VERSION" -version)"; then
    exec "$bin" -color
elif command -v docker > /dev/null 2>&1; then
    exec docker run --rm -v "$PWD:/repo" -w /repo "rhysd/actionlint:$ACTIONLINT_VERSION" -color
fi
if [ "${CI:-}" = "true" ]; then
    echo "error: neither actionlint $ACTIONLINT_VERSION nor docker is installed"
    exit 1
fi
echo "skip: neither actionlint $ACTIONLINT_VERSION nor docker is installed"
