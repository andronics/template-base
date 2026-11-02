# 0001: Stacked templates: a base, and one stack overlay per project

Status: Approved
Date: 2026-11-01
Authors: Stephen Cox; drafted by Claude (Claude Code)

## Context

`metalayerlab/project-template` was one Copier template: a language-agnostic core plus `layers/<lang>/`,
with about 114 `language ==` / `kind ==` conditionals. Every change, even to one layer, was a release of the
whole template and an update PR in every project. The layer contract made every layer define everything the
core asked for, so `layers/obsidian/` carried Docker, systemd and release pieces a vault never uses, and the
core had to know each layer by name.

The idea note **🥞 Stacked Copier Templates** (in the brain's `vault/ideas/`) chose to stack templates instead
(its option A). This record is the split as built, and it rebuilds the parts of project-template's design
records 0001–0020 that still govern base. Those records are not imported. The originals stay in
project-template's `docs/design/`.

## Decision

### Repositories and versions

- One repository per template, `template-<name>`, because a Copier source is a repository root. This
  repository is new, built from project-template `v0.1.23`'s files, with no history, tags or releases.
  `project-template` stays untouched until no project's `_src_path` points at it, then it is archived.
- Releases start at `v1.0.0` (release-please, `initial-version`), so they are never mistaken for
  project-template's `v0.1.x`.

### Stacking

- **Create:** `copier copy` template-base, then one stack overlay. Base always goes first.
- **Answers files name the role:** base writes `.copier-answers.base.yml`; the stack overlay
  `.copier-answers.stack-<name>.yml`; a future feature overlay `.copier-answers.<name>.yml`. Agents never edit
  any of them (`Edit(.copier-answers.*.yml)` deny, AGENTS.md *Never*).
- **Overlays read base's answers** through `_external_data: {base: .copier-answers.base.yml}` and never
  re-ask base's questions. Base asks only `project_name`, `description`, `github_owner`, `code_owners`,
  `copyright_holder`, `license`, `dependabot_automerge`, `personal_data_guard`.
- **Compatibility:** an overlay computes a hidden value from `_external_data.base._commit`. A missing answers
  file, or a base older than the overlay needs (or untagged), fails the copy or update with that reason.
  Copier runs no validator on a hidden question, so the value raises a Jinja error whose text is the
  message (template-obsidian's `base_check`).

### Ownership

- **One owner per file.** Copier never merges two templates' versions of a file.
- **Base never names an overlay.** No stack, language or kind switch in `template/` or `copier.yml`, which
  a test enforces. It replaces project-template's `tests/test_layers.py`.
- **Slots** are fixed names base expects and the one stack overlay fills: `.github/workflows/stack-ci.yml`,
  `.agents/stack.md`, `.gitignore`, `.pre-commit-config.yaml`, `.claude/settings.json`, `README.md`,
  `.github/dependabot.yml`. Dependabot reads one file, and each stack adds its own ecosystem, so
  `dependabot.yml` is a slot too.
- **Drop-in folders:** `scripts/checks.d/`, `scripts/post-update.d/`, `scripts/bootstrap.d/`. Base's runners
  (`checks.sh`, `post-update.sh`, `bootstrap.sh`) run every `*.sh` in each folder in name order. An overlay
  changes behaviour by adding a file, never by editing a base file.
- **What a drop-in may assume** (issue #4). Anything else it needs, it checks for and names when missing:
  - `checks.d/` runs in base-ci's `checks` job and locally (the Definition of done); `post-update.d/` in
    `template-update.yml`'s `update` job and locally after a local `copier update`. Both jobs are
    `ubuntu-latest` plus `setup-uv`. Such a drop-in may assume `sh`, `python3`, `git` and `uv`, and in CI
    whatever the runner image has preinstalled (unpinned; Docker among it). A tool that's only on the
    image, such as Docker, may be missing locally: skip with a message there and fail in CI, as
    `check-docs-secrets.sh` does. Otherwise a missing tool fails with a message naming it.
  - `bootstrap.d/` runs only on the developer's machine, as Copier's task on `copier copy` (or by hand), so
    no runner image applies. It may assume only `sh` and `git`. For anything else it checks first and, when
    the tool is missing, prints what to install and carries on, as `bootstrap.sh` does for pre-commit,
    rather than failing the copy.
  - A stack's own toolchain works within these tools, or in its own `stack-ci.yml` jobs, which can install
    anything. *Rejected:* base reading an optional, stack-neutral toolchain file (`.nvmrc`, say) and
    installing it in these jobs: base would still name no overlay, but it would know one stack's file.
    Revisit if a lock refresh breaks on the runner's Node.
- **Ownership by name:** `base-*` (and `template-update.yml`, `pr-title.yml`, the runners) are base's;
  `<overlay>-*` workflows and `NN-<overlay>*.sh` drop-ins are an overlay's; anything else is the project's.
  Every template-owned script and workflow carries `Template-owned: template-<name>` near its top. The
  contract check learns owners from that marker and from the answers files, so base never needs a list of
  overlays.

### The contract: `scripts/checks.d/00-base.sh`

`scripts/base-contract.py` (stdlib) fails when any of these holds:

- base's answers file is missing, or there isn't exactly one `.copier-answers.stack-*.yml`;
- a slot is missing, `stack-ci.yml` isn't `workflow_call`, or `dependabot.yml` lacks `github-actions`;
- a marked file names a template with no answers file, or an overlay's workflow or drop-in lacks its prefix;
- a composite file lacks an entry base's rules depend on. In `.gitignore`: `.env`, `secrets/`, `private/`,
  keys, the local Claude files and the graphify caches. In pre-commit: the gitleaks hook. In
  `.claude/settings.json`: the allow and deny lists below, and the repository-boundary hook;
- the AI files are over their context budget.

`00-base.sh` also validates `.github/repository.toml` and self-tests the boundary hook.

### CI and updates

- `base-ci.yml` holds no stack logic. Its jobs are `secrets` (gitleaks), `personal-data` (opt-in), `checks`
  (`sh scripts/checks.sh`, with uv), `stack` (`uses: ./.github/workflows/stack-ci.yml`) and `workflows`
  (actionlint). A job can't both run steps and call a reusable workflow, so the required check is an
  aggregate job **`ci`**: it `needs:` the others and passes only if each one succeeded or was skipped.
  Branch protection names `ci` for every stack. The About-box drift warning runs on `main` outside `ci`.
  `pr-title.yml` stays separate, outside required checks, because it reruns on title edits.
- `template-update.yml` orders the answers files: base, then the stack overlay, then feature overlays by
  name. It updates each in turn with `--skip-tasks`, runs `scripts/post-update.sh`, and opens **one PR per
  template** (`chore/<template>-update`). Without the release App, a change to workflows opens an issue
  asking for a local update, as before.

### Agent permissions

Agents may run every `gh` command except releases, `repo delete` and `repo archive`. `.claude/settings.json`
(a slot) allows `Bash(gh:*)` and denies `Bash(gh release:*)`, `Bash(gh api *releases*)`,
`Bash(gh repo delete:*)` and `Bash(gh repo archive:*)`. Deny beats allow. `Bash(gh api *releases*)` was
verified in Claude Code 2.1.289: a headless run with the allow above was denied
`gh api repos/…/releases/latest`, and ran it without the deny. `gh pr merge` and `gh repo edit` stay allowed.
The other denies stay: pushes naming `main`, force pushes, tag pushes, `git tag`, and `gh pr create -R`.
A command pattern can't catch every API route, so a tag ruleset in this repository's settings should
restrict `v*` tags and releases to the release App. That is set when the repository is created.

### What carries over from project-template's records

| Old record | In base now |
|---|---|
| 0001 Template architecture | Copier, release-please and one AGENTS.md stay; the core plus layers becomes base plus a stack overlay (this record) |
| 0002, 0006 Context budget | `BUDGET` in `base-contract.py`: AGENTS.md **plus** `.agents/stack.md` 9,000 characters (CLAUDE.md loads both), CLAUDE.md 600, GEMINI.md 300, the Cursor rule 300, Copilot 700. The skeleton may use 75%. It moved from the stacks' checkers (the vault check, the wiki standard) to base, which owns the files |
| 0003 Dependabot auto-merge | Opt-in `dependabot_automerge`; `base-dependabot-automerge.yml` queues auto-merge, never approves |
| 0004 Local lint | `scripts/check-docs-secrets.sh` runs gitleaks with CI's pins, and CI calls the same script. Markdown lint leaves base: a stack that wants it adds a drop-in |
| 0007 Terse sessions | Checks print one line on a pass; AGENTS.md's terse-reply and end-of-session rules |
| 0010 Repository metadata | Project-owned `.github/repository.toml` (seeded empty: base can't know a stack's homepage or topics), `scripts/repo-metadata.py`; drift warns, never fails |
| 0011 Agent git permissions | Kept, plus the `gh` rules above |
| 0013 Repository boundary | The PreToolUse hook `scripts/repo-boundary.py`, the AGENTS.md rule and the change-request issue form |

Left for the code overlays (template-python, template-typescript, template-none), which keep them from
project-template: 0005 extra ports, 0008 `language: none` (becomes template-none), 0009 TypeScript, 0012 image
extras, 0014 the web kind, 0017 the integration job, and 0020 config on interpose. 0015 and 0016 (brains) and
0018 and 0019 (Brain pull) are template-obsidian's: its decision 0001.

### What base renders

Base's files are the old core's **brain rendering made overlay-neutral**. Releases, the wiki, Docker,
markdownlint and the code-only issue forms were the parts `kind: brain` excluded, and they move to the code
overlays. Today's `kind == 'brain'` exclusions become simple absence.

## Alternatives considered

- **A meta-template** (base generates each stack's template repository): every change takes two update hops,
  and you debug Jinja that renders Jinja. *Rejected.*
- **Keep one template, tidy the layers:** doesn't fix "every change ships everywhere". *Rejected.*
- **Rename project-template to template-base:** drags the single-template history along and makes old
  projects depend on GitHub's redirect. *Rejected* for a new repository with no history.
- **A required check per overlay job:** the list changes whenever an overlay adds a job. *Rejected* for one
  aggregate `ci`.
- **A free-text `stack` answer in base that renders `uses:`:** `uses:` takes a fixed path, and the overlay's
  identity would live in two places that can drift. *Rejected* for the `stack-ci.yml` slot.
- **Owners from a list of prefixes in base:** base would name overlays. *Rejected* for the marker comment.
- **The context budget in each stack's checker:** two copies of one number, guarding files base owns.
  *Rejected.*
- **`dependabot.yml` owned by base:** a code overlay couldn't add its ecosystem. *Rejected* for a slot.

## Consequences

- A change to an overlay ships only to its projects; a change to base ships everywhere.
- **Migration** (per project, by Stephen): render base and the overlay in a scratch directory, diff it
  against the project, and commit the two new answers files in place of `.copier-answers.yml` in one reviewed
  PR. Project edits to files that are now another template's must be carried over by hand: in the brain,
  `.gitignore`'s extra lines and `.gitleaks.toml`'s allow-list. Point branch protection at `ci` in the same
  step. A brain's `brain-pull.yml` becomes `obsidian-brain-pull.yml`, so its first run looks back one day
  (it can't find the old workflow's last run): dispatch it with `since` if more time has passed.
- Files a code overlay can't extend, because base owns them: the Documentation link in
  `ISSUE_TEMPLATE/config.yml`, the code checklist in the PR template, Copilot's code rules, and the
  TypeScript section of `.editorconfig`. Revisit them when template-python lands. The likely answer is
  `.agents/stack.md`, or a `.prettierrc` for TypeScript's indent.
- `.github/repository.toml` is seeded with no homepage or topics.

## Open questions

- **Feature overlays (Docker, `contrib/`):** not yet. Keep them in the code overlays, gated by
  `container_image`, until a third language duplicates them.
- **The tag ruleset:** set it when the repository is created (Stephen's step). Recommendation: restrict
  `v*` tag creation and releases to the release App.
