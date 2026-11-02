# 0003: CODEOWNERS on personal accounts

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Implemented
Date: 2026-11-02
Authors: Stephen Cox; drafted by Claude (Claude Code)

## Context

`code_owners` defaulted to `@<github_owner>/maintainers`. Teams exist only in organisations, so on a personal
account (andronics) the default named a team that cannot exist and GitHub marks the CODEOWNERS file invalid.
Copier cannot ask GitHub at render time whether an owner is an organisation without a network call in a
template, which `copier copy --defaults` and the tests should not depend on.

## Decision

A new base question, `owner_is_org` (bool, default `true`), asked after `github_owner`. It only picks the
`code_owners` default: `@<owner>/maintainers` when true, `@<owner>` when false. `code_owners` is still asked
and still wins. Organisations (metalayerlab) render as before.

## Alternatives considered

- **Look the owner up with the GitHub API** (a task or `_external_data`): needs network and a token at
  render time, and fails offline and in the tests.
- **Default to `@<owner>` everywhere**: valid on both, but loses the team default organisations rely on.
- **Only a better help text**: the wrong default is still the one `--defaults` writes.

## Consequences

Existing projects keep their recorded `code_owners`; `copier update` records `owner_is_org: true` for them
and changes nothing. brain already answers `code_owners: '@andronics'`, so it needs no change. A new
personal-account project answers `owner_is_org: false` once.
