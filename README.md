# template-base

The base every metalayerlab project starts from: AI-assistant instructions, the guard rails (agent
permissions, the repository-boundary hook, the secret scan), CI with one required check, and weekly template
updates. A **stack overlay** goes on top and says what the project is.

```sh
uvx copier copy --trust gh:andronics/template-base my-project
uvx copier copy --trust gh:andronics/template-obsidian my-project   # or another stack overlay
```

Base always goes first: the overlay reads its answers from `.copier-answers.base.yml` and never asks them again.

## How the stack fits together

| Mechanism | What it is |
|---|---|
| Answers files | Base writes `.copier-answers.base.yml`; the stack overlay `.copier-answers.stack-<name>.yml`; a feature overlay `.copier-answers.<name>.yml`. Each updates on its own schedule |
| Slots | Fixed names base expects and the stack overlay fills: `.github/workflows/stack-ci.yml`, `.agents/stack.md`, `.gitignore`, `.pre-commit-config.yaml`, `.claude/settings.json`, `README.md`, `.github/dependabot.yml` |
| Drop-ins | `scripts/checks.d/`, `post-update.d/`, `bootstrap.d/`: `scripts/checks.sh` and friends run every file in order |
| Ownership by name | `base-*` is base's; `<overlay>-*` and `NN-<overlay>*.sh` an overlay's, marked `Template-owned: template-<name>`; anything else the project's |
| One required check | `base-ci.yml`'s `ci` job gathers the secret scan, `scripts/checks.sh`, actionlint and the stack's `stack-ci.yml` |
| The contract | `scripts/checks.d/00-base.sh` fails without exactly one stack overlay, a slot, a base entry in a composite file (the gitleaks hook, `private/`, the `gh` allow and the release/repo-delete/repo-archive denies), an owner's answers file, or inside the context budget |
| Updates | `template-update.yml` updates base, then the stack overlay, then feature overlays by name: one PR per template, then `scripts/post-update.sh` |

The Definition of done in every project is `sh scripts/checks.sh` plus the Docker secret scan.

## Versions

Releases start at `v1.0.0` (release-please), so this line is never mistaken for project-template's `v0.1.x`.
An overlay checks base's `_commit` against the version it needs, and fails the copy or update if base is older.

## Where this came from

This repository was built from the files of
[metalayerlab/project-template](https://github.com/metalayerlab/project-template) at `v0.1.23`, as a new
repository with no history, tags or releases (the idea note *🥞 Stacked Copier Templates*). Its design records
(0001–0020) are not imported: [`docs/decisions/0001`](docs/decisions/0001-stacked-templates.md) rebuilds the
ones that still govern base, and names the ones left for the code overlays. The originals stay in
[project-template's `docs/design/`](https://github.com/metalayerlab/project-template/tree/main/docs/design).

## License

[Unlicense](LICENSE).
