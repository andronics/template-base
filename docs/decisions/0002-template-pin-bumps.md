# 0002: Automatic pin bumps for template sources

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Accepted (2026-11-02)
Date: 2026-11-02
Authors: Stephen Cox

## Context

Issue #20. Every action in a template is pinned to a commit SHA with its version in a trailing comment
(AGENTS.md), and the tools the checks run are pinned by hand. Nothing ever bumps those pins in the template
repositories:

- **Dependabot never sees them.** A project's Dependabot reads the rendered `.github/workflows/*.yml`. A
  template's sources are under `template/` (and template-python's `includes/`), mostly named `*.jinja`,
  which no Dependabot ecosystem parses. And none of the five template repositories has a
  `.github/dependabot.yml` of its own, so even their own CI (`template-ci.yml`, `release-please.yml`,
  `pr-title.yml`) is bumped by hand.
- **Projects move ahead of their templates.** Brain's Dependabot bumped `astral-sh/setup-uv` to v10.3.3
  (andronics/brain#14) in `base-ci.yml` and `template-update.yml`, template-owned files, while every
  template still pinned v10.3.2 (fixed by hand in #24 and template-python#3). Until the templates caught up,
  that bump was a project edit on a template-owned file: `copier update` carries it as a diff, a template
  change next to it makes a conflict, and `copier recopy --overwrite` (decision 0001's migration) drops it.
- **Hand-pinned tools repeat across repositories and drift.** On 2026-11-02:

  | Pin | Where |
  |---|---|
  | `rhysd/actionlint:1.7.12` | base's `base-ci.yml.jinja`; every template repo's `template-ci.yml`, tests and AGENTS.md |
  | `ghcr.io/gitleaks/gitleaks:v8.30.1` | base's `scripts/check-docs-secrets.sh` |
  | hadolint `v2.15.1` (release URL, Docker image) | python's and typescript's `stack-ci.yml.jinja` and tests; base's, python's, typescript's and container's `template-ci.yml` |
  | kubeconform `v0.8.0` (release URL) | the same `stack-ci.yml.jinja` and `template-ci.yml` files, while template-container's `tests/test_container.py` runs `ghcr.io/yannh/kubeconform:v0.7.0` |
  | `markdownlint-cli2:v0.24.0` | python's and typescript's `scripts/check-markdown.sh` |
  | `ghcr.io/astral-sh/uv:0.13.6`, base images | template-python's `includes/docker/*.Dockerfile.jinja`, and the other image templates |

  Projects' Dependabot bumps the image `FROM` lines too (the `docker` ecosystem in the stack's
  `dependabot.yml`), so those drift the same way. The `docker run` lines and release URLs it never bumps.

**What projects' Dependabot says today.** `.github/dependabot.yml` is a stack slot (decision 0001).
template-obsidian's, template-python's and template-typescript's all list `github-actions` at `/` (one
weekly group, `chore(deps)`), plus `uv` or `npm` and, with `container_image`, `docker`. None excludes a path,
so Dependabot bumps template-owned and project-owned workflows alike. base's contract requires only the
`github-actions` entry.

**Constraints.** Base never names an overlay inside `template/` or `copier.yml`; its own CI and tooling at
the repository root may (`template-ci.yml` already checks out all four). A PR opened with `GITHUB_TOKEN`
starts no workflows, so `ci` never reports and it can't merge. Only a GitHub App token opens PRs that run
CI (Tagwarden, the release App, here; template-python's 0002 relies on the same). Pushing a change to
a repository's own `.github/workflows/` needs the `workflows` permission, which Tagwarden doesn't have
(Courier, the planned template-update App, does). A bump in `template/` changes what projects get, so it's
a `fix:` and a patch release; a bump to a template repo's own CI is a `chore:`.

## Decision

**Renovate, self-hosted in each template repository's CI, reading the sources directly, with no render
step.** template-base owns the mechanism at its repository root, outside `template/`. Projects keep
Dependabot as it is.

### Why no render step

The pins are literal text in the sources: `uses: owner/repo@SHA # vX.Y.Z`, `image:vX.Y.Z`,
`.../releases/download/vX.Y.Z/...`. No pin is computed by Jinja, and none may be (below). So the updater
edits the source line it found, and rendering adds only a way to map a change in the output back to the
`.jinja` line, which is the hard part. Whether the bumped source still renders and passes is what the PR's
own Template CI already checks: it renders every variant and runs the checks.

### What template-base adds (repository root only)

- **`renovate/templates.json5`**, a shared preset every template repository extends:
  - `enabledManagers`: `github-actions`, `dockerfile` and `custom.regex` only. The template repos' own
    `uv.lock` and the projects' ecosystems stay out of scope (open question 5).
  - `github-actions` gets an extra `managerFilePatterns` entry, `template/**/.github/workflows/**`, and
    `dockerfile` gets `template/**/*Dockerfile*` and `includes/**/*Dockerfile*`, beside their defaults
    (the repo's own `.github/workflows/` and Dockerfiles). Narrower than first proposed (every `*.jinja`,
    `template/**/*.yml`, `includes/**`): the dry run (Findings) showed the same pins and none of the noise.
    Renovate's GitHub Actions extractor finds `uses:` lines line by line, so the Jinja around them doesn't
    stop it, and no `uses:` regex fallback is needed.
  - **Action inputs aren't bumped:** a `packageRules` entry disables `github-actions`' `uses-with`
    dependencies (`node-version`, `python-version` and the like), which it reads wherever the YAML parses.
    Those are choices, not pins.
  - **Custom regex managers** for the hand-pinned tools, in any file under `template/`, `includes/`,
    `tests/`, `scripts/`, `.github/workflows/` and `AGENTS.md`: Docker image references with a version tag
    (an allow-list of names: actionlint, gitleaks, hadolint, kubeconform, markdownlint-cli2, uv), and
    `https://github.com/OWNER/REPO/releases/download/vX.Y.Z/` URLs (`github-releases` datasource). Docker Hub
    images use the `docker` datasource. GHCR gives Renovate no release dates, so `minimumReleaseAge` would
    hold a GHCR image forever (seen in the implementation's dry run): gitleaks, kubeconform and uv are read
    from their GitHub releases instead, whose tags the images share. A GHCR base image in a `FROM` line
    would need the same treatment in its repository's `renovate.json`.
  - A fourth regex manager reads `renovate-version:` in `pin-bumps.yml` (an action input, so excluded
    above) from npm, so Renovate bumps itself; the tests validate the preset with that version.
  - SHA pins keep their `# vX.Y.Z` comment, which Renovate rewrites with the digest.
  - `minimumReleaseAge: "3 days"`: a hijacked release (tj-actions, 2025) is usually caught within that.
  - **Two groups per repository, per week:** files under `template/` and `includes/` →
    `fix(deps): bump template pins` (a patch release; projects get it); everything else →
    `chore(deps): bump repository pins` (no release). One tool pinned in both lands in both, in the same
    week, at the same version. Majors stay in the group (`separateMajorMinor: false`), so it's two PRs; a
    group with one update is titled after it (`fix(deps): bump astral-sh/setup-uv action to v10.3.4`).
  - `schedule: ["before 4am on sunday"]`, so a merged bump can be released before projects'
    `template-update.yml` runs on Monday 06:00 UTC. **No automerge**, no dependency dashboard issue.
- **`.github/workflows/pin-bumps.yml`**, triggered by `schedule` (Sunday 02:23 UTC), `workflow_dispatch`
  and `workflow_call`. It mints the App token (`actions/create-github-app-token`, with `contents`,
  `pull-requests` and `workflows` write) from `vars.PIN_BUMP_APP_CLIENT_ID` and
  `secrets.PIN_BUMP_APP_PRIVATE_KEY`, and runs `renovatebot/github-action` (SHA-pinned, Renovate at an
  exact version) against the calling repository (`RENOVATE_REPOSITORIES: ${{ github.repository }}`). A
  manual run lifts the schedule (`RENOVATE_FORCE`). **Without the App's variable** only a second job runs,
  which prints a notice that the App isn't configured and succeeds: it never falls back to `GITHUB_TOKEN`,
  whose PRs run no CI. So the workflow is inert until the App exists. It's a repository workflow, never
  rendered.
- **`renovate.json`**: `{"extends": ["local>andronics/template-base//renovate/templates.json5"]}`, so
  template-base's own sources and CI are bumped too.

### What each overlay repository adds

`renovate.json` (the same `extends`) and a caller, `.github/workflows/pin-bumps.yml`, weekly plus
`workflow_dispatch`, whose one job `uses: andronics/template-base/.github/workflows/pin-bumps.yml@SHA #
vX.Y.Z` with `secrets: inherit`; Renovate bumps that pin like any other, so the overlays follow base's
mechanism a week behind at most. Plus the App's variable and secret (`PIN_BUMP_APP_CLIENT_ID`,
`PIN_BUMP_APP_PRIVATE_KEY`). No
file under `template/` changes, so no release. A rule only an overlay needs (template-typescript's nginx
odd-minor rule, say) goes in its own `renovate.json`'s `packageRules`, never in the shared preset, which
names no overlay.

### Pins stay literal

Every pin stays written out where it's used. A version in a Jinja variable or a shared data file would hide
it from both bots and from actionlint (option 2, below).

### Projects

Unchanged: Dependabot keeps bumping everything in the project, template-owned workflows included, and
`.github/dependabot.yml` (the slot) and the contract don't change. Once the template carries the same bump,
the next `copier update` should merge the two identical changes cleanly (Copier reapplies the project's
diff with a three-way merge, and both sides made the same change; a test confirms it, below), and the
project's edit disappears. The window in which a project is ahead is a week, not
"until someone notices".

## Alternatives considered

- **(1) A scheduled render, then a pin updater on the output, then a PR rewriting the sources.**
  Dependabot doesn't help here: its CLI (`dependabot/cli`) runs outside GitHub but with the same parsers,
  so it still skips `.jinja`, and it prints a diff, not a PR. On the output, any updater works, but the PR has to change the source, and a rendered line maps back to a
  `.jinja` line only by search, per variant, which is what reading the source directly does without the
  render. *Rejected* for the render step; the tools, without it:
  - **`pinact`** reads `uses:` lines by regex, so `pinact run -u template/**/*.jinja` works on sources.
    It covers actions only: the image tags and release URLs need a second tool, and its PRs need a
    workflow of our own around it. *Rejected* for one tool covering both.
  - **`ratchet`** parses YAML, and `[% if %]` lines aren't YAML. *Rejected.*
  - **A script on the GitHub API** (tags and releases, rewrite in place). Small for actions, then grows
    datasources for GHCR, Docker Hub and npm, grouping, release-age and PR bookkeeping, which Renovate
    already has. *Rejected*; it stays the fallback if Renovate is refused (open question 3).
- **(2) Pins in one data file that the templates read** (`includes/pins.yml`, or `copier.yml`
  `_external_data`). `_external_data` reads files from the *destination* project, not the template, so it
  can't hold a template's pins; a Jinja include or `when: false` variables in `copier.yml` can. Either way,
  `uses: actions/checkout@[[ pins.checkout ]]` is invisible to actionlint and to every bot in the
  sources, and a bot is still needed for the data file. One file for all five repos can't work: overlays
  share no Jinja (decision 0001). *Rejected*: indirection with no saving.
- **(3) Projects' Dependabot ignores template-owned workflows; templates bump by hand on release.** By hand
  is what we have: v10.3.2 sat in five repos while brain was already on v10.3.3. Excluding template-owned
  paths also delays security fixes in projects until a template release and a template update. And the
  slot owner would have to list base's and every feature overlay's workflow names, since template-owned
  and project-owned workflows share `.github/workflows/`. *Rejected* for now (open question 4).
- **Dependabot in each template repository.** Fixes their own CI, but not `template/` (no `.jinja`, no
  `docker run` lines or release URLs), which is the issue. *Rejected*; Renovate covers both, and two bots in
  one repository would open duplicate PRs.
- **Mend's hosted Renovate App** instead of self-hosting. No workflow to keep, but a third-party App with
  write access to every template repository, outside the App and key set we manage. *Rejected* in favour
  of `renovatebot/github-action` with our App, as open question 2 asks.
- **The mechanism in `template/`, so projects get it too.** Projects already have Dependabot for what's in
  them; a second bot there duplicates its PRs. And template-python's 0002 rejected Renovate in projects for
  one git dependency. *Rejected*; templates only.

## Consequences

- **Each template repository** gets `renovate.json` and a caller workflow, and one or two PRs a week:
  `fix(deps): bump template pins` (merging it cuts a patch release through release-please) and
  `chore(deps): bump repository pins`. Every pin in the tables above moves on its own, so the kubeconform
  v0.7.0/v0.8.0 split in template-container closes with the first run.
- **Each project** gets nothing new: the template releases arrive through `template-update.yml` as today,
  with bumps it may already have. `tests/test_update.py` gains a case: a project that bumped a pin, updated
  to a template carrying the same bump, has no conflict and no diff left on that line.
- **Slots and contract:** no slot changes, and `base-contract.py` doesn't change. `dependabot.yml` keeps
  its one required entry.
- **Release:** the mechanism lives at template-base's root, so adding it is a `ci:` PR and no release, in
  every repository. Each later `fix(deps)` is a patch release. Nothing here is minor or major.
- **Context budget:** unchanged. `template/AGENTS.md.jinja` doesn't change. This repository's AGENTS.md
  gains one line, "Pins are bumped by Renovate (decision 0002): don't hand-bump one unless it's urgent",
  and so do the overlays'.
- **template-python's 0002 (tag-check):** separate and compatible. Tag-check bumps git-tag-pinned
  dependencies in *projects*. If its 0003 puts `interpose @ git+https://...@vX.Y.Z` into template-python's
  `pyproject.toml.jinja`, that pin is #20's problem again (projects' tag-check runs ahead of the
  template), and template-python's `renovate.json` adds a regex manager for that line (`github-tags`
  datasource). 0002's case against Renovate is about projects and stands.
