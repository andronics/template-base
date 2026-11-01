from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from stacking import ROOT, commit, copy, stage  # noqa: E402

BASE = {"project_name": "demo", "description": "A demo project", "github_owner": "metalayerlab"}
STUB = ROOT / "tests/fixtures/stub-stack"


@pytest.fixture(scope="session")
def base_src(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return stage(ROOT, tmp_path_factory.mktemp("src") / "template-base")


@pytest.fixture(scope="session")
def project(base_src: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Base alone, with the stub stack overlay filling its slots."""
    dst = tmp_path_factory.mktemp("render") / "demo"
    copy(base_src, dst, BASE)
    copy(STUB, dst, {})
    return commit(dst)
