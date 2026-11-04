"""Render template-base with a stub stack overlay, and with each real overlay, and check the results.

    uv run pytest                 # every test
    uv run pytest -m docker       # also the secret scan through Docker

Each render is a project as `copier copy` of base and then one stack overlay (and any feature
overlay) would create it, and it must pass its own Definition of done (`sh scripts/checks.sh`) unchanged.
The real overlays are sibling checkouts (../template-<name> or $TEMPLATE_<NAME>), skipped when missing.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml
from conftest import BASE
from stacking import ROOT, checks, commit, copy, project_env, sh, sibling, stage


def test_base_names_no_overlay() -> None:
    """Base never names an overlay: no stack, language or kind switch anywhere (decision 0001).
    This replaces project-template's tests/test_layers.py."""
    names = re.compile(r"\b(obsidian|typescript|python|vault|brain|layers?)\b|language ==|kind ==|\blanguage\b")
    files = [ROOT / "copier.yml", *(p for p in (ROOT / "template").rglob("*") if p.is_file())]
    hits = [f"{p.relative_to(ROOT)}:{n}: {line.strip()}" for p in files
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if names.search(line) and "specific language governing" not in line]  # fmt: skip
    assert hits == []


def test_base_asks_only_identity_questions() -> None:
    questions = {k for k, v in yaml.safe_load((ROOT / "copier.yml").read_text()).items()
                 if not k.startswith("_") and v.get("when") is not False and v.get("ask") is not False}  # fmt: skip
    assert questions == {"project_name", "description", "github_owner", "owner_is_org", "code_owners", "copyright_holder",
                         "license", "dependabot_automerge", "personal_data_guard"}  # fmt: skip


def test_checks_pass(project: Path) -> None:
    result = checks(project)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == ["00-base OK", "20-stub OK"]


def test_answers_files(project: Path) -> None:
    assert (project / ".copier-answers.base.yml").is_file()
    assert (project / ".copier-answers.stack-stub.yml").is_file()
    assert not (project / ".copier-answers.yml").exists()
    base = yaml.safe_load((project / ".copier-answers.base.yml").read_text())
    assert base["_commit"] == "v1.0.0" and base["project_name"] == "demo"


def test_no_unrendered_jinja(project: Path) -> None:
    leftovers = []
    for path in project.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        if re.search(r"\[\[|\[%|\.jinja$", path.name) or re.search(r"\[\[ |\[% ", path.read_text(errors="ignore")):
            leftovers.append(str(path))
    assert not leftovers


HEADROOM = 0.75  # the skeleton may use at most 75% of each budget, leaving room for the project


