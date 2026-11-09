"""Tests for building solver workspaces."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kit.task import MetadataError
from kit.workspace import (
    WorkspaceError,
    build_workspace,
    copy_allowed_paths,
    create_solver_tree,
    hash_tree,
    make_temp_dir,
)
from kit.task import load_one


@pytest.fixture()
def task():
    """The first task, which is stable and small."""
    return load_one("001-discount-stacking")


def test_build_workspace_contains_only_what_a_solver_sees(task, tmp_path: Path) -> None:
    destination = tmp_path / "workspace"
    built = build_workspace(task.id, destination)

    assert built == destination.resolve()
    assert (built / "minishop" / "pricing.py").is_file()
    assert (built / "tests" / "test_pricing.py").is_file()
    assert (built / "task.md").is_file()
    assert not (built / "metadata.json").exists()
    assert not (built / "verifier").exists()
    assert not (built / "golden.patch").exists()
    assert not (built / "inject.patch").exists()


def test_build_workspace_refuses_a_non_empty_folder(task, tmp_path: Path) -> None:
    destination = tmp_path / "workspace"
    destination.mkdir()
    (destination / "keep.txt").write_text("do not delete", encoding="utf-8")

    with pytest.raises(WorkspaceError, match="not empty"):
        build_workspace(task.id, destination)
    assert (destination / "keep.txt").read_text(encoding="utf-8") == "do not delete"

    build_workspace(task.id, destination, force=True)
    assert not (destination / "keep.txt").exists()
    assert (destination / "minishop" / "pricing.py").is_file()


def test_build_workspace_rejects_an_unknown_task(tmp_path: Path) -> None:
    with pytest.raises(MetadataError, match="unknown task"):
        build_workspace("999-no-such-task", tmp_path / "workspace")


def test_hash_tree_ignores_caches_and_bytecode(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"cache")
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / ".pytest_cache" / "state").write_text("x", encoding="utf-8")

    manifest = hash_tree(tmp_path)
    assert list(manifest) == ["a.txt"]


def test_hash_tree_hashes_symlinks_as_targets(tmp_path: Path) -> None:
    (tmp_path / "real.txt").write_text("real", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to("real.txt")
    except (OSError, NotImplementedError):
        pytest.skip("this OS does not allow creating symlinks without extra rights")

    manifest = hash_tree(tmp_path)
    assert manifest["link.txt"] == "symlink:real.txt"


def test_copy_allowed_paths_takes_only_the_editable_part(task, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    create_solver_tree(task, workspace)
    destination = tmp_path / "clean"
    destination.mkdir()

    copy_allowed_paths(task, workspace, destination)

    assert (destination / "minishop" / "pricing.py").is_file()
    assert not (destination / "tests").exists()
    assert not (destination / "task.md").exists()


def test_create_solver_tree_keeps_the_task_prompt(task, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    create_solver_tree(task, workspace)
    assert (workspace / "task.md").read_text(encoding="utf-8") == task.file("task.md").read_text(
        encoding="utf-8"
    )


def test_feature_task_starts_from_the_base_library(tmp_path: Path) -> None:
    feature = load_one("005-coupon-feature")
    workspace = tmp_path / "workspace"
    create_solver_tree(feature, workspace)
    pricing = (workspace / "minishop" / "pricing.py").read_text(encoding="utf-8")
    assert "class Coupon" not in pricing
    assert (workspace / "task.md").is_file()


def test_make_temp_dir_exists_and_is_outside_the_repository() -> None:
    root = make_temp_dir()
    try:
        assert root.is_dir()
        assert Path(__file__).resolve().parent not in root.parents
    finally:
        os.rmdir(root)