- **The App:** the PRs need an App token, or their CI never runs. The workflow names the App by
  its variable and secret, as `release-please.yml` does, but has no `GITHUB_TOKEN` fallback. Bumping a
  template repo's own `.github/workflows/` needs the `workflows` permission; bumping `template/` may not
  (Findings). The App is Courier (open question 2), not Tagwarden.
- **Projects' `template-update.yml`** (issue #36) prefers the same App: with `PIN_BUMP_APP_CLIENT_ID` set
  in a project, it mints Courier's token with `contents`, `pull-requests` and `workflows` write; else the
  release App's, else `GITHUB_TOKEN`. Neither of those two may push a change to `.github/workflows/`
  (Tagwarden stays without `workflows`), so with them an update that changes a workflow opens the "run
  locally" issue instead of a PR, decided from the token before pushing. A push or PR that fails anyway
  opens the same issue, not a red job. So a project that wants workflow updates as PRs installs Courier and
  sets its variable and secret.
- **Scheduled workflows** stop after 60 days without activity in a public repository. A merged bump
  counts as activity, so this matters only for a repository that merges nothing for two months, as for
  `template-update.yml`: nothing new.
- **Migration:** one PR in template-base (the preset, `pin-bumps.yml`, `renovate.json`, the AGENTS.md
  line, the tests), then one per overlay (TODO.md). Create Courier, install it on all five; set the
  variable and secret in each. Close any open hand-bump PRs.
