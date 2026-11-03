# Design records

Why template-base is the way it is. Copy [0000-template.md](0000-template.md) to `NNNN-short-title.md` and add
a line below. **Read this index first**, then only the records you need. project-template's records (0001–0020)
are not imported: 0001 rebuilds the ones that still govern base; the originals are in
[project-template's docs/design/](https://github.com/metalayerlab/project-template/tree/main/docs/design).

| # | Title | Status | Decision in one line |
|---|---|---|---|
| [0001](0001-stacked-templates.md) | Stacked templates | Approved | A base plus one stack overlay per project: answers files by role, slots, drop-ins, ownership by name, one `ci` check, one update PR per template; carries project-template's 0002–0004, 0006, 0007, 0010, 0011 and 0013 |
| [0002](0002-template-pin-bumps.md) | Automatic pin bumps for template sources | Accepted | Self-hosted Renovate, from a preset and workflow at template-base's root, bumps action SHAs and tool pins in every template repo's `.jinja` sources and own CI, with no render step; projects keep Dependabot (#20) |
| [0003](0003-codeowners-personal-accounts.md) | CODEOWNERS on personal accounts | Implemented | An `owner_is_org` question (default true) picks the `code_owners` default: `@owner/maintainers` for an organisation, `@owner` for a personal account |
| [0004](0004-app-token-minting.md) | App token minting | Approved | One composite action (`.github/actions/app-token`) mints every App token, with `owner:`, explicit permissions and a declared fallback (`required` or `github-token`); secrets named by role (`UPDATE_APP_*`, `RELEASE_APP_*`, `BRAIN_PULL_APP_*`), the legacy names shimmed until the next major |
| [0005](0005-owner-is-org-from-code-owners.md) | `owner_is_org` follows `code_owners` | Implemented | `owner_is_org` defaults to false when `code_owners` names `@owner` (an organisation can't be a code owner), and a recorded `true` beside it fails validation, so an update corrects it; amends 0003 |
| [0006](0006-project-gitleaks-allow-list.md) | The project's gitleaks allow-list | Implemented | `.gitleaks.toml` becomes the project's (`_skip_if_exists`) and extends the template-owned `.gitleaks.base.toml` (default rules, base's allow-list); an existing project's `scripts/post-update.sh` switches `useDefault = true` to that `path`; `00-base.sh` fails on a file that still doesn't extend it |
| [0007](0007-gitleaks-scan-scope.md) | gitleaks scan scope | Approved | On a PR, the `secrets` job scans only that PR's commits; a nightly scheduled run scans the full history and opens or updates a `secret-scan` issue on a finding |