def budget(project: Path) -> dict[tuple[str, ...], int]:
    spec = importlib.util.spec_from_file_location("base_contract", project / "scripts/base-contract.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BUDGET  # type: ignore[no-any-return]


def test_always_loaded_files_leave_headroom(project: Path) -> None:
    over = {}
    for names, limit in budget(project).items():
        size = sum(len((project / n).read_text()) for n in names if (project / n).is_file())
        if size > limit * HEADROOM:
            over[names] = (size, int(limit * HEADROOM))
    assert not over, f"skeleton uses too much of the context budget (chars, allowed): {over}"


def test_template_problems_are_reported(project: Path) -> None:
    """A project that finds a template bug reports it to the template that owns the file."""
    agents = (project / "AGENTS.md").read_text()
    assert "`_src_path` in its `.copier-answers.*.yml`" in agents
    assert "gh issue list -R <owner/repo> --state all" in agents
    assert "Template problem found?" in (project / ".github/pull_request_template.md").read_text()


def test_agents_point_at_the_stack(project: Path) -> None:
    assert "@.agents/stack.md" in (project / "CLAUDE.md").read_text()
    assert "@./.agents/stack.md" in (project / "GEMINI.md").read_text()
    assert ".agents/stack.md" in (project / ".cursor/rules/project.mdc").read_text()
    assert ".agents/stack.md" in (project / "AGENTS.md").read_text()
    assert "Every other `gh` command is allowed." in (project / "AGENTS.md").read_text()


def test_ci_has_one_required_check(project: Path) -> None:
    """`ci` gathers every job, the stack's included: the one required check (decision 0001)."""
    jobs = yaml.safe_load((project / ".github/workflows/base-ci.yml").read_text())["jobs"]
    assert jobs["stack"]["uses"] == "./.github/workflows/stack-ci.yml"
    assert jobs["ci"]["name"] == "ci" and jobs["ci"]["if"] == "always()"
    assert set(jobs["ci"]["needs"]) == set(jobs) - {"ci", "metadata"}
    assert "sh scripts/checks.sh" in json.dumps(jobs["checks"])


@pytest.mark.parametrize(("owner", "is_org", "owners"), [("metalayerlab", True, "@metalayerlab/maintainers"),
                                                          ("andronics", False, "@andronics")])  # fmt: skip
def test_code_owners_default(base_src: Path, tmp_path: Path, owner: str, is_org: bool, owners: str) -> None:
    """An organisation's CODEOWNERS names its maintainers team; a personal account has no teams (0003)."""
    copy(base_src, tmp_path, {**BASE, "github_owner": owner, "owner_is_org": is_org})
    rules = [line.split() for line in (tmp_path / ".github/CODEOWNERS").read_text().splitlines()
             if line and not line.startswith("#")]  # fmt: skip
    assert rules == [["*", owners], ["/.github/workflows/", owners]]


@pytest.mark.parametrize(("owner", "owners", "is_org"), [("andronics", "@andronics", False),
                                                          ("Andronics", "@andronics @someone", False),
                                                          ("metalayerlab", "@metalayerlab/maintainers", True),
                                                          ("metalayerlab", "@alice @bob", True)])  # fmt: skip
def test_owner_is_org_follows_a_given_code_owners(base_src: Path, tmp_path: Path, owner: str, owners: str,
                                                  is_org: bool) -> None:  # fmt: skip
    """`-d code_owners=@owner` means a personal account: an organisation can't be a code owner (0005)."""
    copy(base_src, tmp_path, {**BASE, "github_owner": owner, "code_owners": owners})
    recorded = yaml.safe_load((tmp_path / ".copier-answers.base.yml").read_text())
    assert recorded["owner_is_org"] is is_org


@pytest.mark.parametrize("data", [{"owner_is_org": True, "code_owners": "@andronics"},
                                  {"owner_is_org": True, "code_owners": "@andronics/maintainers @Andronics"}])  # fmt: skip
def test_owner_is_org_contradicting_code_owners_fails(base_src: Path, tmp_path: Path, data: dict[str, object]) -> None:
    """Never recorded, so a later update's replay of this version can't fail on it (0005)."""
    with pytest.raises(ValueError, match="personal account, not an organisation"):
        copy(base_src, tmp_path, {**BASE, "github_owner": "andronics", **data})


def test_dependabot_automerge_is_opt_in(base_src: Path, tmp_path: Path) -> None:
    for answer, present in (("off", False), ("patch", True)):
        dst = tmp_path / answer
        copy(base_src, dst, {**BASE, "dependabot_automerge": answer})
        assert (dst / ".github/workflows/base-dependabot-automerge.yml").exists() == present


def test_actions_are_pinned(project: Path) -> None:
    uses = [line.strip() for f in (project / ".github/workflows").glob("*.yml")
            for line in f.read_text().splitlines() if re.match(r"\s*(- )?uses: ", line)]  # fmt: skip
    pin = re.compile(r"^(- )?uses: (\./\S+|[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d\S*)$")
    assert uses and [u for u in uses if not pin.match(u)] == []


def test_labels_are_created(project: Path) -> None:
    text = "\n".join(f.read_text() for f in (project / ".github/workflows").glob("*.yml"))
    used = {n for g in re.findall(r"--label ([\w-]+)|^\s+labels: ([\w-]+)", text, re.M) for n in g if n}
    assert "template-update" in used and used <= set(re.findall(r"gh label create ([\w-]+)", text))


def plan_order(project: Path, names: list[str]) -> list[str]:
    run = yaml.safe_load((project / ".github/workflows/template-update.yml").read_text())
    script = next(s["run"] for s in run["jobs"]["plan"]["steps"] if s.get("id") == "order")
    with tempfile.TemporaryDirectory() as tmp:
        for name in names:
            (Path(tmp) / name).write_text("x\n")
        out = Path(tmp) / "out"
        subprocess.run(["bash", "-c", script], cwd=tmp, check=True, env={"GITHUB_OUTPUT": str(out), "PATH": "/usr/bin:/bin"})
        return json.loads(out.read_text().removeprefix("templates="))


def test_template_update_order(project: Path) -> None:
    """Base first, then the stack overlay, then feature overlays by name; one PR each."""
    names = [".copier-answers.zeta.yml", ".copier-answers.stack-x.yml", ".copier-answers.alpha.yml",
             ".copier-answers.base.yml"]  # fmt: skip
    assert plan_order(project, names) == [".copier-answers.base.yml", ".copier-answers.stack-x.yml",
                                          ".copier-answers.alpha.yml", ".copier-answers.zeta.yml"]  # fmt: skip
    flow = yaml.safe_load((project / ".github/workflows/template-update.yml").read_text())
    update = flow["jobs"]["update"]
    assert update["strategy"]["max-parallel"] == 1
    steps = "\n".join(json.dumps(s) for s in update["steps"])
    assert "--skip-tasks" in steps and "sh scripts/post-update.sh" in steps
    assert steps.index("copier update -a") < steps.index("sh scripts/post-update.sh")
    # Unmerged paths block create-pull-request's checkout (issue #33).
    assert steps.index("sh scripts/post-update.sh") < steps.index("sh scripts/stage-conflicts.sh")
    assert steps.index("sh scripts/stage-conflicts.sh") < steps.index("create-pull-request")
    pr = next(s for s in update["steps"] if "create-pull-request" in s.get("uses", ""))
    assert pr["with"]["branch"] == "chore/${{ env.TEMPLATE }}-update"


TOKEN = "${{ steps.workflows-app.outputs.token || steps.release-app.outputs.token || github.token }}"


def update_steps(project: Path) -> list[dict]:
    return yaml.safe_load((project / ".github/workflows/template-update.yml").read_text())["jobs"]["update"]["steps"]


def minted(steps: list[dict], variables: dict[str, str]) -> set[str]:
    """The App-token steps that run with these repository variables set.

    An `if:` is `&&` of terms, each `vars.X == ''`, `vars.X != ''` or `(vars.X != '' || vars.Y != '')`.
    """

    def term(text: str) -> bool:
        alts = re.findall(r"vars\.(\w+) (==|!=) ''", text)
        assert alts and len(alts) == text.count("vars."), text
        return any((variables.get(name, "") != "") == (op == "!=") for name, op in alts)

    def holds(cond: str) -> bool:
        return all(term(t) for t in cond.split(" && "))

    return {s["id"] for s in steps if "create-github-app-token" in s.get("uses", "") and holds(s["if"])}


def pusher(steps: list[dict], ran: set[str]) -> str:
    """Evaluate the PUSHER expression: `steps.X.outcome == 'success' && 'x' || ... || 'fallback'`."""
    step = next(s for s in steps if s.get("name") == "Can the token push this update?")
    expr = step["env"]["PUSHER"]
    for sid, value in re.findall(r"steps\.([\w-]+)\.outcome == 'success' && '([\w-]+)'", expr):
        if sid in ran:
            return value
    return re.search(r"\|\| '([\w-]+)' }}$", expr).group(1)


def test_template_update_token_order(project: Path) -> None:
    """The update role's App (with workflows) first, else the release role's, else GITHUB_TOKEN (#36, 0004).

    The update role reads UPDATE_APP_* and, for one release cycle, the legacy PIN_BUMP_APP_* (TODO.md).
    """
    steps = update_steps(project)
    apps = {s["id"]: s for s in steps if "create-github-app-token" in s.get("uses", "")}
    assert list(apps) == ["workflows-app", "release-app"]
    update, release = apps["workflows-app"]["with"], apps["release-app"]["with"]
    assert update["client-id"] == "${{ vars.UPDATE_APP_CLIENT_ID || vars.PIN_BUMP_APP_CLIENT_ID }}"
    assert update["private-key"] == ("${{ vars.UPDATE_APP_CLIENT_ID != '' && secrets.UPDATE_APP_PRIVATE_KEY"
                                     " || secrets.PIN_BUMP_APP_PRIVATE_KEY }}")  # fmt: skip
    assert release["client-id"] == "${{ vars.RELEASE_APP_CLIENT_ID }}"
    assert release["private-key"] == "${{ secrets.RELEASE_APP_PRIVATE_KEY }}"
    # Least privilege (0004): owner and permissions always; the release role never gets workflows (0002).
    def permissions(given: dict[str, str]) -> set[str]:
        assert all(v == "write" for k, v in given.items() if k.startswith("permission-"))
        return {k.removeprefix("permission-") for k in given if k.startswith("permission-")}

    assert permissions(update) == {"contents", "pull-requests", "workflows"}
    assert permissions(release) == {"contents", "pull-requests"}
    assert update["owner"] == release["owner"] == "${{ github.repository_owner }}"
    # Every token the job pushes or reads templates with is the same preference chain.
    tokens = [v for s in steps for k, v in {**s.get("with", {}), **s.get("env", {})}.items() if k.lower() == "token"]
    assert len(tokens) == 3 and set(tokens) == {TOKEN}
    cases = [({"UPDATE_APP_CLIENT_ID": "1", "PIN_BUMP_APP_CLIENT_ID": "0", "RELEASE_APP_CLIENT_ID": "2"},
              {"workflows-app"}, "workflows-app"),
             ({"UPDATE_APP_CLIENT_ID": "1"}, {"workflows-app"}, "workflows-app"),
             ({"PIN_BUMP_APP_CLIENT_ID": "0", "RELEASE_APP_CLIENT_ID": "2"}, {"workflows-app"}, "workflows-app"),
             ({"RELEASE_APP_CLIENT_ID": "2"}, {"release-app"}, "release-app"),
             ({}, set(), "github-token")]  # fmt: skip
    for variables, apps_run, who in cases:
        assert minted(steps, variables) == apps_run, variables
        assert pusher(steps, apps_run) == who, variables


def run_push_check(project: Path, tmp_path: Path, who: str, touch: str) -> dict[str, str]:
    """Run the 'Can the token push' step in a copy of the project with one file changed; return what it set."""
    step = next(s for s in update_steps(project) if s.get("name") == "Can the token push this update?")
    dst = tmp_path / f"{who}-{touch.replace('/', '_')}"
    shutil.copytree(project, dst)
    (dst / touch).parent.mkdir(parents=True, exist_ok=True)
    (dst / touch).write_text("changed\n")
    env_file = tmp_path / f"{dst.name}.env"
    env_file.write_text("")
    subprocess.run(["bash", "-e", "-c", step["run"]], cwd=dst, check=True, capture_output=True,
                   env=project_env({"PUSHER": who, "GITHUB_ENV": str(env_file)}))  # fmt: skip
    return dict(line.split("=", 1) for line in env_file.read_text().splitlines())


def test_template_update_routes_workflow_changes(project: Path, tmp_path: Path) -> None:
    """A workflow change goes to the 'run locally' issue unless the token is the App with workflows (issue #36)."""
    workflow, other = ".github/workflows/template-update.yml", "scripts/new.sh"
    for who in ("release-app", "github-token"):
        found = run_push_check(project, tmp_path, who, workflow)
        assert found.get("NEEDS_LOCAL") == "1" and ".github/workflows/" in found["WHY_LOCAL"], who
        assert run_push_check(project, tmp_path, who, ".github/workflows/new.yml").get("NEEDS_LOCAL") == "1", who
        assert run_push_check(project, tmp_path, who, other) == {}, who
    assert run_push_check(project, tmp_path, "workflows-app", workflow) == {}
    steps = update_steps(project)
    pr = next(s for s in steps if s.get("id") == "pr")
    assert pr["if"] == "env.NEEDS_LOCAL != '1'" and pr["continue-on-error"] is True
    # A refused push all the same leads to the same issue, not a red job.
    issue = next(s for s in steps if s.get("name") == "Ask for a local update")
    assert "UPDATE_APP_CLIENT_ID" in issue["run"] and "UPDATE_APP_PRIVATE_KEY" in issue["run"]
    assert issue["if"] == "env.NEEDS_LOCAL == '1' || steps.pr.outcome == 'failure'"
    assert steps.index(pr) < steps.index(issue) and "gh issue create" in issue["run"]
    names = [s.get("name") for s in steps]
    assert names.index("scripts/stage-conflicts.sh") < names.index("Can the token push this update?") < steps.index(pr)


def test_bootstrap_runs_on_copy_only() -> None:
    tasks = yaml.safe_load((ROOT / "copier.yml").read_text())["_tasks"]
    assert tasks and all(t.get("when") == "[[ _copier_operation == 'copy' ]]" for t in tasks)


def test_runners_run_drop_ins_in_order(project: Path, tmp_path: Path) -> None:
    dst = tmp_path / "p"
    shutil.copytree(project, dst)
    for folder, runner in (("post-update.d", "post-update.sh"), ("bootstrap.d", "bootstrap.sh")):
        (dst / "scripts" / folder).mkdir()
        for name in ("20-b.sh", "10-a.sh"):
            (dst / "scripts" / folder / name).write_text(f"echo {folder}/{name}\n")
        out = sh("sh", f"scripts/{runner}", cwd=dst).splitlines()
        assert out[:2] == [f"{folder}/10-a.sh", f"{folder}/20-b.sh"], out


def test_docs_secrets_without_docker(project: Path, tmp_path: Path) -> None:
    """Optional locally, never skipped in CI."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("bash", "dirname"):
        (bin_dir / tool).symlink_to(shutil.which(tool) or tool)
    for ci, code in (("", 0), ("true", 1)):
        result = subprocess.run([str(project / "scripts/check-docs-secrets.sh")], cwd=project, capture_output=True,
                                text=True, env={"PATH": str(bin_dir), "CI": ci})  # fmt: skip
        assert result.returncode == code, result.stdout + result.stderr


@pytest.mark.docker
def test_docs_secrets_with_docker(project: Path) -> None:
    assert sh("scripts/check-docs-secrets.sh", cwd=project).splitlines() == ["check-docs-secrets OK: gitleaks"]


@pytest.mark.docker
def test_docs_secrets_reads_the_projects_allow_list(project: Path, tmp_path: Path) -> None:
    """.gitleaks.toml extends .gitleaks.base.toml (decision 0006): the default rules, base's
    lock-file entry and the project's own entries all apply."""
    dst = tmp_path / "p"
    shutil.copytree(project, dst)
    token = "ghp_" + "aBcDeFgHiJkLmNoPqRsTuVwXyZ01234567"[::-1] + "89"
    (dst / "notes.md").write_text(f'token = "{token}"\n')
    (dst / "sub").mkdir()
    (dst / "sub/uv.lock").write_text(f'token = "{token[:-1]}0"\n')
    commit(dst)
    failed = subprocess.run(["scripts/check-docs-secrets.sh"], cwd=dst, capture_output=True, text=True, check=False)
    assert failed.returncode == 1 and "notes.md" in failed.stdout and "uv.lock" not in failed.stdout, failed.stdout
    with (dst / ".gitleaks.toml").open("a") as f:
        f.write(f'\n[[allowlists]]\ndescription = "a test token"\nregexes = ["{token}"]\n')
    commit(dst)
    assert sh("scripts/check-docs-secrets.sh", cwd=dst).splitlines() == ["check-docs-secrets OK: gitleaks"]


def edit_hook(project: Path, file_path: str) -> subprocess.CompletedProcess[str]:
    event = json.dumps({"cwd": str(project), "tool_input": {"file_path": file_path}})
    return subprocess.run(["python3", "scripts/repo-boundary.py"], cwd=project, input=event, capture_output=True,
                          text=True, env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(project)})  # fmt: skip


