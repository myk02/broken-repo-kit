"""Detecting attempts to win by changing something other than the library.

A solver's workspace is diffed against a freshly built broken tree. Anything
outside ``metadata.json``'s ``allowed_paths`` that was added, changed or deleted
is a violation. This is what stops the cheap tricks: editing the tests,
adding a ``conftest.py`` at the root, dropping in a ``pytest.ini``, or
replacing ``task.md`` with a note saying "done".

The second half of the defence is structural and lives in :mod:`kit.runner`:
the verifier files and the visible tests are copied *from the kit* into a clean
directory, and only the allowed paths are taken from the workspace. Even a
solver who edits a test file in the workspace cannot change the code that runs.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .task import Task
from .workspace import create_solver_tree, hash_tree

__all__ = ["check_violations", "expected_manifest", "is_allowed"]


def is_allowed(task: Task, relative: str) -> bool:
    """True when ``relative`` is inside one of the task's allowed paths."""
    for entry in task.allowed_paths:
        cleaned = entry.rstrip("/")
        if relative == cleaned or relative.startswith(cleaned + "/"):
            return True
    return False


def expected_manifest(task: Task) -> dict[str, str]:
    """Digest every file of the pristine solver workspace for ``task``."""
    with tempfile.TemporaryDirectory(prefix="kit-expect-") as tmp:
        root = Path(tmp) / "workspace"
        create_solver_tree(task, root)
        return hash_tree(root)


def check_violations(task: Task, workspace: Path, expected: dict[str, str]) -> tuple[str, ...]:
    """Return a sorted list of human-readable violations, empty when clean.

    Caches written by pytest are ignored, so a solver who ran the visible tests
    is not accused of anything.
    """
    workspace = Path(workspace)
    if not workspace.is_dir():
        return (f"workspace does not exist: {workspace}",)

    actual = hash_tree(workspace)
    violations: list[str] = []

    for entry in task.allowed_paths:
        if not (workspace / entry).exists():
            violations.append(f"missing required path: {entry}")

    for relative in sorted(actual):
        if is_allowed(task, relative):
            continue
        if relative not in expected:
            violations.append(f"added file outside the allowed paths: {relative}")
        elif expected[relative] != actual[relative]:
            violations.append(f"modified file outside the allowed paths: {relative}")

    for relative in sorted(expected):
        if is_allowed(task, relative):
            continue
        if relative not in actual:
            violations.append(f"deleted file outside the allowed paths: {relative}")

    return tuple(violations)
