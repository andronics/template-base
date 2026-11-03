# 0007: gitleaks scans a PR's own commits, and full history nightly

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Approved (2026-11-03, approved by the brain coordinator for Stephen)
Date: 2026-11-03
Authors: Stephen Cox

## Context

Every project's `secrets` job in `base-ci.yml` (template-owned, rendered into every project whatever its
stack) checks out with `fetch-depth: 0` and runs `scripts/check-docs-secrets.sh secrets`. The script runs
gitleaks (v8.30.1, in Docker) as `gitleaks git --redact … --config .gitleaks.toml .` with no `--log-opts`,
so it scans every commit reachable from the checkout. The job runs on a pull request to `main`, on a push
to `main` and on `workflow_dispatch`, and `ci` (the one required check) needs it. Run locally, the script
scans the same way.

So every PR rescans the whole history:

- **A finding in an old commit fails every PR,** whatever the PR changed. The PR's author can't fix it in
  the PR: the fix is an allow-list entry (0006) or a history rewrite, and until then nothing merges. The
  red check also says nothing about whether the PR's own commits are clean.
- **The cost grows with the history.** A full clone and a scan of every commit on every PR, and on every
  push to a PR, for a check whose answer for the old commits hasn't changed since the last run.
- A secret in history still matters: a rule added or tightened in a gitleaks bump, or a commit that
  reached `main` without this check, can turn up a finding in commits no PR touches any more. Something
  must still scan all of it.

## Decision

- **On a pull request,** the `secrets` job scans only the PR's own commits: those reachable from the PR's
  head and not from its base (`github.event.pull_request.base.sha..github.event.pull_request.head.sha`).
  `ci` still needs the job, so a secret a PR adds still blocks it.
- **Nightly,** a scheduled run scans the full history of the default branch, as the job does today. A
  finding fails that run and opens an issue in the project (or updates the open one), labelled
  `secret-scan`, linking the run. The issue never quotes the finding: the log is redacted (`--redact`) and
  the issue says only the rule, the file and the commit.
- **Push to `main`, `workflow_dispatch` and a local run** keep the full-history scan: they are not on a
  PR's critical path, and a local run should match what CI can find.
- `scripts/check-docs-secrets.sh` stays the one place the gitleaks image and arguments live, so a local
  run of a range matches CI's.

## Alternatives considered

- **Full history on every PR (today):** a finding in an old commit blocks every PR, by authors who can't
  fix it there, and the scan's cost grows with the history. *Rejected.*
- **PR commits only, no full scan:** fast, but a finding in history that a new or tightened rule turns
  up, or that reached `main` without the check, is never seen again. *Rejected.*
- **PR commits plus a nightly full-history scan:** a PR is judged on what it adds, and history is still
  scanned every day. *Chosen.*

## Consequences

- **Speed:** a PR's secret scan reads a handful of commits instead of the whole history. The checkout
  still needs both ends of the range, so it keeps `fetch-depth: 0` (or fetches the base explicitly); the
  saving is in the scan, and in not failing on findings the PR didn't make.
- **What a nightly finding means:** a secret, or a false positive, in a commit already on the default
  branch. The PR checks stay green, so it blocks nothing; the issue is the signal. A real secret is
  already exposed to anyone who can read the repository: rotate it first, then allow-list or rewrite
  history. A false positive goes in `.gitleaks.toml`'s allow-list (0006).
- **Who sees it:** the issue, in the project, where its maintainers and anyone watching issues see it.
  GitHub mails a scheduled run's failure only to the user who last changed its cron line; in a project
  that is whoever committed the template update, often the update App, so the mail alone would reach
  nobody. A public repository with no activity for 60 days has its scheduled workflows turned off by
  GitHub; the PR and push scans still run.
- **Every project gets it:** the change is to template-owned files (`base-ci.yml`, the script, and a new
  workflow), so it reaches every project, whatever its stack, through its next base update PR, as a
  `feat:` (a new workflow and a changed check). If the new workflow is added under
  `.github/workflows/`, a project whose update runs without the update role's App gets an issue asking
  for a local `copier update` instead of a PR, as for any workflow change (template-update.yml).
- A PR that adds a secret and removes it in a later commit of the same PR still fails: the range covers
  every commit in it, not only the final diff. That is intended, since the squash leaves the commit in the
  PR's history on GitHub.
- Rollback: revert; every PR scans full history again.

### Implementation outline (the follow-up PR)

1. `scripts/check-docs-secrets.sh`: an optional range (an environment variable such as
   `GITLEAKS_LOG_OPTS`, or a second argument) passed to gitleaks as `--log-opts`; unset, it scans the
   full history as now.
2. `base-ci.yml.jinja`: on `pull_request`, the `secrets` job passes the PR's `base.sha..head.sha`; on other
   events, nothing.
3. A new template-owned workflow (e.g. `base-secret-history.yml`): `schedule` once a night and
   `workflow_dispatch`, `fetch-depth: 0`, the script with no range, `issues: write`, and on failure
   opens or updates the `secret-scan` issue with `GITHUB_TOKEN`, creating the label if it's missing.
4. `tests/`: the rendered workflows (actionlint), the script's range handling, and a render with each
   overlay; `template/AGENTS.md.jinja` and the script's comments say a PR scans its own commits.
5. Mark this record Implemented and update its index line.

## Open questions

- None: the scope is decided. The follow-up PR's review settles the names (the variable, the workflow, the
  label) and the hour.
