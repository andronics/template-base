"""meta/platform, the platform centre's module for `meta` (the brain's design record 0019).

No network: a fake `gh` on PATH answers from the recorded fixtures in tests/fixtures/meta_platform/,
and a small fake core runs each verb the way record 0019 §3 says the real one will.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "meta/platform"
FIXTURES = ROOT / "tests/fixtures/meta_platform"
NOW = "2026-11-04T05:00:00Z"  # the fixtures were recorded at 04:14
# Built here, never stored in a fixture: the secret fixture holds a placeholder the fake gh fills in.
TOKEN = "ghp_" + "Zx9" * 12
STATES = {"ok", "warn", "fail", "unknown"}

FAKE_GH = """\
import json, os, sys
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
if os.environ.get("FAKE_GH_FAIL"):
    print("error connecting to api.github.com (auth " + os.environ["FAKE_GH_TOKEN"] + ")", file=sys.stderr)
    sys.exit(1)
with open(os.environ["FAKE_GH_FIXTURE"]) as body:
    sys.stdout.write(body.read().replace("@@TOKEN@@", os.environ["FAKE_GH_TOKEN"]))
"""

# Every verb with arguments the fixtures can answer.
CALLS = [
    ["status"],
    ["list", "templates"],
    ["list", "updates"],
    ["list", "releases"],
    ["show", "template-base"],
    ["show", "go"],
    ["releases"],
    ["releases", "--since", "2026-11-01"],
]


@pytest.fixture
def gh(tmp_path: Path) -> dict[str, str]:
    """A fake `gh` first on PATH; returns the environment that points it at a fixture."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "gh"
    fake.write_text(f"#!{sys.executable}\n{FAKE_GH}")
    fake.chmod(0o755)
    return {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_GH_LOG": str(tmp_path / "gh.log"),
        "FAKE_GH_FIXTURE": str(FIXTURES / "ok.json"),
        "FAKE_GH_TOKEN": TOKEN,
        "META_PLATFORM_NOW": NOW,
        "TZ": "UTC",
        "META_CACHE_DIR": str(tmp_path / "cache"),
    }


def manifest() -> dict:
    run = subprocess.run([str(MODULE), "--meta-manifest"], capture_output=True, text=True, check=True)
    return json.loads(run.stdout)


def core(verb: str, args: list[str], env: dict[str, str], as_json: bool = False) -> subprocess.CompletedProcess[str]:
    """Run one verb as record 0019 §3's core does: its environment, `--json` passed on, stdin closed."""
    argv = [str(MODULE), verb, *args, *(["--json"] if as_json else [])]
    full = {k: v for k, v in os.environ.items() if not k.startswith(("META", "NO_COLOR"))}
    full.update(env)
    full.update({"META": "1", "META_CENTRE": "platform", "META_VERB": verb, "META_TIMEOUT": "20"})
    if as_json:
        full["META_JSON"] = "1"
    Path(full["META_CACHE_DIR"]).mkdir(mode=0o700, exist_ok=True)
    return subprocess.run(
        argv, check=False, env=full, capture_output=True, text=True, timeout=30, preexec_fn=lambda: os.close(0)
    )


def check_plain(run: subprocess.CompletedProcess[str]) -> None:
    for line in run.stdout.splitlines():
        assert len(line) <= 100, line
        assert "\033" not in line, "colour without a terminal"
    for line in run.stderr.splitlines():
        assert line.startswith("meta platform: "), line


# ---------------------------------------------------------------- the manifest


def test_module_is_an_executable_outside_template() -> None:
    assert MODULE.is_file()
    assert stat.S_IMODE(MODULE.stat().st_mode) == 0o755
    assert MODULE.read_text().startswith("#!/usr/bin/env python3\n")
    assert not (ROOT / "template/meta").exists()