def test_edits_stay_in_the_repository(project: Path) -> None:
    cases = {"src/new.txt": 0, str(project / "README.md"): 0, f"{tempfile.gettempdir()}/scratch.txt": 0,
             str(Path.home() / "elsewhere/repo/file.txt"): 2}  # fmt: skip
    assert {p: edit_hook(project, p).returncode for p in cases} == cases


@pytest.mark.parametrize("target", ["py312", "py313", "py314"])
def test_scripts_pass_a_stacks_ruff(target: str) -> None:
    """Base's Python scripts pass a code project's ruff at 100 columns (issue #6), for every Python
    target a stack sets: py314 formats `except (A, B):` without its brackets (PEP 758). None is a
    .jinja file, so the source is what projects get; a conditional name is matched without its `[% %]`."""
    scripts = [str(p) for p in (ROOT / "template/scripts").iterdir()
               if re.sub(r"\[%.*?%\]", "", p.name).endswith(".py")]  # fmt: skip
    assert len(scripts) >= 4
    ruff = (sys.executable, "-m", "ruff")
    fixed = ("--isolated", "--no-cache", "--target-version", target, "--line-length", "100")
    sh(*ruff, "check", *fixed, "--select", "E501", *scripts, cwd=ROOT)
    sh(*ruff, "format", *fixed, "--check", *scripts, cwd=ROOT)


