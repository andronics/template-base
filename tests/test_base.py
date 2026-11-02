"""Render template-base with a stub stack overlay, and with template-obsidian, and check the results.

    uv run pytest                 # every test
    uv run pytest -m docker       # also the secret scan through Docker

Each render is a project as `copier copy` of base and then one stack overlay would create
it, and it must pass its own Definition of done (`sh scripts/checks.sh`) unchanged.
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
from stacking import ROOT, checks, commit, copy, sh, sibling, stage


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
    assert questions == {"project_name", "description", "github_owner", "code_owners", "copyright_holder",
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
    pr = next(s for s in update["steps"] if "create-pull-request" in s.get("uses", ""))
    assert pr["with"]["branch"] == "chore/${{ env.TEMPLATE }}-update"


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


def edit_hook(project: Path, file_path: str) -> subprocess.CompletedProcess[str]:
    event = json.dumps({"cwd": str(project), "tool_input": {"file_path": file_path}})
    return subprocess.run(["python3", "scripts/repo-boundary.py"], cwd=project, input=event, capture_output=True,
                          text=True, env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(project)})  # fmt: skip


def test_edits_stay_in_the_repository(project: Path) -> None:
    cases = {"src/new.txt": 0, str(project / "README.md"): 0, f"{tempfile.gettempdir()}/scratch.txt": 0,
             str(Path.home() / "elsewhere/repo/file.txt"): 2}  # fmt: skip
    assert {p: edit_hook(project, p).returncode for p in cases} == cases


def test_scripts_pass_a_stacks_ruff() -> None:
    """Base's Python scripts pass a code project's ruff at 100 columns (issue #6). None is a .jinja
    file, so the source is what projects get; a conditional name is matched without its `[% %]`."""
    scripts = [str(p) for p in (ROOT / "template/scripts").iterdir()
               if re.sub(r"\[%.*?%\]", "", p.name).endswith(".py")]  # fmt: skip
    assert len(scripts) >= 4
    ruff = (sys.executable, "-m", "ruff")
    sh(*ruff, "check", "--isolated", "--no-cache", "--line-length", "100", "--select", "E501", *scripts, cwd=ROOT)
    sh(*ruff, "format", "--isolated", "--no-cache", "--check", "--line-length", "100", *scripts, cwd=ROOT)


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

