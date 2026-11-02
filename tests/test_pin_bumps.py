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
CLIENT_ID = "PIN_BUMP_APP_CLIENT_ID"
PRIVATE_KEY = "PIN_BUMP_APP_PRIVATE_KEY"


def workflow() -> dict:  # type: ignore[type-arg]
    return yaml.safe_load(WORKFLOW.read_text())  # type: ignore[no-any-return]


def runs(condition: str, variables: dict[str, str]) -> bool:
    """A job's `if:`, for the one form the gating uses: `vars.NAME == ''` or `vars.NAME != ''`."""
    match = re.fullmatch(r"vars\.(\w+) (==|!=) ''", condition.strip())
    assert match, f"unexpected job condition {condition!r}"
    empty = variables.get(match[1], "") == ""
    return empty if match[2] == "==" else not empty


def renovate_version() -> str:
    step = next(s for s in workflow()["jobs"]["renovate"]["steps"] if "renovatebot/github-action" in s.get("uses", ""))
    return str(step["with"]["renovate-version"])


def test_pin_bumps_skip_without_the_app() -> None:
    """No App variable: only the notice job runs, so nothing falls back to GITHUB_TOKEN (whose PRs run no CI)."""
    jobs = workflow()["jobs"]
    assert set(jobs) == {"not-configured", "renovate"}
    for variables, expected in (({}, {"not-configured"}), ({CLIENT_ID: "Iv23abc"}, {"renovate"})):
        assert {name for name, job in jobs.items() if runs(job["if"], variables)} == expected, variables
    notice = " ".join(step["run"] for step in jobs["not-configured"]["steps"])
    assert "::notice" in notice and CLIENT_ID in notice and PRIVATE_KEY in notice


def test_pin_bumps_use_only_the_app_token() -> None:
    text = WORKFLOW.read_text()
    assert "github.token" not in text and "secrets.GITHUB_TOKEN" not in text
    steps = workflow()["jobs"]["renovate"]["steps"]
    app = next(s for s in steps if s.get("uses", "").startswith("actions/create-github-app-token@"))
    assert app["with"]["client-id"] == f"${{{{ vars.{CLIENT_ID} }}}}"
    assert app["with"]["private-key"] == f"${{{{ secrets.{PRIVATE_KEY} }}}}"
    assert {k: v for k, v in app["with"].items() if k.startswith("permission-")} == {
        "permission-contents": "write", "permission-pull-requests": "write", "permission-workflows": "write"}  # fmt: skip
    renovate = next(s for s in steps if s.get("uses", "").startswith("renovatebot/github-action@"))
    assert renovate["with"]["token"] == f"${{{{ steps.{app['id']}.outputs.token }}}}"
    assert renovate["env"]["RENOVATE_REPOSITORIES"] == "${{ github.repository }}"
    assert re.fullmatch(r"\d+\.\d+\.\d+", renovate_version())


def test_pin_bumps_triggers() -> None:
    """Weekly and by hand for template-base; `workflow_call` for every other template repository."""
    on = workflow()[True]  # PyYAML reads the `on:` key as True
    assert set(on) == {"schedule", "workflow_dispatch", "workflow_call"}
    assert on["schedule"][0]["cron"].split()[-1] == "0", "Sunday, inside the preset's schedule"
    assert set(on["workflow_call"]["secrets"]) == {PRIVATE_KEY}
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
