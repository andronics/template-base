# meta/: the platform centre's module for `meta`

`meta/platform` answers "how are the templates?" for `meta platform …`, the front door to every knowledge
centre that the brain's design record 0019 (*One Meta Command Is The Front Door To Every Centre*) defines.
The core (`meta`, in the brain) finds it through the platform coordinator's `meta_module` property, reads
its manifest and caches its output. It is repository tooling: copier renders only `template/`, so projects
never get it.

| Verb | Shows |
|---|---|
| `status` | Each template's latest release and its CI on `main`, and the repos behind their template (Courier's open update PRs). Exit 1 on any `warn` or `fail` |
| `list templates\|updates\|releases` | The seven template repos; Courier's open update PRs; Tagwarden's open release PRs (`owner/repo#N`) |
| `show <template>` | One template: latest release and date, CI on `main`, open PRs, open release PR and its version |
| `releases [--since YYYY-MM-DD]` | Template releases since a date, newest first (default: the last 7 days) |

Every verb takes `--json` and `--help`; `meta/platform --meta-manifest` prints the manifest. It reads
GitHub only through one `gh api graphql` query, writes nothing and keeps no cache. Exit codes are the
record's: 0 well, 1 a problem found, 2 usage, 4 GitHub unreachable, 5 no such template.

## Tests

`tests/test_meta_platform.py` runs every verb through a small fake core (the record's environment and
rules) against a fake `gh` that answers from `tests/fixtures/meta_platform/`, so it needs no network:

```sh
uv run pytest tests/test_meta_platform.py
```

To refresh a fixture, record a live answer and keep it small; the secret fixture holds `@@TOKEN@@`, which
the fake `gh` fills in, so no token-shaped string is ever committed.
