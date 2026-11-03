# 0005: `owner_is_org` follows `code_owners` when it is known

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Implemented
Date: 2026-11-03
Authors: Stephen Cox

## Context

Decision 0003 added `owner_is_org` (bool, default `true`) and said an existing project's `copier update`
"records `owner_is_org: true` for them and changes nothing". It did record `true`, for personal accounts
too: the brain (andronics, a user) answers `code_owners: '@andronics'`, and its update to v2.0.10 wrote
`owner_is_org: true` into `.copier-answers.base.yml`. Each overlay keeps a copy of base's answers
(`base_answers`, decision 0001), so template-obsidian's next update copied the wrong value into
`.copier-answers.stack-obsidian.yml`. The overlays copy base's file as it is and invent nothing: a key missing
from base's file is missing from the copy. The wrong value comes from base's default.

Copier still can't ask GitHub whether an owner is an organisation (0003), but on an update, or with
`-d code_owners=…`, it does know `code_owners`: Copier renders each question with the recorded answers in
its context, so `owner_is_org` can read `code_owners` though it is asked first. GitHub's CODEOWNERS takes
users, `@org/team`s and emails; an organisation is not a user, so it can't be a code owner. A
`code_owners` naming `@<github_owner>` therefore means a personal account.

## Decision

- **Default:** `owner_is_org` is `false` when `code_owners` is known and names `@<github_owner>` (as a
  whole entry, case-insensitive), else `true`. A first copy doesn't know `code_owners` yet, so it still
  defaults to `true`, as in 0003. An update of a project from before the question records `false` for a
  personal account and `true` for an organisation.
- **Validators:** `owner_is_org: true` beside a `code_owners` naming `@<github_owner>` fails, on both
  questions. Copier drops a recorded answer that fails its validator and recomputes it from the default,
  so a project that already recorded the wrong `true` records `false` on its next base update. The
  validator on `code_owners` keeps an interactive copy (which asks `owner_is_org` first) from recording
  the pair, so a later update's replay of this version never meets it.
- `code_owners` is still asked and still wins; rendered files don't change. Only the answers files do.

## Alternatives considered

- **Omit missing keys in the overlays' copy:** they already do. The copy reads base's file, and the
  wrong value was in base's file.
- **A `_migrations` task rewriting the answers file:** Copier reads the recorded answers before "before"
  migrations run, so the update would still use the old value, and it adds a script base must keep.
- **Ask the GitHub API:** rejected in 0003 (network and a token at render time).
- **Infer `true` from a `/team` in `code_owners`, `false` otherwise:** an organisation may list users
  (`@alice @bob`); that is valid and says nothing about the owner. Only `@<owner>` is conclusive.

## Consequences

- A personal-account project from before 0003, or one that recorded `owner_is_org: true` since, gets
  `owner_is_org: false` in its next base update PR. The overlay's next update PR copies it into
  `base_answers` (its validator sees the copy is stale). The template-update workflow updates each
  template from `main` in its own job, so the overlay's PR follows on the run after base's PR merges.
- Organisations, and personal accounts whose `code_owners` doesn't name the owner, keep what they have.
- A copy with `owner_is_org: true` and `code_owners` naming the owner fails with the reason.

## Open questions

- None.
