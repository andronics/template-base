# 0004: App token minting

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Approved (2026-11-03)
Date: 2026-11-03
Authors: Stephen Cox

## Context

The template repositories and their projects mint GitHub App tokens in nine places, each a near copy of
`actions/create-github-app-token` v3.3.0 gated on a repository variable: Courier in template-base's
`pin-bumps.yml` and in projects' `template-update.yml`, Tagwarden in every `release-please.yml`, in
template-python's release and tag-check workflows and in template-typescript's release, and Scout in
template-obsidian's `obsidian-brain-pull.yml`. They differ where they shouldn't:

- **Scope.** Only three set `owner:`, and only Courier's and Scout's list `permission-*`, so Tagwarden's
  tokens carry every permission its App has.
- **Fallback.** Courier has none (`pin-bumps.yml` prints a notice, `template-update.yml` opens a "run
  locally" issue); Tagwarden and Scout fall back to `GITHUB_TOKEN`. Nothing says which is intended.
- **Secret names are named after a job, not a role.** `PIN_BUMP_APP_*` is Courier's, and also Ansible's,
  which bumps no pins; `RELEASE_APP_*` is Tagwarden's and Stardate's; Scout has `SCOUT_APP_*`. The names are
  literal in rendered workflows, with no Copier question.

The template-actors design (in the brain vault, "Template Actors", decided by Stephen on 2026-11-03) turns
actors into declared things: a manifest per actor, a secret naming convention, a fallback policy per actor
and one shared mint. It puts the mint here, because base's own `template-update.yml` needs it, as do
template-python, template-typescript and template-obsidian, and base must not depend on an overlay
([0001](0001-stacked-templates.md)). The rest, the **actor manifest** included, belongs to
**template-actors**, a feature overlay in its own repository (0001's rules: an `actors-*` prefix,
Template-owned markers, `.copier-answers.actors.yml`, a `checks.d` drop-in). This record is the part base
owns.

Constraints from [0002](0002-template-pin-bumps.md) and 0001: an App token is required for a PR whose CI
must run (a `GITHUB_TOKEN` PR starts no workflows); Courier has `workflows: write`; Tagwarden is the only
bypass actor on `v*` tags and never gets `workflows`; only the release App creates `v*` tags.

## Decision

### One mint action

**`.github/actions/app-token/action.yml`**, a composite action at template-base's root (repository tooling,
not rendered), wraps `actions/create-github-app-token` (SHA-pinned, bumped by Renovate like every pin).

| Input | Meaning |
|---|---|
| `role` | The role's secret prefix (`UPDATE`, `RELEASE`, `BRAIN_PULL`), for messages |
| `client-id`, `private-key` | The role's pair: `vars.<ROLE>_APP_CLIENT_ID`, `secrets.<ROLE>_APP_PRIVATE_KEY` |
| `legacy-client-id`, `legacy-private-key` | The legacy pair, read only when the role's pair is incomplete (the shim, below) |
| `owner` | The installation's owner; default `github.repository_owner`, and always passed explicitly by our callers |
| `repositories` | Empty: the current repository only. `*`: every repository the installation can see. Else a list; required when `owner` isn't the repository's owner |
| `permission-*` | Passed through (the repository permissions: `contents`, `pull-requests`, `workflows`, `issues`, …). At least one is required: a token never gets all of an App's permissions |
| `fallback` | `required` or `github-token` (below) |

| Output | Meaning |
|---|---|
| `token` | The token, or empty |
| `source` | `app`, `legacy-app`, `github-token` or `none` |
| `can-push-workflows` | `true` only for an App token minted with `permission-workflows: write` |

A complete role pair wins, else a complete legacy pair (with a warning to rename it), else no App. A
half-set pair is a warning and isn't used. A configured App that fails to mint fails the job: it never
quietly falls back. Composite actions can't read `secrets` or `vars`, so the caller passes both pairs.

### Secrets are named by role

