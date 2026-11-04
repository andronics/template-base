# 0008: A project's own steps after a template update

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Proposed
Date: 2026-11-04
Authors: Stephen Cox

## Context

`scripts/post-update.sh` (template-owned) runs after every `copier update`: `template-update.yml`'s
`update` job runs it once per template's update, after `copier update` and before
`scripts/stage-conflicts.sh`, and a person runs it after a local update or recopy (`_message_after_update`,
`_message_after_copy`). It runs base's own migrations, then every `scripts/post-update.d/*.sh` in name
order, with `set -eu`, so the first failing step stops the rest. Its comment says the folder holds
"every template's" steps, and today only overlays ship any (`20-python-uv-lock.sh`,
`20-typescript-npm-lock.sh`).

A project needs a step of its own there too. The example: a vault generates shell completions from its
scripts' `argparse` definitions and checks them in CI. When a template update changes one of those
scripts, the completions go stale, the update PR's checks fail, and someone regenerates them by hand. A
step that regenerates them after every update would have made the PR green on its own.

What base already says and does:

- **Ownership by name** (0001): `base-*` and the runners are base's, `<overlay>-*` workflows and
  `NN-<overlay>*.sh` drop-ins an overlay's, "anything else is the project's". The contract
  (`base-contract.py`, run by `checks.d/00-base.sh`) learns owners from the `Template-owned:
  template-<name>` marker: a file in `scripts/` without it is the project's, and only a marked drop-in must
  carry its owner's prefix.
- **checks.d already takes project drop-ins.** `tests/test_contract.py`'s allowed cases include "a project
  drop-in", an unmarked `scripts/checks.d/50-mine.sh`. The same rule covers `post-update.d/` and
  `bootstrap.d/` (the contract lists all three as drop-in folders), but nothing tests or documents a
  project step in them, and the runners' comments speak only of templates.
- **Nothing fixes where a project file sorts.** Templates number theirs `00` (base), `20` (stack overlays)
  and `40` (feature overlays). An unmarked `10-mine.sh` would run before the stack overlay's lock refresh.
- **In CI**, a post-update step runs on `ubuntu-latest` with `setup-uv`, and may assume `sh`, `python3`,
  `git` and `uv` (0001's "What a drop-in may assume"). Git's global config holds the update token (the
  update App's, else the release App's, else `GITHUB_TOKEN`) as an `insteadOf` URL, so a step can reach
  every repository that token can. The job's `GITHUB_TOKEN` has `contents`, `pull-requests` and `issues`
  write. Whatever a step changes in the working tree goes into the update PR.
- **On failure**, the workflow logs a warning, the PR still opens, and its body says `post-update.sh`
  failed (or failed on conflict markers) and asks for it to be run and committed. Locally the script
  exits non-zero.
- **Copier and project files** (checked with Copier 9.19, a two-release template): `copier update` leaves
  alone a file no version of the template renders, and deletes one a new version stopped rendering. A
  project file at a path a new version starts rendering becomes an inline conflict (`<<<<<<< before
  updating` / `>>>>>>> after updating`), which `00-base.sh` then fails. So a project step is safe as long
  as no template ever ships its name.

## Decision

A project adds its own post-update steps as drop-ins in `scripts/post-update.d/`, the precedent `checks.d/`
already sets, under a range of names no template ships.

- **Names:** `9N-project-<what>.sh` (`90`–`99`), for example `90-project-completions.sh`. Templates number
  their drop-ins `00`–`89`, so a project step runs after every template's step, in every locale (two-digit
  prefixes sort the same under any collation). The same convention applies in `checks.d/` and
  `bootstrap.d/`, so one rule covers all three folders.
- **Owner:** the project. No `Template-owned:` marker; never in `_skip_if_exists` or any template's
  `template/`. A template never renders a `9N-` drop-in or one named `NN-project-*`, so `copier update`
  can't conflict with or delete it.
