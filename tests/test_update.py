"""`copier update` of a stacked project: base's own, and the stack overlay's (issue #10).

Copier replays the old and new template versions into empty directories, without
`.copier-answers.base.yml`, so an overlay reads base's answers from the `base_answers` copy it
records in its own answers file (decision 0001). The stub stack overlay follows that pattern;
these tests break if a contract change stops it working.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from conftest import BASE, STUB
from stacking import GIT, ROOT, checks, commit, copy, project_env, sh, stage

EDIT = "A line the project added.\n"


def release(src: Path, tag: str, path: str, old: str, new: str) -> None:
    """Change one template file in a staged copy, commit it and tag `tag`."""
    file = src / path
    text = file.read_text()
    assert old in text, f"{path} lacks {old!r}"
    file.write_text(text.replace(old, new))
    sh(*GIT, "commit", "-qam", tag, cwd=src)
    sh("git", "tag", tag, cwd=src)


def update(project: Path, answers: str, *args: str) -> None:
    """As template-update.yml runs it."""
    sh(sys.executable, "-m", "copier", "update", "-a", answers, "--trust", "--skip-tasks", "--defaults",
       "--conflict", "inline", *args, cwd=project)  # fmt: skip


def stacked(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Base and the stub overlay at v1.0.0, copied, committed, then a project edit committed."""
    base = stage(ROOT, tmp_path / "template-base")
    stub = stage(STUB, tmp_path / "template-stub")
    project = tmp_path / "demo"
    copy(base, project, BASE)
    copy(stub, project, {})
    commit(project)
    with (project / "README.md").open("a") as f:
        f.write(f"\n{EDIT}")
    commit(project)
    return base, stub, project


def assert_clean(project: Path) -> None:
    tracked = sh("git", "ls-files", "--others", "--cached", "--exclude-standard", cwd=project).splitlines()
    marker = re.compile(r"^(<{7}|>{7}) ", re.M)
    marked = [n for n in tracked if (project / n).is_file() and marker.search((project / n).read_text(errors="ignore"))]
    assert marked == [], f"conflict markers in {marked}"
    assert not list(project.rglob("*.rej"))
    result = checks(commit(project))
    assert result.returncode == 0, result.stdout + result.stderr


def answers(project: Path, name: str) -> dict[str, object]:
    return yaml.safe_load((project / f".copier-answers.{name}.yml").read_text())  # type: ignore[no-any-return]


def test_overlay_update_keeps_base_answers(tmp_path: Path) -> None:
    """Stub v1.0.0 -> v1.1.0: base's values stay, the project's edit survives, no conflicts."""
    _, stub, project = stacked(tmp_path)
    release(stub, "v1.1.0", "template/.github/ISSUE_TEMPLATE/config.yml.jinja", "never in a public issue",
            "never in a public issue of [[ base_answers.project_name ]]")  # fmt: skip
    update(project, ".copier-answers.stack-stub.yml")

    config = (project / ".github/ISSUE_TEMPLATE/config.yml").read_text()
    assert "https://github.com/metalayerlab/demo/security/advisories/new" in config
    assert "never in a public issue of demo" in config
    readme = (project / "README.md").read_text()
    assert readme.startswith("# demo\n\nA demo project\n"), readme
    assert EDIT in readme
    stub_answers = answers(project, "stack-stub")
    assert stub_answers["_commit"] == "v1.1.0"
    assert stub_answers["base_answers"]["project_name"] == "demo"  # type: ignore[index]
    assert_clean(project)


def test_base_update_then_overlay_update(tmp_path: Path) -> None:
    """Base v1.0.0 -> v1.0.1 with a changed answer, then the overlay: the new answer reaches both."""
    base, stub, project = stacked(tmp_path)
    release(base, "v1.0.1", "template/CLAUDE.md.jinja", "@AGENTS.md", "@AGENTS.md\n")
    update(project, ".copier-answers.base.yml", "-d", "description=A changed description")
    assert answers(project, "base")["_commit"] == "v1.0.1"
    assert answers(project, "base")["description"] == "A changed description"
    assert_clean(project)

    release(stub, "v1.1.0", "template/scripts/checks.d/20-[[ stub_name ]].sh.jinja", "only check", "one check")
    update(project, ".copier-answers.stack-stub.yml")
    readme = (project / "README.md").read_text()
    assert readme.startswith("# demo\n\nA changed description\n"), readme
    assert EDIT in readme
    assert answers(project, "stack-stub")["base_answers"]["description"] == "A changed description"  # type: ignore[index]
    assert_clean(project)


