# 0006: The project's gitleaks allow-list extends base's

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Implemented
Date: 2026-11-03
Authors: Stephen Cox

## Context

Every project's secret scan (`scripts/check-docs-secrets.sh`, CI's `secrets` job, the stack's pre-commit
hook) reads `.gitleaks.toml`. Base rendered it as a template-owned file: gitleaks' default rules and a
lock-file allow-list. Projects need their own false positives too: the brain adds a regex for RFC 6455's
sample `Sec-WebSocket-Key`. Its entry lives in the template-owned file and survives updates only because
Copier's 3-way merge happens not to touch those lines. A base change near them conflicts, and nothing says
where a project's entry belongs.

gitleaks (v8.30.1, pinned in the script) loads one config, which may `[extend]` either the built-in
defaults (`useDefault = true`) or another file (`path = "…"`), not both (an error), and follows extends
two levels deep. An extended file's global allow-lists are appended to the extending file's, so every
allow-list from every level applies; `[allowlist]` (the old form) and `[[allowlists]]` may differ between
files. `path` is read relative to the working directory: the repository root for the script, the hook
and a local `gitleaks git`.

## Decision

- **`.gitleaks.base.toml`**, template-owned: `[extend] useDefault = true` and base's `[[allowlists]]`
  (the lock files). Base's entries change here and reach projects by update.
- **`.gitleaks.toml`**, the project's: listed in `_skip_if_exists`, seeded with
  `[extend] path = ".gitleaks.base.toml"` and a commented `[[allowlists]]` example. It stays the entry
  point, so the script, CI, the pre-commit hook and a bare `gitleaks git` (which finds `.gitleaks.toml`
  itself) need no change. The chain is `.gitleaks.toml` → `.gitleaks.base.toml` → the defaults: the
  two levels gitleaks allows.
- **`scripts/base-contract.py`** (run by `00-base.sh`) fails when `.gitleaks.toml` is missing, isn't
  valid TOML, or its `[extend] path` isn't `.gitleaks.base.toml`, and says how to fix it. Without that
  line the project would silently lose base's allow-list and, if it also dropped `useDefault`, the
  default rules.

## Alternatives considered

- **Base's `.gitleaks.toml` extends a project-owned `.gitleaks.project.toml`:** base can't also say
  `useDefault`, so the default rules would have to come from the project's file. And an existing project's
  entries sit in the file base still owns: the update merges around them or conflicts, and they need moving
  by hand. *Rejected.*
- **A seeded, empty project section in the template-owned file:** Copier's merge is what we have today;
  it still conflicts when base changes nearby lines. *Rejected.*
- **Two `--config` files in the script:** gitleaks takes one. *Rejected.*
- **Warn instead of fail when `.gitleaks.toml` doesn't extend base:** a warning in a weekly update PR is
  easy to merge past, and the project then never gets base's allow-list changes. *Rejected.*

## Consequences

- A project's allow-list entries never conflict with, or are lost to, a base update. Base's never
  reach a project's file.
- **Existing projects:** the update leaves `.gitleaks.toml` exactly as it was (Copier skips it, custom
  entries included) and adds `.gitleaks.base.toml`. The PR's `ci` then fails in `00-base.sh`, naming the
  fix: under `[extend]`, replace `useDefault = true` with `path = ".gitleaks.base.toml"`. Keep the
  project's entries; the lock-file entry may go (base has it), and the old `[allowlist]` form still works.
  One reviewed line in the update PR; `tests/test_update.py` replays it with the brain's entry.
- Rollback: revert; a project's `.gitleaks.toml` with `path` would then need `useDefault = true` again.

## Open questions

- None.
