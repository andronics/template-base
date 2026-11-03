# TODO

template-base's own outstanding work. Bugs and features with discussion belong in GitHub issues; this file is
for what maintainers (and their AI assistants) should know at a glance. An Approved design record with work
left gets a line here or an issue.

## Open

- Remove the legacy App secret names (`PIN_BUMP_APP_*`, `SCOUT_APP_*`) and the shim (`legacy-*` inputs of `.github/actions/app-token`, the `legacy` argument of `includes/github/app-token.yml.jinja`, `PIN_BUMP_APP_PRIVATE_KEY` in `pin-bumps.yml`'s `workflow_call`) in template-base's next major, once every template repository and project has set `UPDATE_APP_*` / `BRAIN_PULL_APP_*`, deleted the old names and taken a base release with the shim; the action's "legacy secret names" warning finds the stragglers ([0004](docs/decisions/0004-app-token-minting.md)).
- Renovate for the template repos' own `uv.lock` in the `chore(deps)` group, after pins have run for a few weeks ([0002](docs/decisions/0002-template-pin-bumps.md), open question 5).

## Decided against (don't re-propose without reading this first)

<!-- One line each: the idea, why not, and a link to the issue, PR or design record. -->

- Denying every `git push` to agents: the `main` ruleset already guards `main`, so agents push feature branches (project-template's [0011](https://github.com/metalayerlab/project-template/blob/main/docs/design/0011-agent-git-permissions.md), kept by [0001](docs/decisions/0001-stacked-templates.md))
- Claude Code's sandbox on by default, to confine Bash to the project: it also blocks the `uv` cache, Docker and `gh` login (project-template's [0013](https://github.com/metalayerlab/project-template/blob/main/docs/design/0013-repository-boundary.md), kept by [0001](docs/decisions/0001-stacked-templates.md))
- Setting "Allow GitHub Actions to create and approve pull requests" from `repo-metadata.py`: CI's `GITHUB_TOKEN` can't read it, and it is a security choice for the maintainer (project-template's [0018](https://github.com/metalayerlab/project-template/blob/main/docs/design/0018-brain-pull.md))
- A meta-template that generates each stack's template repository: two update hops per change, and Jinja that renders Jinja ([0001](docs/decisions/0001-stacked-templates.md))
- One template with tidier layers: every change still ships everywhere ([0001](docs/decisions/0001-stacked-templates.md))
- Renaming project-template to template-base: drags the single-template history along, and old projects depend on GitHub's redirect ([0001](docs/decisions/0001-stacked-templates.md))
- A required check per overlay job: the list changes whenever an overlay adds a job; one aggregate `ci` instead ([0001](docs/decisions/0001-stacked-templates.md))
- A free-text `stack` answer in base that renders `uses:`: `uses:` takes a fixed path, and the overlay's identity would live in two places; the `stack-ci.yml` slot instead ([0001](docs/decisions/0001-stacked-templates.md))
- Owners from a list of prefixes in base: base would name overlays; the `Template-owned:` marker instead ([0001](docs/decisions/0001-stacked-templates.md))
- The context budget in each stack's checker: two copies of one number, guarding files base owns ([0001](docs/decisions/0001-stacked-templates.md))
- `dependabot.yml` owned by base: a code overlay couldn't add its ecosystem; a slot instead ([0001](docs/decisions/0001-stacked-templates.md))
- Rendering the templates to bump their pins: a rendered line maps back to its `.jinja` source only by search, per variant; Renovate reads the sources directly ([0002](docs/decisions/0002-template-pin-bumps.md))
- gitleaks over the full history on every PR: an old finding blocks every PR, by authors who can't fix it there ([0007](docs/decisions/0007-gitleaks-scan-scope.md))
- gitleaks over a PR's commits only, with no full-history scan: a finding in history is never seen again ([0007](docs/decisions/0007-gitleaks-scan-scope.md))
- Pins in one data file the templates read: hides them from actionlint and every bot, and overlays share no Jinja ([0002](docs/decisions/0002-template-pin-bumps.md))
- Bumping template pins by hand on release: v10.3.2 sat in five repos while a project was on v10.3.3; Renovate weekly instead ([0002](docs/decisions/0002-template-pin-bumps.md))
- Actor-keyed App secret names (`COURIER_APP_*`): the actor filling a role differs by owner, so every rendered workflow would need a per-owner answer; role-keyed instead ([0004](docs/decisions/0004-app-token-minting.md))
- Calling the token action remotely from base's own `template/`: base would pin itself, and Renovate would bump that pin after every release, a `fix(deps)` cutting the next one; a rendered macro instead ([0004](docs/decisions/0004-app-token-minting.md))
- Pin-bump PRs from `GITHUB_TOKEN` when no App is configured: its PRs run no CI, so they can't merge; the workflow skips with a notice ([0002](docs/decisions/0002-template-pin-bumps.md))
- The PR template and issue-form config owned by base, the code checklist in `.agents/stack.md`: reviewers read the PR template, and the Documentation link has nowhere else to go; two slots instead ([0001](docs/decisions/0001-stacked-templates.md), #1)