def test_workflows_lint(project: Path) -> None:
    if shutil.which("actionlint"):
        sh("actionlint", cwd=project)
    elif shutil.which("docker"):
        sh("docker", "run", "--rm", "-v", f"{project}:/repo", "-w", "/repo", "rhysd/actionlint:1.7.12", cwd=project)
    else:
        pytest.skip("neither actionlint nor docker available")


def test_base_plus_obsidian(base_release: Path, tmp_path: Path) -> None:
    """Base with the latest template-obsidian (../template-obsidian or $TEMPLATE_OBSIDIAN) passes its checks."""
    obsidian = sibling("template-obsidian", "TEMPLATE_OBSIDIAN")
    if obsidian is None:
        pytest.skip("template-obsidian is not checked out next to this repository")
    dst = tmp_path / "brain"
    copy(base_release, dst, BASE)
    copy(stage(obsidian, tmp_path / "template-obsidian"), dst, {"vault_dir": "knowledge", "brain_pull": True})
    result = checks(commit(dst))
    assert result.returncode == 0, result.stdout + result.stderr


def test_projects_run_without_the_runners_github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Base's own CI env never reaches a rendered project: on its release PR, GITHUB_HEAD_REF made
    the code overlays' checks run check-wiki.py --strict on a fresh render."""
    monkeypatch.setenv("GITHUB_HEAD_REF", "release-please--x")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("CI", "true")
    env = project_env({"UV_LINK_MODE": "symlink"})
    assert not [k for k in env if k.startswith("GITHUB_")]
    assert env["CI"] == "true" and env["UV_LINK_MODE"] == "symlink" and "PATH" in env


