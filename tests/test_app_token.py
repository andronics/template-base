"""The App-token action (decision 0004), and the workflows that mint with it.

`.github/actions/app-token` is repository tooling (template-base's own workflows; the overlays' later), and
`includes/github/app-token.yml.jinja` renders the same contract into base's projects (test_base.py checks
the rendered template-update.yml). The action's two shell steps run here, with the inputs as their env.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml
from stacking import ROOT

ACTION = ROOT / ".github/actions/app-token/action.yml"
INCLUDE = ROOT / "includes/github/app-token.yml.jinja"
MINT = "actions/create-github-app-token@"


def action() -> dict:  # type: ignore[type-arg]
    return yaml.safe_load(ACTION.read_text())  # type: ignore[no-any-return]


def step(sid: str) -> dict:  # type: ignore[type-arg]
    return next(s for s in action()["runs"]["steps"] if s.get("id") == sid)


def run_step(sid: str, env: dict[str, str], tmp_path: Path) -> tuple[int, dict[str, str], str]:
    """Run one of the action's shell steps with `env` standing in for its evaluated `env:`."""
    out = tmp_path / f"{sid}.out"
    out.write_text("")
    result = subprocess.run(["bash", "-e", "-c", step(sid)["run"]], check=False, capture_output=True, text=True,
                            env={"PATH": "/usr/bin:/bin", "GITHUB_OUTPUT": str(out),
                                 "GITHUB_REPOSITORY": "acme/widget", "GITHUB_REPOSITORY_OWNER": "acme", **env})  # fmt: skip
    found = dict(line.split("=", 1) for line in out.read_text().splitlines())
    return result.returncode, found, result.stdout


def pick(tmp_path: Path, **overrides: str) -> tuple[int, dict[str, str], str]:
    env = {"ROLE": "UPDATE", "FALLBACK": "required", "HAS_ID": "false", "HAS_KEY": "false",
           "HAS_LEGACY_ID": "false", "HAS_LEGACY_KEY": "false", "OWNER": "acme", "REPOSITORIES": "",
           "PERMISSIONS": " write  write "}  # fmt: skip
    return run_step("pick", {**env, **overrides}, tmp_path)


def test_action_pins_the_mint_by_sha() -> None:
    """Both mints, and the rendered include, use the one SHA-pinned create-github-app-token."""
    uses = {s["uses"] for s in action()["runs"]["steps"] if "uses" in s}
    assert len(uses) == 1
    (pin,) = uses
    assert re.fullmatch(rf"{re.escape(MINT)}[0-9a-f]{{40}}", pin)
    assert f"uses: {pin} # v" in ACTION.read_text() and f"uses: {pin} # v" in INCLUDE.read_text()


def test_action_passes_every_permission_through() -> None:
    """Every permission-* input reaches both mints and the empty-list check; owner and repositories too."""
    permissions = {k for k in action()["inputs"] if k.startswith("permission-")}
    assert {
        "permission-contents",
        "permission-pull-requests",
        "permission-workflows",
        "permission-issues",
    } <= permissions
    for sid, client in (("app", "client-id"), ("legacy", "legacy-client-id")):
        given = step(sid)["with"]
        assert {k for k in given if k.startswith("permission-")} == permissions, sid
        assert all(given[k] == f"${{{{ inputs.{k} }}}}" for k in permissions), sid
        assert given["client-id"] == f"${{{{ inputs.{client} }}}}", sid
        assert given["owner"] == "${{ inputs.owner }}", sid
        assert given["repositories"] == "${{ steps.pick.outputs.repositories }}", sid
    listed = step("pick")["env"]["PERMISSIONS"]
    assert all(f"inputs.{k} }}}}" in listed for k in permissions)


@pytest.mark.parametrize(
    ("has", "pair"),
    [
        ({"HAS_ID": "true", "HAS_KEY": "true", "HAS_LEGACY_ID": "true", "HAS_LEGACY_KEY": "true"}, "app"),
        ({"HAS_ID": "true", "HAS_KEY": "true"}, "app"),
        ({"HAS_LEGACY_ID": "true", "HAS_LEGACY_KEY": "true"}, "legacy-app"),
        ({"HAS_ID": "true", "HAS_LEGACY_ID": "true", "HAS_LEGACY_KEY": "true"}, "legacy-app"),
        ({"HAS_LEGACY_ID": "true"}, "none"),
        ({}, "none"),
    ],
)
def test_action_reads_the_role_names_then_the_legacy_ones(tmp_path: Path, has: dict[str, str], pair: str) -> None:
    """A complete role pair wins; else a complete legacy pair (with a rename warning); else none."""
    code, found, out = pick(tmp_path, **has)
    assert code == 0 and found["pair"] == pair, out
    assert ("legacy secret names" in out) == (pair == "legacy-app")
    assert ("only half" in out) == (has.get("HAS_ID") == "true" and has.get("HAS_KEY") != "true")


