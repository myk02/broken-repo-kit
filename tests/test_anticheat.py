"""Tests for the anti-cheat manifest check."""

from __future__ import annotations

import shutil
from pathlib import Path

from kit.anticheat import check_violations, expected_manifest, is_allowed
from kit.task import load_one
from kit.workspace import create_solver_tree


def make_workspace(tmp_path: Path):
    task = load_one("001-discount-stacking")
    workspace = tmp_path / "workspace"
    create_solver_tree(task, workspace)
    return task, workspace, expected_manifest(task)


def test_clean_workspace_has_no_violations(tmp_path: Path) -> None:
    task, workspace, expected = make_workspace(tmp_path)
    assert check_violations(task, workspace, expected) == ()


def test_editing_the_library_is_allowed(tmp_path: Path) -> None:
    task, workspace, expected = make_workspace(tmp_path)
    pricing = workspace / "minishop" / "pricing.py"
    pricing.write_text(pricing.read_text(encoding="utf-8") + "\n# fixed\n", encoding="utf-8")
    assert check_violations(task, workspace, expected) == ()


def test_adding_a_file_inside_the_library_is_allowed(tmp_path: Path) -> None:
    task, workspace, expected = make_workspace(tmp_path)
    (workspace / "minishop" / "helpers.py").write_text("VALUE = 1\n", encoding="utf-8")
    assert check_violations(task, workspace, expected) == ()


def test_editing_a_visible_test_is_a_violation(tmp_path: Path) -> None:
    task, workspace, expected = make_workspace(tmp_path)
    test_file = workspace / "tests" / "test_pricing.py"
    test_file.write_text(test_file.read_text(encoding="utf-8") + "\n# nope\n", encoding="utf-8")
    violations = check_violations(task, workspace, expected)
    assert any("modified file outside the allowed paths" in item for item in violations)


def test_adding_a_conftest_is_a_violation(tmp_path: Path) -> None:
    task, workspace, expected = make_workspace(tmp_path)
    (workspace / "conftest.py").write_text("import pytest\n", encoding="utf-8")
    violations = check_violations(task, workspace, expected)
    assert any("added file outside the allowed paths" in item for item in violations)


def test_deleting_the_task_prompt_is_a_violation(tmp_path: Path) -> None:
    task, workspace, expected = make_workspace(tmp_path)
    (workspace / "task.md").unlink()
    violations = check_violations(task, workspace, expected)
    assert any("deleted file outside the allowed paths" in item for item in violations)


def test_deleting_the_whole_library_is_a_violation(tmp_path: Path) -> None:
    task, workspace, expected = make_workspace(tmp_path)
    shutil.rmtree(workspace / "minishop")
    violations = check_violations(task, workspace, expected)
    assert any("missing required path" in item for item in violations)


def test_pytest_caches_are_ignored(tmp_path: Path) -> None:
    task, workspace, expected = make_workspace(tmp_path)
    (workspace / "__pycache__").mkdir()
    (workspace / "__pycache__" / "x.pyc").write_bytes(b"x")
    (workspace / ".pytest_cache").mkdir()
    (workspace / ".pytest_cache" / "state").write_text("x", encoding="utf-8")
    assert check_violations(task, workspace, expected) == ()


def test_is_allowed_respects_path_boundaries() -> None:
    task = load_one("001-discount-stacking")
    assert is_allowed(task, "minishop/pricing.py") is True
    assert is_allowed(task, "minishop") is True
    assert is_allowed(task, "minishop2/pricing.py") is False
    assert is_allowed(task, "tests/test_pricing.py") is False