- **Tests:** `tests/test_pin_bumps.py` checks the App gating (no variable: only the notice job runs; no
  `GITHUB_TOKEN` anywhere) and runs `renovate-config-validator --strict` on the preset and `renovate.json`
  with the version the workflow runs (`-m npx`, which CI's `-m ''` includes). `tests/test_update.py` has
  the identical-bump case above. actionlint lints `pin-bumps.yml` with the other workflows.
- **Rollback:** delete the caller workflow in a repository. Nothing was rendered into projects.
- **TODO.md** gets "Decided against" lines for the render step, the pins data file and the hand bumps.

## Open questions (resolved 2026-11-02)

Stephen accepted every recommendation.

1. **Does Renovate's `github-actions` manager read `.jinja` workflow sources, including the files with
   `[% if %]` blocks, and rewrite the SHA and its comment?** Yes (Findings). No `uses:` regex fallback;
   the two managers are narrowed to the files they can read.
2. **Which App opens the PRs?** **Courier**, a new App with `workflows: write`, installed on the five
   template repositories: it brings changes in, so bumps fit its role, and Tagwarden (the release App, the
   tag ruleset's only bypass) stays narrow. Courier isn't created yet; until it is, `pin-bumps.yml` skips
   with a notice.
3. **Renovate at all, or a small script?** **Renovate**: it already does SHA-plus-comment pins, GHCR,
   Docker Hub and GitHub release datasources, grouping, release age and one PR per group, and its config
   is shared from template-base without naming an overlay.
4. **Should projects' `dependabot.yml` exclude template-owned workflows?** **Not now**: identical bumps
   merge cleanly (now a test), and excluding them delays security fixes by a template release. Revisit if
   `copier update` conflicts on pins after a month of weekly bumps; then the stack slot adds
   `exclude-paths` for `base-*.yml`, `template-update.yml`, `pr-title.yml`, `stack-ci.yml` and its own
   prefix, and a feature overlay's workflows need a contract entry, a minor release.
5. **Also let Renovate bump the template repos' own `uv.lock` (copier, pytest)?** **Yes, later**, in the
   `chore(deps)` group, as a follow-up once pins have run for a few weeks (TODO.md).
6. **Automerge?** **No**: every template change reaches every project, and CODEOWNERS already requires
   Stephen's review. A weekly grouped PR is one review.
7. **Action inputs (`node-version: '24'` → `'26'`, Findings)?** **Excluded**: a `packageRules` entry
   disables `depType: uses-with`.

## Findings (dry run 2026-11-03)

Open question 1, checked with Renovate 44.199.2 (`npx`; the `renovate/renovate` image of the same version
didn't start here), `--platform=local --dry-run=full`, `LOG_LEVEL=debug`, on scratch copies of
template-base (`d929eee`) and template-obsidian (`8c0cdc6`), plus template-python (`3a21b19`) because
neither has a Dockerfile source. The config was this record's preset as written: `managerFilePatterns`
`template/**/*.jinja`, `template/**/*.yml` and `includes/**` on `github-actions` and `dockerfile`, the two
regex managers, `minimumReleaseAge: "3 days"`, the two groups. Deliberately stale pins: `setup-uv` v10.3.2
(`07a047e`) in base's `base-ci.yml.jinja` and obsidian's `obsidian-brain-pull.yml` source, `checkout`
v7.0.0 *inside* base-ci's `[% if personal_data_guard %]` block, `actionlint:1.7.11`, and `uv:0.13.5` in
python's `builder.Dockerfile.jinja`.

- **`github-actions` reads every `.jinja` workflow source.** Every `uses: owner/repo@SHA # vX.Y.Z` line under
  `template/` was extracted: 13 in base (4 files), 7 in obsidian, 13 in python (3 files), the same count
  as a `grep`. That includes the files whose names are `[% if %]` blocks and the lines inside `[% if %]`.
  Three sources aren't valid YAML (`base-ci.yml.jinja` and `base-dependabot-automerge.yml` for their
  `[% if %]` lines, python's `stack-ci.yml.jinja`): Renovate logs `Does not match schema: Invalid YAML` at
  debug and keeps the `uses:` deps, which it finds line by line. It loses only what it reads from parsed
  YAML (`runs-on`, `container:`, `node-version`-style inputs), and none of those is pinned in those files.
  `[[ var ]]` in obsidian's file is inside strings, so it parses.
- **Proposed updates:** `setup-uv` v10.3.2 → v10.3.3 (both repos), `checkout` v7.0.0 → v7.0.1,
  `actionlint` 1.7.11 → 1.7.12 (regex), `ghcr.io/astral-sh/uv` 0.13.5 → 0.13.6 (dockerfile), all in
  `renovate/template-pins`. The local platform stops before branches, so the rewrite was checked by passing
  the logged upgrades to Renovate's own `doAutoReplace`: the SHA and its comment change together,
  `astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3`, and nothing else in the file.
- **Regex managers** found every hand pin a `grep` finds: actionlint in workflows, tests and AGENTS.md,
  gitleaks, markdownlint-cli2, hadolint and kubeconform release URLs, hadolint's image in tests.
- **Noise, not misses:** `dockerfile` on every `*.jinja` reads Python `from x import y` and `FROM [[ ... ]]`
  as images (`invalid-value`, skipped); `github-actions` on every `*.jinja` logs schema errors for
  CODEOWNERS, LICENSE and the like. The `FROM` lines in template-python are `[[ layer.container_base ]]`,
  derived from the `python_version` answer, so they are no template pin. `ghcr.io/astral-sh/uv` in
  `COPY --from=` is found by both `dockerfile` and the regex manager; the second is a no-op in the same
  branch.
- **Side effect:** in YAML that parses, `github-actions` also bumps action inputs: template-base's own
  `template-ci.yml` got `node-version: '24'` → `'26'` (a major, so its own branch). The preset should say
  whether it wants that (a `packageRules` entry on `depType: uses-with`).

**So:** no `uses:` regex fallback is needed. The one change is to narrow the two managers to the files they
can read, which a re-run confirmed finds the same pins and none of the noise:

```json
"github-actions": { "managerFilePatterns": ["template/**/.github/workflows/**"] },
"dockerfile": { "managerFilePatterns": ["template/**/*Dockerfile*", "includes/**/*Dockerfile*"] }
```

**The `workflows` permission.** GitHub says an App needs it "to access or edit Actions files in the
`.github/workflows` directory" ([choosing permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)),
and that "you must store workflow files in the `.github/workflows` directory of your repository"
([workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)), so
`template/.github/workflows/` holds no workflow GitHub would run and isn't that directory. The docs don't
say so for nested paths in as many words; the first `fix(deps)` push by an App without `workflows` settles
it, and Courier (open question 2) has the permission either way.