def test_manifest_follows_record_0019() -> None:
    m = manifest()
    assert m["meta"] == 1
    assert m["centre"] == "platform"
    assert m["owner"] == "platform-coordinator"
    assert isinstance(m["summary"], str) and m["summary"]
    assert isinstance(m["results"], list) and all(isinstance(r, int) for r in m["results"])
    assert m["results"] == [1, 5]
    assert set(m["verbs"]) == {"status", "list", "show", "releases"}
    for name, verb in m["verbs"].items():
        assert isinstance(verb["summary"], str) and verb["summary"], name
        assert isinstance(verb["cache"], int) and not isinstance(verb["cache"], bool), name
        assert 60 <= verb["cache"] <= 900, name
        assert verb.get("writes", False) is False, name
        assert not verb.get("interactive", False), name
        complete = verb.get("complete")
        if isinstance(complete, str):
            assert complete.split()[0] in m["verbs"], name
        else:
            assert complete is None or isinstance(complete, list), name
    assert m["verbs"]["list"]["complete"] == ["templates", "updates", "releases"]


# ---------------------------------------------------------------- every verb through the fake core


@pytest.mark.parametrize("call", CALLS, ids=" ".join)
def test_verb_plain(call: list[str], gh: dict[str, str]) -> None:
    run = core(call[0], call[1:], gh)
    assert run.returncode == 0, run.stderr
    check_plain(run)


@pytest.mark.parametrize("call", CALLS, ids=" ".join)
def test_verb_json_is_one_value(call: list[str], gh: dict[str, str]) -> None:
    run = core(call[0], call[1:], gh, as_json=True)
    assert run.returncode == 0, run.stderr
    data = json.loads(run.stdout)  # exactly one value: trailing text fails to parse
    if call[0] == "status":
        assert set(data) == {"summary", "state", "checks"}
        assert data["state"] in STATES
        for check in data["checks"]:
            assert {"name", "state", "detail"} <= set(check) <= {"name", "state", "detail", "since"}
            assert check["state"] in STATES
    elif call[0] in ("list", "releases"):
        assert isinstance(data, list)
        assert all(isinstance(row, dict) and "name" in row for row in data)
        if call[0] == "list":
            assert [row["name"] for row in data] == sorted(row["name"] for row in data)
    else:
        assert isinstance(data, dict) and data["name"].startswith("template-")


def test_status_all_ok(gh: dict[str, str]) -> None:
    run = core("status", [], gh)
    assert run.returncode == 0
    first, *checks = run.stdout.splitlines()
    assert first.startswith("ok ") and "platform:" in first
    assert len(checks) == 8  # seven templates and the repos behind
    assert "release 1.0.3 open" in run.stdout


def test_lists(gh: dict[str, str]) -> None:
    names = core("list", ["templates"], gh).stdout.split()
    assert names == sorted(
        f"template-{t}" for t in ("base", "obsidian", "python", "typescript", "container", "actors", "go")
    )
    assert core("list", ["updates"], gh).stdout.split() == ["andronics/example-project#150"]
    assert core("list", ["releases"], gh).stdout.split() == ["andronics/template-go#31"]


def test_show_gives_key_value_lines(gh: dict[str, str]) -> None:
    lines = core("show", ["go"], gh).stdout.splitlines()
    head = dict(line.split(": ", 1) for line in lines[: lines.index("")])
    assert head["name"] == "template-go"
    assert head["latest release"] == "v1.0.2"
    assert head["ci on main"].startswith("passing")
    assert head["release pr"] == "#31"
    assert head["release version"] == "1.0.3"


def test_releases_newest_first(gh: dict[str, str]) -> None:
    rows = json.loads(core("releases", ["--since", "2026-11-01"], gh, as_json=True).stdout)
    published = [row["published"] for row in rows]
    assert published and published == sorted(published, reverse=True)
    assert all(p >= "2026-11-01" for p in published)


def test_help(gh: dict[str, str]) -> None:
    for argv in (["--help"], ["status", "--help"]):
        run = subprocess.run([str(MODULE), *argv], check=False, capture_output=True, text=True)
        assert run.returncode == 0
        assert all(verb in run.stdout for verb in ("status", "list", "show", "releases"))


