#!/usr/bin/env bash
# Scan for secrets: what CI's Secret scan job runs, with the same pinned version and
# arguments (it calls this script). Uses gitleaks 8.30.1 when it is installed (on PATH or in
# the runner's tools folder), else the pinned Docker image. A stack that lints Markdown does it in its own
# scripts/checks.d/ drop-in (template-base decision 0001).
# Template-owned: template-base. With neither the tool nor Docker it skips locally, but is an error in CI.
# Quiet on a pass: one summary line; a failing tool's output in full (template-base decision 0001).
#
#   scripts/check-docs-secrets.sh            # gitleaks
set -euo pipefail
cd "$(dirname "$0")/.."

checks="${1:-secrets}"

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

GITLEAKS_VERSION=8.30.1
gitleaks_cmd=()
if bin="$(find_tool gitleaks "$GITLEAKS_VERSION" version)"; then
    gitleaks_cmd=("$bin")
elif command -v docker > /dev/null 2>&1; then
    gitleaks_cmd=(docker run --rm -v "$PWD:/repo" -w /repo "ghcr.io/gitleaks/gitleaks:v$GITLEAKS_VERSION")
else
    if [ "${CI:-}" = "true" ]; then
        echo "error: neither gitleaks $GITLEAKS_VERSION nor docker is installed"
        exit 1
    fi
    echo "skip: neither gitleaks $GITLEAKS_VERSION nor docker is installed"
    exit 0
fi

status=0
passed=""

# Runs a check, printing its output only if it fails.
run() {
    local name="$1" out
    shift
    if out="$("$@" 2>&1)"; then
        passed="$passed $name"
    else
        printf 'error: %s\n%s\n' "$name" "$out"
        status=1
    fi
}

for check in $checks; do
    case "$check" in
        secrets)
            # Scans commits, as CI does. Allow-list false positives in .gitleaks.toml.
            run gitleaks "${gitleaks_cmd[@]}" \
                git --redact --verbose --no-banner --no-color --config .gitleaks.toml .
            ;;
        *)
            echo "usage: $0 [secrets]"
            exit 2
            ;;
    esac
done
if [ "$status" -eq 0 ]; then
    echo "check-docs-secrets OK:$passed"
fi
exit "$status"
