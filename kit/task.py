"""Task metadata: what a task is, and what a solver is allowed to touch.

``metadata.json`` is the single source of truth for the machine-readable part of
a task. It is deliberately *not* copied into a solver workspace: knowing which
file to look at would give the answer away.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .paths import TASKS_DIR, is_task_id

__all__ = ["MetadataError", "Task", "TaskStructure", "check_structure", "load_task", "load_tasks"]

KINDS = frozenset({"bug", "security", "performance", "feature", "refactor"})
DIFFICULTIES = frozenset({"easy", "medium", "medium-hard", "hard"})
STATUSES = frozenset({"ready", "draft"})

REQUIRED_FILES = (
    "task.md",
    "metadata.json",
    "inject.patch",
    "golden.patch",
    "reasoning.md",
    "verifier/test_fail_to_pass.py",
    "verifier/test_pass_to_pass.py",
)


class MetadataError(ValueError):
    """Raised when ``metadata.json`` is missing or malformed."""


@dataclass(frozen=True)
class Task:
    """Everything the kit needs to know about one task."""

    id: str
    kind: str
    difficulty: str
    summary: str
    touched_files: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    tags: tuple[str, ...]
    estimated_minutes: int
    time_limit_seconds: int
    version: int
    status: str
    path: Path

    @property
    def is_ready(self) -> bool:
        """False for scaffolded tasks, which ``selftest`` skips by default."""
        return self.status == "ready"

    def __str__(self) -> str:
        return f"{self.id} [{self.kind}/{self.difficulty}] {self.summary}"

    def file(self, relative: str) -> Path:
        """Path to one file of this task."""
        return self.path / relative


def _require(data: dict[str, object], key: str, kind: type, task_id: str) -> object:
    if key not in data:
        raise MetadataError(f"{task_id}: metadata.json is missing {key!r}")
    value = data[key]
    if not isinstance(value, kind):
        raise MetadataError(f"{task_id}: {key!r} must be a {kind.__name__}")
    return value


def _string_tuple(data: dict[str, object], key: str, task_id: str) -> tuple[str, ...]:
    raw = _require(data, key, list, task_id)
    assert isinstance(raw, list)
    values = []
    for item in raw:
        if not isinstance(item, str):
            raise MetadataError(f"{task_id}: {key!r} must contain only strings")
        values.append(item)
    return tuple(values)


def load_task(path: Path) -> Task:
    """Load and validate one task folder."""
    metadata_path = path / "metadata.json"
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise MetadataError(f"{path.name}: no metadata.json") from None
    except json.JSONDecodeError as exc:
        raise MetadataError(f"{path.name}: metadata.json is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise MetadataError(f"{path.name}: metadata.json must contain an object")

    task_id = _require(data, "id", str, path.name)
    assert isinstance(task_id, str)
    if task_id != path.name or not is_task_id(task_id):
        raise MetadataError(f"{path.name}: id must equal the folder name and look like 001-my-task")

    kind = _require(data, "type", str, task_id)
    if kind not in KINDS:
        raise MetadataError(f"{task_id}: type must be one of {sorted(KINDS)}")
    difficulty = _require(data, "difficulty", str, task_id)
    if difficulty not in DIFFICULTIES:
        raise MetadataError(f"{task_id}: difficulty must be one of {sorted(DIFFICULTIES)}")
    status = _require(data, "status", str, task_id)
    if status not in STATUSES:
        raise MetadataError(f"{task_id}: status must be one of {sorted(STATUSES)}")

    touched = _string_tuple(data, "touched_files", task_id)
    allowed = _string_tuple(data, "allowed_paths", task_id)
    if not allowed:
        raise MetadataError(f"{task_id}: allowed_paths must not be empty")
    for entry in allowed:
        if entry.startswith("/") or ".." in Path(entry).parts:
            raise MetadataError(f"{task_id}: allowed_paths entry {entry!r} escapes the workspace")

    seconds = _require(data, "time_limit_seconds", int, task_id)
    minutes = _require(data, "estimated_minutes", int, task_id)
    version = _require(data, "version", int, task_id)
    assert isinstance(seconds, int) and isinstance(minutes, int) and isinstance(version, int)
    if seconds < 1 or minutes < 1 or version < 1:
        raise MetadataError(f"{task_id}: time_limit_seconds, estimated_minutes and version must be positive")

    return Task(
        id=task_id,
        kind=kind,
        difficulty=difficulty,
        summary=_require(data, "summary", str, task_id),  # type: ignore[arg-type]
        touched_files=touched,
        allowed_paths=allowed,
        tags=_string_tuple(data, "tags", task_id),
        estimated_minutes=minutes,
        time_limit_seconds=seconds,
        version=version,
        status=status,
        path=path,
    )


def load_tasks(include_drafts: bool = True) -> list[Task]:
    """Load every task folder, sorted by id."""
    if not TASKS_DIR.is_dir():
        return []
    tasks: list[Task] = []
    for folder in sorted(TASKS_DIR.iterdir()):
        if not folder.is_dir() or not is_task_id(folder.name):
            continue
        task = load_task(folder)
        if include_drafts or task.is_ready:
            tasks.append(task)
    return tasks


def load_one(task_id: str) -> Task:
    """Load one task by id, raising :class:`MetadataError` if it is unknown."""
    path = TASKS_DIR / task_id
    if not path.is_dir():
        raise MetadataError(f"unknown task: {task_id!r} (run 'python -m kit list')")
    return load_task(path)


@dataclass(frozen=True)
class TaskStructure:
    """The result of checking that a task folder is complete."""

    problems: tuple[str, ...]
    valid_patches: tuple[str, ...]
    invalid_patches: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """True when the folder has no problems."""
        return not self.problems


def check_structure(task: Task, *, min_valid: int = 2, min_invalid: int = 3) -> TaskStructure:
    """Check that a task folder has every file the kit promises, and enough solutions."""
    problems: list[str] = []
    for relative in REQUIRED_FILES:
        path = task.path / relative
        if not path.is_file():
            problems.append(f"missing {relative}")
        elif relative == "inject.patch" and task.kind == "feature":
            # A feature starts from the untouched base; there is nothing to inject.
            continue
        elif not path.read_text(encoding="utf-8").strip():
            problems.append(f"empty {relative}")

    valid = _patch_names(task.path / "solutions" / "valid")
    invalid = _patch_names(task.path / "solutions" / "invalid")
    if len(valid) < min_valid:
        problems.append(f"needs at least {min_valid} valid solutions, found {len(valid)}")
    if len(invalid) < min_invalid:
        problems.append(f"needs at least {min_invalid} invalid solutions, found {len(invalid)}")
    return TaskStructure(problems=tuple(problems), valid_patches=valid, invalid_patches=invalid)


def _patch_names(directory: Path) -> tuple[str, ...]:
    if not directory.is_dir():
        return ()
    return tuple(sorted(path.name for path in directory.glob("*.patch")))