def test_recopy_migrates_a_project_from_before_base_answers(tmp_path: Path) -> None:
    """Stub v1.0.0 reads _external_data directly: update fails, recopy once, then updates work."""
    base = stage(ROOT, tmp_path / "template-base")
    stub = stage(STUB, tmp_path / "template-stub", tag="v1.1.0")
    sh("git", "switch", "-qc", "before-fix", cwd=stub)
    config = stub / "copier.yml"
    old = re.sub(r"\nbase_answers:\n(  .*\n)+", "\n", config.read_text())
    config.write_text(old.replace("(_external_data.base or base_answers | default({}))", "_external_data.base"))
    for name in ("README.md.jinja", ".github/ISSUE_TEMPLATE/config.yml.jinja"):
        file = stub / "template" / name
        file.write_text(file.read_text().replace("base_answers.", "_external_data.base."))
    sh(*GIT, "commit", "-qam", "v1.0.0", cwd=stub)
    sh("git", "tag", "v1.0.0", cwd=stub)
    sh("git", "switch", "-q", "main", cwd=stub)
    project = tmp_path / "demo"
    copy(base, project, BASE)
    copy(stub, project, {}, vcs_ref="v1.0.0")
    commit(project)
    assert "base_answers" not in answers(project, "stack-stub")

    failed = subprocess.run([sys.executable, "-m", "copier", "update", "-a", ".copier-answers.stack-stub.yml",
                             "--trust", "--skip-tasks", "--defaults", "--conflict", "inline"],
                            cwd=project, capture_output=True, text=True, check=False, env=project_env())  # fmt: skip
    assert failed.returncode != 0 and "needs template-base first" in failed.stderr, failed.stderr
    sh("git", "reset", "-q", "--hard", cwd=project)
    sh("git", "clean", "-qfd", cwd=project)
    sh(sys.executable, "-m", "copier", "recopy", "-a", ".copier-answers.stack-stub.yml", "--trust",
       "--skip-tasks", "--defaults", "--overwrite", cwd=project)  # fmt: skip
    assert answers(project, "stack-stub")["_commit"] == "v1.1.0"
    assert answers(project, "stack-stub")["base_answers"]["project_name"] == "demo"  # type: ignore[index]
    commit(project)

    release(stub, "v1.2.0", "template/scripts/checks.d/20-[[ stub_name ]].sh.jinja", "only check", "one check")
    update(project, ".copier-answers.stack-stub.yml")
    assert answers(project, "stack-stub")["_commit"] == "v1.2.0"
    assert (project / "README.md").read_text().startswith("# demo\n\nA demo project\n")
    assert_clean(project)


def test_recopy_message(tmp_path: Path) -> None:
    """A recopy prints the copy message (issue #26): it must not tell an existing project to copy its overlay."""
    _, _, project = stacked(tmp_path)
    recopy = subprocess.run([sys.executable, "-m", "copier", "recopy", "-a", ".copier-answers.base.yml", "--trust",
                             "--skip-tasks", "--defaults", "--overwrite"],
                            cwd=project, capture_output=True, text=True, check=True, env=project_env())  # fmt: skip
    lines = recopy.stderr.splitlines()
    assert any(line.strip().startswith("A recopy: run sh scripts/post-update.sh") for line in lines), recopy.stderr
    assert all(line.strip().startswith("A new project:") for line in lines if "copier copy" in line), recopy.stderr


def test_a_pin_the_project_bumped_first(tmp_path: Path) -> None:
    """Dependabot bumps a pin in a template-owned workflow; then base carries the same bump (decision 0002).
    The update merges the two identical changes: no conflict, and the project's edit is gone."""
    old = "astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3"
    new = "astral-sh/setup-uv@0123456789abcdef0123456789abcdef01234567 # v10.3.4"
    base, _, project = stacked(tmp_path)
    workflow = project / ".github/workflows/base-ci.yml"
    assert old in workflow.read_text()
    workflow.write_text(workflow.read_text().replace(old, new))
    commit(project)
    release(base, "v1.0.1", "template/.github/workflows/base-ci.yml.jinja", old, new)
    update(project, ".copier-answers.base.yml")
    assert answers(project, "base")["_commit"] == "v1.0.1"
    text = workflow.read_text()
    assert new in text and old not in text
    assert_clean(project)
    fresh = tmp_path / "fresh"
    copy(base, fresh, BASE, vcs_ref="v1.0.1")
    assert text == (fresh / ".github/workflows/base-ci.yml").read_text(), "the project's edit should be gone"


def test_a_conflict_is_staged_for_the_pr(tmp_path: Path) -> None:
    """The project and base change the same line (issue #33): Copier leaves the file unmerged in git's
    index, which blocks create-pull-request's checkout. stage-conflicts.sh stages it, markers and all,
    and names it; the checks then fail until the markers are resolved."""
    old = "astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3"
    ours = "astral-sh/setup-uv@1111111111111111111111111111111111111111 # v10.3.4"
    theirs = "astral-sh/setup-uv@2222222222222222222222222222222222222222 # v10.4.0"
    base, _, project = stacked(tmp_path)
    path = ".github/workflows/base-ci.yml"
    workflow = project / path
    workflow.write_text(workflow.read_text().replace(old, ours))
    commit(project)
    release(base, "v1.0.1", f"template/{path}.jinja", old, theirs)
    update(project, ".copier-answers.base.yml")
    assert sh("git", "ls-files", "-u", cwd=project), "expected Copier to leave an unmerged entry"

    staged = sh("sh", "scripts/stage-conflicts.sh", cwd=project)

    assert staged.splitlines() == [path]
    assert sh("git", "ls-files", "-u", cwd=project) == ""
    sh(*GIT, "checkout", "-qB", "chore/template-base-update", "HEAD", "--", cwd=project)  # as create-pull-request does
    text = workflow.read_text()
    assert re.search(r"^<{7} .*\n(.*\n)*.*" + re.escape(ours) + r"(.*\n)*={7}\n(.*\n)*.*" + re.escape(theirs)
                     + r"(.*\n)*>{7} ", text, re.M), text  # fmt: skip
    assert sh("sh", "scripts/stage-conflicts.sh", cwd=project) == ""
    result = checks(commit(project))
    assert result.returncode != 0 and "unresolved conflict markers" in result.stdout, result.stdout + result.stderr
    assert path in result.stdout