def test_reads_only_through_one_graphql_query(gh: dict[str, str]) -> None:
    for call in CALLS:
        core(call[0], call[1:], gh)
    calls = [json.loads(line) for line in Path(gh["FAKE_GH_LOG"]).read_text().splitlines()]
    assert calls
    for argv in calls:
        assert argv[:2] == ["api", "graphql"]
        query = next(a for a in argv if a.startswith("query="))
        assert "mutation" not in query


# ---------------------------------------------------------------- planted defects


def test_failing_ci_fails_status(gh: dict[str, str]) -> None:
    gh["FAKE_GH_FIXTURE"] = str(FIXTURES / "failing.json")
    run = core("status", [], gh, as_json=True)
    assert run.returncode == 1
    data = json.loads(run.stdout)
    assert data["state"] == "fail"
    failed = [c for c in data["checks"] if c["state"] == "fail"]
    assert [c["name"] for c in failed] == ["template-python"]
    assert "since" in failed[0]
    plain = core("status", [], gh)
    assert plain.returncode == 1
    assert plain.stdout.startswith("fail ")


def test_repos_long_behind_warn(gh: dict[str, str]) -> None:
    gh["FAKE_GH_FIXTURE"] = str(FIXTURES / "behind.json")
    run = core("status", [], gh, as_json=True)
    assert run.returncode == 1
    updates = next(c for c in json.loads(run.stdout)["checks"] if c["name"] == "updates")
    assert updates["state"] == "warn"
    assert "example-project" in updates["detail"]


@pytest.mark.parametrize("call", [c for c in CALLS if c != ["list", "templates"]], ids=" ".join)
def test_gh_failing_exits_4(call: list[str], gh: dict[str, str]) -> None:
    gh["FAKE_GH_FAIL"] = "1"
    for as_json in (False, True):
        run = core(call[0], call[1:], gh, as_json=as_json)
        assert run.returncode == 4, run.stderr
        assert run.stdout == ""
        assert run.stderr.startswith("meta platform: ")
        assert TOKEN not in run.stderr


def test_gh_missing_exits_4(gh: dict[str, str], tmp_path: Path) -> None:
    no_gh = tmp_path / "no-gh"  # python3 for the shebang, and no gh
    no_gh.mkdir()
    (no_gh / "python3").symlink_to(sys.executable)
    gh["PATH"] = str(no_gh)
    run = core("status", [], gh)
    assert run.returncode == 4
    assert "gh" in run.stderr


@pytest.mark.parametrize(
    ("args", "code"),
    [
        (["show", "nosuch"], 5),
        (["list", "nosuch"], 2),
        (["list"], 2),
        (["shwo", "base"], 2),
        (["status", "extra"], 2),
        (["status", "--bogus"], 2),
        (["releases", "--since", "last tuesday"], 2),
        (["releases", "--since"], 2),
    ],
    ids=lambda v: " ".join(v) if isinstance(v, list) else str(v),
)
def test_usage_and_not_found(args: list[str], code: int, gh: dict[str, str]) -> None:
    run = core(args[0], args[1:], gh)
    assert run.returncode == code
    assert run.stdout == ""
    check_plain(run)


def test_no_verb_is_usage() -> None:
    assert subprocess.run([str(MODULE)], check=False, capture_output=True, text=True).returncode == 2


def test_token_never_reaches_output(gh: dict[str, str]) -> None:
    gh["FAKE_GH_FIXTURE"] = str(FIXTURES / "secret.json")
    seen = ""
    for call in CALLS:
        for as_json in (False, True):
            run = core(call[0], call[1:], gh, as_json=as_json)
            assert run.returncode in (0, 1), run.stderr
            seen += run.stdout + run.stderr
    assert TOKEN not in seen
    assert TOKEN[:12] not in seen
    assert "[redacted]" in seen  # the planted token was there to find
