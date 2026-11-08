"""Where things live on disk.

Every path in the kit is derived from this module, so the kit works no matter
which directory it is started from and on every operating system.
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = [
    "BASE_DIR",
    "BASE_PACKAGE",
    "BASE_TESTS",
    "KIT_ROOT",
    "TASKS_DIR",
    "TASK_ID_PATTERN",
    "is_task_id",
    "task_dir",
]

KIT_ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = KIT_ROOT / "base"
BASE_PACKAGE = BASE_DIR / "minishop"
BASE_TESTS = BASE_DIR / "tests"
TASKS_DIR = KIT_ROOT / "tasks"
DOCS_DIR = KIT_ROOT / "docs"

TASK_ID_PATTERN = re.compile(r"^[0-9]{3}-[a-z0-9]+(?:-[a-z0-9]+)*$")

# Ignored when a workspace is compared against the pristine broken tree.
# A solver running the visible tests must not be punished for the caches that
# pytest leaves behind.
IGNORED_NAMES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
IGNORED_SUFFIXES = (".pyc", ".pyo")


def is_task_id(value: str) -> bool:
    """True when ``value`` looks like a task folder name, e.g. ``001-my-task``."""
    return bool(TASK_ID_PATTERN.match(value))


def task_dir(task_id: str) -> Path:
    """Return the folder for ``task_id``, rejecting anything that could escape ``tasks/``."""
    if not is_task_id(task_id):
        raise ValueError(f"not a valid task id: {task_id!r} (expected e.g. 001-discount-stacking)")
    return TASKS_DIR / task_id