A workflow fills a **role**; which actor fills it differs by owner (Courier or Ansible, Tagwarden or
Stardate), and the template-actors manifest maps actor to role. So:

| Role | Variable and secret | Replaces | Filled by (today) |
|---|---|---|---|
| update | `UPDATE_APP_CLIENT_ID`, `UPDATE_APP_PRIVATE_KEY` | `PIN_BUMP_APP_*` | Courier (andronics), Ansible (metalayerlab) |
| release | `RELEASE_APP_CLIENT_ID`, `RELEASE_APP_PRIVATE_KEY` | unchanged | Tagwarden (andronics), Stardate (metalayerlab) |
| brain pull | `BRAIN_PULL_APP_CLIENT_ID`, `BRAIN_PULL_APP_PRIVATE_KEY` | `SCOUT_APP_*` | Scout |

**One App may serve several actors** (Chronicler runs on Tagwarden's App): a role's secrets name an App,
and the manifest says which App each actor uses. Nothing here assumes one App per actor or per role.

**The legacy names keep working for one release cycle, through the shim, then they are removed.** Concretely:
the shim ships in the template-base minor release that carries this record (and in each overlay's release
that adopts it). The legacy names are removed in **template-base's next major release after every template
repository and every project has switched**: the role-named variable and secret set, the legacy ones
deleted, and a base release with this record taken through `template-update.yml`. The action's "legacy
secret names" warning in run logs is how to find who hasn't. Removing them is a `feat!`: a project that
still has only the legacy names would lose its App. TODO.md tracks it.

### Fallback policy, declared per actor

Every caller says which:

- **`required`**: no App, no token. The action prints a notice and returns `source: none`, and the caller
  skips its work (or fails, if skipping would hide a problem). Never `GITHUB_TOKEN`: its PRs run no CI.
  Courier's pin bumps.
- **`github-token`**: `GITHUB_TOKEN`, accepting what that means: CI doesn't run on its PRs, and it can't push
  a change to `.github/workflows/` (an update that needs to becomes an issue). Tagwarden's release PRs, as
  today; Scout's brain pull.

The template-actors manifest declares the policy per actor; the workflow passes it to the action.

### Least privilege

Every mint passes `owner:` and explicit `permission-*`. The release role never gets `workflows`
([0002](0002-template-pin-bumps.md)): it may move `v*` tags, so it stays narrow. The update role has
`contents`, `pull-requests` and `workflows` write.

### Who calls it, and how

- **template-base's own workflows** use the local path, `./.github/actions/app-token`, after a checkout.
  The action only exists at a released SHA after this merges (release-please tags it), so a pinned remote
  reference can't be written in the PR that adds it. `release-please.yml` checks out its own commit;
  `pin-bumps.yml`, which overlays call at a pinned SHA, checks out `job.workflow_repository` at
  `job.workflow_sha`, the called workflow's commit, not the caller's (verified on 2026-11-03 with a
  cross-commit reusable call). actionlint 1.7.12 doesn't know those two properties yet:
  `.github/actionlint.yaml` ignores that one message in that one file.
  - `pin-bumps.yml`: the update role, `required`, `contents`, `pull-requests` and `workflows` write.
  - `release-please.yml`: the release role, `github-token`, `contents`, `pull-requests` and `issues` write.
- **The overlays' rendered workflows** (release, tag-check, brain pull; their own PRs) call it remotely:
  `uses: andronics/template-base/.github/actions/app-token@<SHA> # vX.Y.Z`. template-base is public, so any
  repository may call it, in andronics or metalayerlab, public or private. Renovate's `github-actions`
  manager bumps that pin in the template sources like any other (0002), and projects' Dependabot in the
  rendered output.
- **base's own rendered workflows don't call it.** They render the same steps from one Jinja macro,
  `includes/github/app-token.yml.jinja` (outside `template/`, imported, never a file in projects), which
  holds the shim expressions and the pinned `create-github-app-token`. Calling the action remotely from
  base's own `template/` would pin template-base inside template-base: Renovate would bump that pin after
  every base release, as a `fix(deps)` that cuts the next release, which Renovate bumps the week after,
  forever. The rendered steps are plain `create-github-app-token` steps that only `vars` gate (secrets can't
  appear in `if:`), so the role pair is chosen by its variable, and the key follows its client ID.
  - `template-update.yml`: the update role (legacy `PIN_BUMP_APP_*`) with `contents`, `pull-requests` and
    `workflows` write; else the release role with `contents` and `pull-requests` write; else
    `GITHUB_TOKEN`. Unchanged otherwise: only the update role's token can push a change to
    `.github/workflows/`, so with the others such an update opens the "run locally" issue, decided before
    any push. Both App tokens cover the owner's whole installation, as before, so they can read a private
    template.

## Alternatives considered

- **Actor-keyed names** (`COURIER_APP_*`, …). Every rendered workflow would need a per-owner Copier
  answer, since the actor filling a role differs by owner. *Rejected* (Stephen, 2026-11-03).
- **One fallback for all actors.** Courier's pin bumps are useless with `GITHUB_TOKEN` (no CI, can't merge)
  while Tagwarden's release PRs work with it, merely without CI. *Rejected* for a per-actor policy.
