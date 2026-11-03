"""Renovate pin bumps (decision 0002): the shared preset, base's renovate.json, and pin-bumps.yml.

    uv run pytest -m npx          # also validate the preset with renovate-config-validator (npx)

None of this is rendered: it is template-base's repository tooling, which every template repository uses.
"""

from __future__ import annotations

import json
import re
import shutil

import pytest
import yaml
from stacking import ROOT, sh

WORKFLOW = ROOT / ".github/workflows/pin-bumps.yml"
PRESET = "renovate/templates.json5"
CLIENT_ID, PRIVATE_KEY = "UPDATE_APP_CLIENT_ID", "UPDATE_APP_PRIVATE_KEY"
LEGACY_ID, LEGACY_KEY = "PIN_BUMP_APP_CLIENT_ID", "PIN_BUMP_APP_PRIVATE_KEY"  # until removed (0004, TODO.md)


def workflow() -> dict:  # type: ignore[type-arg]
    return yaml.safe_load(WORKFLOW.read_text())  # type: ignore[no-any-return]


def renovate_version() -> str:
    step = next(s for s in workflow()["jobs"]["renovate"]["steps"] if "renovatebot/github-action" in s.get("uses", ""))
    return str(step["with"]["renovate-version"])


def steps() -> list[dict]:  # type: ignore[type-arg]
    return workflow()["jobs"]["renovate"]["steps"]  # type: ignore[no-any-return]


def mint() -> dict:  # type: ignore[type-arg]
    return next(s for s in steps() if s.get("uses", "").endswith("/.github/actions/app-token"))


def test_pin_bumps_mint_the_update_role() -> None:
    """The update role's App (Courier), legacy names as the shim, `required`: never GITHUB_TOKEN (its PRs run no CI)."""
    text = WORKFLOW.read_text()
    assert "github.token" not in text and "secrets.GITHUB_TOKEN" not in text
    given = mint()["with"]
    assert given["role"] == "UPDATE" and given["fallback"] == "required"
    assert given["client-id"] == f"${{{{ vars.{CLIENT_ID} }}}}"
    assert given["private-key"] == f"${{{{ secrets.{PRIVATE_KEY} }}}}"
    assert given["legacy-client-id"] == f"${{{{ vars.{LEGACY_ID} }}}}"
    assert given["legacy-private-key"] == f"${{{{ secrets.{LEGACY_KEY} }}}}"
    assert given["owner"] == "${{ github.repository_owner }}"
    assert {k: v for k, v in given.items() if k.startswith("permission-")} == {
        "permission-contents": "write", "permission-pull-requests": "write", "permission-workflows": "write"}  # fmt: skip
    renovate = next(s for s in steps() if s.get("uses", "").startswith("renovatebot/github-action@"))
    assert renovate["with"]["token"] == f"${{{{ steps.{mint()['id']}.outputs.token }}}}"
    assert renovate["env"]["RENOVATE_REPOSITORIES"] == "${{ github.repository }}"
    assert re.fullmatch(r"\d+\.\d+\.\d+", renovate_version())


def test_pin_bumps_skip_without_the_app() -> None:
    """No App: the action prints the notice and says `none`, and every later step is skipped."""
    after = steps()[steps().index(mint()) + 1 :]
    assert after and all(f"steps.{mint()['id']}.outputs.source != 'none'" in s["if"] for s in after)


def test_pin_bumps_run_the_action_from_their_own_commit() -> None:
    """An overlay calls this at a pinned SHA: the action comes from that commit of template-base, not the caller."""
    checkout = steps()[steps().index(mint()) - 1]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["repository"] == "${{ job.workflow_repository }}"
    assert checkout["with"]["ref"] == "${{ job.workflow_sha }}"
    assert mint()["uses"] == f"./{checkout['with']['path']}/.github/actions/app-token"


def test_pin_bumps_triggers() -> None:
    """Weekly and by hand for template-base; `workflow_call` for every other template repository."""
    on = workflow()[True]  # PyYAML reads the `on:` key as True
    assert set(on) == {"schedule", "workflow_dispatch", "workflow_call"}
    assert on["schedule"][0]["cron"].split()[-1] == "0", "Sunday, inside the preset's schedule"
    assert set(on["workflow_call"]["secrets"]) == {PRIVATE_KEY, LEGACY_KEY}
    assert workflow()["permissions"] == {}


def test_renovate_json_extends_the_preset() -> None:
    config = json.loads((ROOT / "renovate.json").read_text())
    assert config["extends"] == [f"local>andronics/template-base//{PRESET}"]
    assert (ROOT / PRESET).is_file()


@pytest.mark.npx
def test_renovate_config_is_valid() -> None:
    """The preset and renovate.json, with the Renovate version pin-bumps.yml runs."""
    if not shutil.which("npx"):
        pytest.skip("npx not available")
    sh("npx", "--yes", "--package", f"renovate@{renovate_version()}", "--", "renovate-config-validator",
       "--strict", "--no-global", "renovate.json", PRESET, cwd=ROOT)  # fmt: skip