# The code overlays: a stack with these answers, then template-container with its own when they're
# given. A stack's defaults build an image and name docker and k8s, so they take template-container.
CODE: dict[str, tuple[str, dict[str, object], dict[str, object] | None]] = {
    "python": ("python", {}, {}),
    "python-cli": ("python", {"kind": "cli", "container_image": False}, None),
    "typescript": ("typescript", {}, {}),
    "typescript-cli": ("typescript", {"kind": "cli", "container_image": False}, None),
}  # fmt: skip
# Each stack's Definition of done after checks.sh, as its stack-ci.yml runs it: its linters read base's files.
DOD = {
    "python": [("uv", "sync", "--locked", "--quiet"), ("uv", "run", "ruff", "check"),
               ("uv", "run", "ruff", "format", "--check"), ("uv", "run", "mypy"),
               ("uv", "run", "pytest", "-p", "no:cacheprovider")],
    "typescript": [("npm", "ci", "--no-audit", "--no-fund", "--loglevel=error"), ("npm", "run", "lint"),
                   ("npm", "run", "format:check"), ("npm", "run", "typecheck"), ("npm", "test")],
}  # fmt: skip
# As in the overlays' own tests: venvs link uv's cache.
CODE_ENV = {"UV_LINK_MODE": "symlink"}