- **The contract** (`base-contract.py`) fails a file carrying a `Template-owned:` marker that is a drop-in
  numbered `90`–`99` or named `NN-project-*`: it would collide with a project's step. It does not fail an
  unmarked drop-in by its name: unmarked files in these folders stay the project's, as today, so
  `checks.d/50-mine.sh` keeps passing.
- **Failure:** a project step fails `post-update.sh` exactly as a template's does. In CI the PR still opens
  with the failure note; locally the script exits non-zero. Because project steps run last, a failing one
  never stops a template's.
- **Where it runs:** in `template-update.yml` on every template's update PR, and locally after an update or
  recopy, so a step must be idempotent and cheap when nothing changed. The same tools as any post-update
  step (`sh`, `python3`, `git`, `uv`; Docker only in CI). A step should change only files the project owns,
  or generated files the project commits, and never push, tag or call GitHub: the update job's token is in
  git's config, and the PR carries its changes.
- **Docs and tests:** `post-update.sh`, `checks.sh` and `bootstrap.sh` say a project may add `9N-project-*`
  steps; 0001's ownership line and the README's "Drop-ins" and "Ownership by name" rows name the range; a
  test shows a `90-project-x.sh` running after a `20-<overlay>-*.sh`; a contract case fails a marked
  `90-*` drop-in. A `feat:` release of base, since it is new guidance every project gets.

## Alternatives considered

- **A reserved range in `post-update.d/` (`9N-project-*.sh`):** follows the precedent `checks.d/` already
  sets (an unmarked drop-in is the project's), needs no change to the runners, and sorts last. *Chosen.*
- **A separate hook, `scripts/post-update.local.sh`** (seeded empty, `_skip_if_exists`, run last): ordering
  is certain, but it is a second mechanism for something the drop-in folders already do, one file grows
  into a script of unrelated steps, and `checks.d/` would still take project drop-ins, so the three folders
  would disagree. Seeding it puts an empty file in every project. *Rejected.*
- **A project-owned folder, `scripts/post-update.project.d/`:** ordering and ownership are certain and no
  name can collide, but it doubles the folders (one per drop-in folder, for consistency), each runner
  globs twice, and it contradicts the existing project drop-in in `checks.d/`. *Rejected.*
- **A prefix without a number (`project-*.sh`):** sorts after every `NN-` name in both C and UTF-8
  collation, but sits outside the `NN-` scheme every other drop-in follows, and a project couldn't order
  two of its own steps without inventing one. *Rejected.*
- **Fail any unmarked drop-in outside `9N-project-*`:** makes the range a rule rather than a convention,
  but breaks projects that already have one (`50-mine.sh` is in the allowed cases on purpose). *Rejected*
  for now; see the open questions.

## Consequences

- A project can repair what a template update breaks in its own files (completions, generated docs, a
  lock refresh of its own) in the update PR itself, instead of by hand after a red check.
- Templates lose the `90`–`99` range and the name `project` for their drop-ins. No template uses either
  today (`00`, `20`, `40`).
- A project with an existing unmarked drop-in keeps working; one that wants it to run last renames it.
- A slow or flaky project step slows or fails every template's update PR, since it runs on each one.
- No migration: base's change is comments, docs, one contract case and tests. Rollback is reverting them;
  project steps still run, as unmarked drop-ins do today.

## Open questions

- **Should the contract later fail an unmarked drop-in outside `9N-project-*`?** Recommendation: not now. It
  would break existing project drop-ins for little gain; the marker already tells template files from
  project ones. Revisit if a project's step is found running before a template's by accident.
- **Is `9N-project-*` the right name, or just `9N-*`?** Recommendation: keep `project` in the name. The
  number alone sorts it, but the word says whose it is when someone reads the folder, and the contract can
  catch a template using it.
- **Should base ship an example (a commented `90-project-example.sh.off`, say)?** Recommendation: no. It
  would be a template-owned file in a project's range; the runners' comments and the README are enough.
