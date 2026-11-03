# AGENTS.md: working on template-base

This repository is a [Copier](https://copier.readthedocs.io/) template: `template/` is rendered into every
new project, and one **stack overlay** (template-python, template-typescript or template-obsidian) is applied
on top of it, then any feature overlay (template-container). These instructions are for changing **the base**. The instructions
projects get are in `template/AGENTS.md.jinja`. Why it is split this way: `docs/decisions/0001-stacked-templates.md`.

## Layout

| Path | What |
|---|---|
| `copier.yml` | The identity questions, derived values, `_skip_if_exists` and the bootstrap task |
| `template/` | Everything rendered into a project. `.jinja` files are rendered; the rest are copied verbatim |
| `template/scripts/base-contract.py` | The stack contract `checks.d/00-base.sh` enforces: slots, owners by name, base entries, budget |
| `tests/` | Renders base with a stub stack overlay (`tests/fixtures/stub-stack/`) and with each real overlay checked out next to it (skipped if missing); the contract cases |
| `docs/decisions/` | Design records; `README.md` is the index |
| `renovate/templates.json5`, `.github/workflows/pin-bumps.yml` | Pin bumps for every template repository (0002): the shared Renovate preset and the reusable workflow. Repository tooling, never rendered |
| `.github/actions/app-token/`, `includes/github/app-token.yml.jinja` | The App-token mint (0004): the composite action every template repository's workflows call, and the macro base's rendered workflows import instead |

## The rules of the split

- **Base never names an overlay.** No stack, language or kind switch in `template/` or `copier.yml`
  (`tests/test_base.py::test_base_names_no_overlay`). An overlay extends base through a slot or a drop-in
  folder (`scripts/checks.d/`, `post-update.d/`, `bootstrap.d/`), never by editing a base file.
- **One owner per file.** A file base writes is never written by an overlay, and the reverse.
- **Overlays read base's answers through their own `base_answers` answer**, never `_external_data` directly:
  `copier update` replays without `.copier-answers.base.yml` (0001, `tests/test_update.py`).
- **Slots** (`stack-ci.yml`, `.agents/stack.md`, `.gitignore`, `.pre-commit-config.yaml`, `.claude/settings.json`,
  `README.md`, `.github/dependabot.yml`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/config.yml`)
  are filled by the one stack overlay. A new slot, or a new entry base needs in one, is a change to
  `base-contract.py` and a minor release, and every stack overlay must follow it.
- Every template-owned script and workflow starts with `Template-owned: template-<name>`.

## Jinja in this template

- Delimiters are **`[[ var ]]`**, **`[% block %]`** and **`[#! comment !#]`**, so GitHub Actions' `${{ }}`
  needs no escaping. Never write `[[` in a `.jinja` file unless you mean a variable.
- Conditional files go in the *name*: `[% if personal_data_guard %]check-personal-data.py[% endif %]`.
- `trim_blocks` and `lstrip_blocks` are on: check the rendered output, not the source.

## Don't read

`uv.lock`, `.venv/`, `CHANGELOG.md` (use `git log`), and `.graphify/`.

## Rules

- Every change keeps the stub render, every overlay render and the contract tests green: `uv run pytest`.
- A change to what projects get reaches every project, whatever its stack: a `feat:`/`fix:` PR title, `!` if breaking.
- Template-owned vs project-owned is decided by `_skip_if_exists`. Never make a file project-owned without saying why.
- AI-facing files have a budget (`BUDGET` in `template/scripts/base-contract.py`); the skeleton may use 75% of it
  together with a stack's `.agents/stack.md`. Raising it needs a design record.
- Pin actions to commit SHAs, with the version in a trailing comment.
- Pins are bumped by Renovate (decision 0002): don't hand-bump one unless it's urgent.
- Never credit an AI in commits or PRs. Never create tags or releases: release-please does.
- Asking the user something? Give your recommendation and why. Reply tersely.

## Definition of done

```sh
uv run pytest -m ''                                             # renders, contract cases, Docker and npx checks
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.12
```
