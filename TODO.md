# TODO

template-base's own outstanding work. Bugs and features with discussion belong in GitHub issues; this file is
for what maintainers (and their AI assistants) should know at a glance. An Approved design record with work
left gets a line here or an issue.

## Open

Nothing yet.

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
- The PR template and issue-form config owned by base, the code checklist in `.agents/stack.md`: reviewers read the PR template, and the Documentation link has nowhere else to go; two slots instead ([0001](docs/decisions/0001-stacked-templates.md), #1)