@pytest.mark.parametrize("render", list(CODE))
def test_base_plus_code_overlay(render: str, base_release: Path, tmp_path: Path) -> None:
    """Base with the latest code overlays passes their checks, manifest check and stack Definition of done."""
    stack, answers, container = CODE[render]
    overlays = [(f"template-{stack}", answers), *([("template-container", container)] if container is not None else [])]
    found = {name: sibling(name, f"TEMPLATE_{name.removeprefix('template-').upper()}") for name, _ in overlays}
    if missing := [name for name, path in found.items() if path is None]:
        pytest.skip(f"{', '.join(missing)} not checked out next to this repository")
    dst = tmp_path / "demo"
    copy(base_release, dst, BASE)
    for name, data in overlays:
        copy(stage(found[name], tmp_path / name), dst, data)  # type: ignore[arg-type]
    sh("sh", "scripts/bootstrap.sh", cwd=dst, env=CODE_ENV)
    result = checks(commit(dst), env=CODE_ENV)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[-1] == f"20-{stack} OK", result.stdout
    manifests = [("bash", "scripts/check-manifests.sh")] if (dst / "scripts/check-manifests.sh").is_file() else []
    for cmd in [*DOD[stack], *manifests]:
        result = subprocess.run(cmd, cwd=dst, capture_output=True, text=True, env=project_env(CODE_ENV))
        assert result.returncode == 0, f"{' '.join(cmd)}:\n{result.stdout}\n{result.stderr}"
