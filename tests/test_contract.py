"""The stack contract that scripts/checks.d/00-base.sh enforces (decision 0001): each case
breaks a rendered base + stub project in one way, and the checks must fail saying why."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import STUB
from stacking import checks, commit, copy


def edit(name: str, old: str, new: str) -> Callable[[Path], None]:
    def change(p: Path) -> None:
        path = p / name
        text = path.read_text()
        assert old in text, (name, old)
        path.write_text(text.replace(old, new))

    return change


def write(name: str, text: str) -> Callable[[Path], None]:
    def change(p: Path) -> None:
        (p / name).parent.mkdir(parents=True, exist_ok=True)
        (p / name).write_text(text)

    return change


def remove(name: str) -> Callable[[Path], None]:
    return lambda p: (p / name).unlink()


def drop_permission(kind: str, entry: str) -> Callable[[Path], None]:
    def change(p: Path) -> None:
        path = p / ".claude/settings.json"
        settings = json.loads(path.read_text())
        settings["permissions"][kind].remove(entry)
        path.write_text(json.dumps(settings))

    return change


def second_stack(p: Path) -> None:
    """A second stack overlay applied on top: the copy itself succeeds; the check catches it."""
    copy(STUB, p, {"stub_name": "other"}, overwrite=True)


FEATURE = "# Template-owned: template-docker. A feature overlay's workflow.\nname: x\non: push\njobs: {}\n"
BREAKS = {
    "a second stack overlay": (second_stack, "exactly one stack overlay"),
    "no stack overlay": (remove(".copier-answers.stack-stub.yml"), "exactly one stack overlay"),
    "no base answers": (remove(".copier-answers.base.yml"), ".copier-answers.base.yml is missing"),
    "slot stack-ci.yml": (remove(".github/workflows/stack-ci.yml"), ".github/workflows/stack-ci.yml is missing"),
    "slot .agents/stack.md": (remove(".agents/stack.md"), ".agents/stack.md is missing"),
    "slot README.md": (remove("README.md"), "README.md is missing"),
    "slot .gitignore": (remove(".gitignore"), ".gitignore is missing"),
    "slot .pre-commit-config.yaml": (remove(".pre-commit-config.yaml"), ".pre-commit-config.yaml is missing"),
    "slot .claude/settings.json": (remove(".claude/settings.json"), ".claude/settings.json is missing"),
    "slot dependabot.yml": (remove(".github/dependabot.yml"), ".github/dependabot.yml is missing"),
    "slot pull_request_template.md": (remove(".github/pull_request_template.md"), ".github/pull_request_template.md is missing"),
    "slot ISSUE_TEMPLATE/config.yml": (remove(".github/ISSUE_TEMPLATE/config.yml"), ".github/ISSUE_TEMPLATE/config.yml is missing"),
    "no template problem item": (edit(".github/pull_request_template.md", "Template problem found?", "Other?"),
                                 "lacks 'Template problem found?'"),
    "no security contact link": (edit(".github/ISSUE_TEMPLATE/config.yml", "/security/advisories/new", "/issues"),
                                 "lacks '/security/advisories/new'"),
    "stack-ci not reusable": (edit(".github/workflows/stack-ci.yml", "workflow_call", "push"), "lacks 'on:\\n  workflow_call'"),
    "an orphan prefixed file": (write(".github/workflows/docker-build.yml", FEATURE), "template-docker, which has no answers file"),
    "an unprefixed overlay workflow": (write(".github/workflows/build.yml", FEATURE.replace("docker", "stub")),
                                       "template-stub's file must be named stub-*"),
    "an unprefixed drop-in": (write("scripts/checks.d/30-lint.sh", "# Template-owned: template-stub.\n"),
                              "template-stub's file must be named stub-*"),
    "no private/ ignore": (edit(".gitignore", "private/\n", ""), "lacks base's entries: private/"),
    "no gitleaks hook": (edit(".pre-commit-config.yaml", "id: gitleaks", "id: other"), "lacks the id: gitleaks hook"),
    "no gh allow": (drop_permission("allow", "Bash(gh:*)"), "allow lacks: Bash(gh:*)"),
    "no gh release deny": (drop_permission("deny", "Bash(gh release:*)"), "deny lacks: Bash(gh release:*)"),
    "no gh api releases deny": (drop_permission("deny", "Bash(gh api *releases*)"), "deny lacks: Bash(gh api *releases*)"),
    "no repo delete deny": (drop_permission("deny", "Bash(gh repo delete:*)"), "deny lacks: Bash(gh repo delete:*)"),
    "no repo archive deny": (drop_permission("deny", "Bash(gh repo archive:*)"), "deny lacks: Bash(gh repo archive:*)"),
    "no git tag deny": (drop_permission("deny", "Bash(git tag:*)"), "deny lacks: Bash(git tag:*)"),
    "no answers edit deny": (drop_permission("deny", "Edit(.copier-answers.*.yml)"), "deny lacks: Edit(.copier-answers.*.yml)"),
    "no boundary hook": (edit(".claude/settings.json", "scripts/repo-boundary.py", "x.py"), "PreToolUse hook"),
    "AGENTS.md over budget": (edit("AGENTS.md", "## Never", "x" * 9000 + "\n## Never"), "over the context budget"),
    "stack.md shares the budget": (write(".agents/stack.md", "x" * 7000), "AGENTS.md + .agents/stack.md"),
    "invalid repository.toml": (write(".github/repository.toml", "topics = 3\n"), ""),
    "gitleaks without base": (edit(".gitleaks.toml", 'path = ".gitleaks.base.toml"', "useDefault = true"),
                              'path = ".gitleaks.base.toml"'),
    "no .gitleaks.toml": (remove(".gitleaks.toml"), "error: .gitleaks.toml:"),
    "invalid .gitleaks.toml": (write(".gitleaks.toml", "[extend\n"), "error: .gitleaks.toml:"),
}  # fmt: skip


@pytest.mark.parametrize("case", BREAKS)
def test_contract_fails(case: str, project: Path, tmp_path: Path) -> None:
    dst = tmp_path / "p"
    shutil.copytree(project, dst)
    change, message = BREAKS[case]
    change(dst)
    result = checks(commit(dst))
    assert result.returncode != 0, result.stdout
    assert message in result.stdout + result.stderr, result.stdout + result.stderr


ALLOWED = {
    "a project workflow": write(".github/workflows/brain-commit.yml", "name: mine\non: push\njobs: {}\n"),
    "a project drop-in": write("scripts/checks.d/50-mine.sh", "echo mine\n"),
    "a project gitleaks entry": edit(".gitleaks.toml", "\n# [[allowlists]]", '\n[[allowlists]]\nstopwords = ["x"]\n#'),
    "a feature overlay": lambda p: (
        write(".copier-answers.docker.yml", "_src_path: gh:andronics/template-docker\n")(p),
        write(".github/workflows/docker-build.yml", FEATURE)(p),
        write("scripts/checks.d/40-docker.sh", "# Template-owned: template-docker.\necho docker\n")(p),
    ),
}


@pytest.mark.parametrize("case", ALLOWED)
def test_contract_allows(case: str, project: Path, tmp_path: Path) -> None:
    """Project files need no prefix; a feature overlay with an answers file may add its own files."""
    dst = tmp_path / "p"
    shutil.copytree(project, dst)
    ALLOWED[case](dst)
    result = checks(commit(dst))
    assert result.returncode == 0, result.stdout + result.stderr