- **A reusable workflow instead of a composite action.** A job can't both call a reusable workflow and run
  steps, and every caller mints mid-job. *Rejected*.
- **Rendering the action into projects** (`template/.github/actions/…`, called by local path). No remote
  fetch and versioned with the base a project is on, but every caller must check out first, the action
  would live twice in this repository, and overlays would depend on a base-rendered file for a mint step.
  *Rejected* for now in favour of the remote call (open question 1).
- **The remote action from base's own rendered workflows.** The Renovate self-bump loop above. *Rejected*
  for the rendered macro.
- **Removing the legacy names with this record.** Every project and template repository with only the
  legacy names would lose its App on the next update. *Rejected* for the one-cycle shim.

## Consequences

- **Rollout (not in this PR):** set `UPDATE_APP_*` (and, with template-obsidian, `BRAIN_PULL_APP_*`) in each
  repository and organisation beside the legacy names, then delete the legacy ones; also the stale
  organisation-level `RELEASE_APP_*` on metalayerlab that point at a deleted App. Nothing changes until a
  variable is set: the shim reads today's names.
- **The overlays** switch their mints to the remote action, each in its own PR, once a base release carries
  it: template-python (release, tag-check), template-typescript (release), template-obsidian (brain pull,
  `BRAIN_PULL_APP_*`, its 0001 fallback to `GITHUB_TOKEN` becoming `fallback: github-token`), and each
  overlay's `release-please.yml`.
- **Projects** get the new names in `template-update.yml` with the next base release; their PIN_BUMP
  variable and secret keep working until the major that removes them.
- **Release:** `template/` changes, so this is a `feat:` and a minor release. Not breaking: the legacy names
  still work.
- **Renovate:** the preset's `github-actions` manager also reads `includes/github/**`, so the macro's pin
  moves with the action's (`action.yml` files are in the manager's defaults).
- **Tests:** `tests/test_app_token.py` runs the action's two shell steps (pair choice, scope, refusals,
  outputs) and checks every permission input reaches both mints, one pin for the action and the macro, and
  no workflow minting directly. `test_pin_bumps.py` and `test_base.py` check the callers' roles, names,
  permissions and fallbacks.
- **Rollback:** revert the PR; the legacy names were never removed.

## Open questions

1. **Overlays: the remote action, or the action rendered into projects?** Recommendation: **remote**, as
   above. It is what the template-actors design assumed, and the overlays' template repos already pin
   template-base (`pin-bumps.yml`). The cost: every template-base release becomes a Renovate bump in every
   overlay, a `fix(deps)` and so a patch release there. If that's too noisy, a preset rule can bump
   `andronics/template-base` monthly. Revisit rendering the action if that noise or a remote fetch at run
   time becomes a problem.