def test_action_scope(tmp_path: Path) -> None:
    """Empty repositories: this one only; `*`: the installation; another owner must name its repositories."""
    assert pick(tmp_path)[1]["repositories"] == "widget"
    assert pick(tmp_path, REPOSITORIES="*")[1]["repositories"] == ""
    assert pick(tmp_path, REPOSITORIES="a,b")[1]["repositories"] == "a,b"
    assert pick(tmp_path, OWNER="other")[0] != 0
    assert pick(tmp_path, OWNER="other", REPOSITORIES="a")[0] == 0


def test_action_refuses_what_it_must(tmp_path: Path) -> None:
    """No permissions (a token with all of the App's), an unknown fallback, or no owner: an error."""
    assert pick(tmp_path, PERMISSIONS="   ")[0] != 0
    assert pick(tmp_path, FALLBACK="maybe")[0] != 0
    assert pick(tmp_path, OWNER="")[0] != 0
    assert pick(tmp_path, FALLBACK="github-token")[0] == 0


@pytest.mark.parametrize(
    ("pair", "fallback", "workflows", "source", "can"),
    [
        ("app", "required", "write", "app", "true"),
        ("legacy-app", "required", "write", "legacy-app", "true"),
        ("app", "github-token", "", "app", "false"),
        ("none", "github-token", "write", "github-token", "false"),
        ("none", "required", "write", "none", "false"),
    ],
)
def test_action_outputs(tmp_path: Path, pair: str, fallback: str, workflows: str, source: str, can: str) -> None:
    """`source` says where the token came from; only an App token with workflows: write can push workflows."""
    token = "" if source == "none" else "t0ken"
    code, found, out = run_step("result", {"ROLE": "UPDATE", "PAIR": pair, "FALLBACK": fallback,
                                           "WORKFLOWS": workflows, "TOKEN": token}, tmp_path)  # fmt: skip
    assert code == 0, out
    assert found == {"token": token, "source": source, "can-push-workflows": can}
    assert ("::notice" in out) == (pair == "none")


def test_action_falls_back_to_github_token_only_when_asked() -> None:
    expr = step("result")["env"]["TOKEN"]
    assert "(inputs.fallback == 'github-token' && github.token)" in expr
    assert expr.index("steps.app.outputs.token") < expr.index("steps.legacy.outputs.token") < expr.index("github.token")


def test_release_please_mints_the_release_role() -> None:
    """Tagwarden's token: contents, pull requests and issues; never workflows (0002); GITHUB_TOKEN as fallback."""
    steps = yaml.safe_load((ROOT / ".github/workflows/release-please.yml").read_text())["jobs"]["release-please"][
        "steps"
    ]
    mint = next(s for s in steps if s.get("uses") == "./.github/actions/app-token")
    assert steps.index(mint) > 0 and steps[0]["uses"].startswith("actions/checkout@")
    given = mint["with"]
    assert given["role"] == "RELEASE" and given["fallback"] == "github-token"
    assert given["client-id"] == "${{ vars.RELEASE_APP_CLIENT_ID }}"
    assert given["private-key"] == "${{ secrets.RELEASE_APP_PRIVATE_KEY }}"
    assert given["owner"] == "${{ github.repository_owner }}"
    assert {k: v for k, v in given.items() if k.startswith("permission-")} == {
        "permission-contents": "write", "permission-pull-requests": "write", "permission-issues": "write"}  # fmt: skip
    release = next(s for s in steps if "release-please-action" in s.get("uses", ""))
    assert release["with"]["token"] == f"${{{{ steps.{mint['id']}.outputs.token }}}}"


def test_no_workflow_mints_directly() -> None:
    """Every mint in template-base's own workflows goes through the action."""
    for flow in (ROOT / ".github/workflows").glob("*.yml"):
        assert MINT not in flow.read_text(), flow.name