def test_a_clean_update_stages_nothing(tmp_path: Path) -> None:
    base, _, project = stacked(tmp_path)
    release(base, "v1.0.1", "template/CLAUDE.md.jinja", "@AGENTS.md", "@AGENTS.md\n")
    update(project, ".copier-answers.base.yml")
    status = sh("git", "status", "--porcelain", cwd=project)
    assert sh("sh", "scripts/stage-conflicts.sh", cwd=project) == ""
    assert sh("git", "status", "--porcelain", cwd=project) == status
    assert_clean(project)


def set_answers(project: Path, name: str, **values: object) -> None:
    """Rewrite answers in a recorded answers file, a value of None dropping the key, then commit."""
    path = project / f".copier-answers.{name}.yml"
    data = answers(project, name)
    target = data["base_answers"] if name.startswith("stack-") else data
    for key, value in values.items():
        if value is None:
            target.pop(key, None)  # type: ignore[union-attr]
        else:
            target[key] = value  # type: ignore[index]
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    commit(project)


def pre_0005_base(dst: Path) -> Path:
    """Base as v1.0.0 with v2.1.0's owner_is_org (default true, no validators), and as it is now at v1.0.1."""
    base = stage(ROOT, dst, tag="v1.0.1")
    sh("git", "switch", "-qc", "before-fix", cwd=base)
    config = base / "copier.yml"
    old = re.sub(r"(?ms)^owner_is_org:\n.*?^code_owners:\n.*?\n\n",
                 "owner_is_org:\n  type: bool\n  default: true\n\ncode_owners:\n  type: str\n"
                 "  default: \"@[[ github_owner ]][% if owner_is_org %]/maintainers[% endif %]\"\n\n",
                 config.read_text())  # fmt: skip
    assert "validator" not in old.split("code_owners:")[0].split("owner_is_org:")[1], "owner_is_org not rewritten"
    config.write_text(old)
    sh(*GIT, "commit", "-qam", "v1.0.0", cwd=base)
    sh("git", "tag", "v1.0.0", cwd=base)
    sh("git", "switch", "-q", "main", cwd=base)
    return base


OWNERS = {"andronics": ("@andronics", False), "metalayerlab": ("@metalayerlab/maintainers", True)}


@pytest.mark.parametrize("owner", sorted(OWNERS))
@pytest.mark.parametrize("recorded", [None, True], ids=["before-0003", "recorded-true"])
def test_owner_is_org_follows_code_owners_on_update(tmp_path: Path, owner: str, recorded: bool | None) -> None:
    """A project from before owner_is_org (0003), or one an update gave base's default `true`, as the brain.

    The overlay mirrors base's file as it is, and base records whether code_owners names the owner as
    a user: a personal account gets `false` on its next base update, and the overlay copies that.
    """
    code_owners, is_org = OWNERS[owner]
    base = pre_0005_base(tmp_path / "template-base")
    stub = stage(STUB, tmp_path / "template-stub")
    project = tmp_path / "demo"
    copy(base, project, {**BASE, "github_owner": owner, "code_owners": code_owners}, vcs_ref="v1.0.0")
    copy(stub, project, {})
    commit(project)
    set_answers(project, "base", owner_is_org=recorded)
    set_answers(project, "stack-stub", owner_is_org=recorded)

    release(stub, "v1.1.0", "template/scripts/checks.d/20-[[ stub_name ]].sh.jinja", "only check", "one check")
    update(project, ".copier-answers.stack-stub.yml")
    mirrored = answers(project, "stack-stub")["base_answers"]
    assert mirrored == {k: v for k, v in answers(project, "base").items() if not k.startswith("_")}
    assert mirrored.get("owner_is_org") == recorded  # type: ignore[union-attr]
    commit(project)

    update(project, ".copier-answers.base.yml")
    assert answers(project, "base")["_commit"] == "v1.0.1"
    assert answers(project, "base")["owner_is_org"] is is_org
    assert answers(project, "base")["code_owners"] == code_owners
    commit(project)

    release(stub, "v1.2.0", "template/scripts/checks.d/20-[[ stub_name ]].sh.jinja", "one check", "a check")
    update(project, ".copier-answers.stack-stub.yml")
    assert answers(project, "stack-stub")["base_answers"]["owner_is_org"] is is_org  # type: ignore[index]
    assert_clean(project)
