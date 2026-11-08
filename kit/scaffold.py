"""Scaffolding a new task folder.

``python -m kit new-task 006-my-idea`` creates every file a task needs, filled
with ``TODO`` markers and nothing else. The new task starts with
``"status": "draft"``, which means ``selftest`` skips it until someone makes it
real by flipping the status to ``"ready"``. That is what makes the framework
reusable: a half-written task is visibly half-written rather than quietly
included in the quality gate.
"""

from __future__ import annotations

import json
from pathlib import Path

from .paths import TASKS_DIR, is_task_id

__all__ = ["ScaffoldError", "new_task"]

METADATA_TEMPLATE = {
    "id": "",
    "type": "bug",
    "difficulty": "medium",
    "summary": "TODO: one line describing the defect",
    "touched_files": ["minishop/TODO.py"],
    "allowed_paths": ["minishop/"],
    "tags": ["TODO"],
    "estimated_minutes": 20,
    "time_limit_seconds": 30,
    "version": 1,
    "status": "draft",
}

TASK_MD = """\
# {task_id}

TODO: describe the symptom a user sees, the behaviour you expect instead, and
the constraints (public API, error types, performance). Do not describe the fix.

## Examples

```python
# TODO: a couple of inputs and the expected output
```

## Constraints

- TODO
"""

FAIL_TO_PASS = '''"""Fail-to-pass tests for {task_id}.

These tests must fail on the broken workspace and pass on the golden solution.
Write them against the public API only.
"""

from __future__ import annotations

import pytest


# TODO: import the names you need from minishop
def test_todo_replace_me() -> None:
    pytest.fail("TODO: write a test that fails on the broken workspace")
'''

PASS_TO_PASS = '''"""Pass-to-pass tests for {task_id}.

These tests must pass on the broken workspace and on the golden solution. They
prove that the fix did not break behaviour that already worked.
"""

from __future__ import annotations


# TODO: import the names you need from minishop
def test_todo_replace_me() -> None:
    assert True  # TODO: replace with a real behaviour check
'''

REASONING_MD = """\
# {task_id} - reasoning

## Root cause

TODO

## Why this verifier is fair

TODO

## What valid variation it allows

TODO

## Cheats it blocks

TODO
"""


class ScaffoldError(Exception):
    """Raised when a new task cannot be created."""


def new_task(task_id: str, *, tasks_dir: Path | None = None) -> Path:
    """Create the folder for a new task and return its path."""
    if not is_task_id(task_id):
        raise ScaffoldError(
            f"invalid task id: {task_id!r} (expected three digits, a dash and lowercase words)"
        )
    root = tasks_dir if tasks_dir is not None else TASKS_DIR
    destination = root / task_id
    if destination.exists():
        raise ScaffoldError(f"task already exists: {destination}")

    (destination / "verifier").mkdir(parents=True)
    (destination / "solutions" / "valid").mkdir(parents=True)
    (destination / "solutions" / "invalid").mkdir(parents=True)

    metadata = dict(METADATA_TEMPLATE)
    metadata["id"] = task_id
    (destination / "metadata.json").write_bytes(
        (json.dumps(metadata, indent=2) + "\n").encode("utf-8")
    )
    files = {
        "task.md": TASK_MD.format(task_id=task_id),
        "verifier/test_fail_to_pass.py": FAIL_TO_PASS.format(task_id=task_id),
        "verifier/test_pass_to_pass.py": PASS_TO_PASS.format(task_id=task_id),
        "reasoning.md": REASONING_MD.format(task_id=task_id),
        "inject.patch": "# TODO: base -> broken unified diff\n",
        "golden.patch": "# TODO: broken -> correct unified diff\n",
        "solutions/valid/.gitkeep": "",
        "solutions/invalid/.gitkeep": "",
    }
    for relative, content in files.items():
        (destination / relative).write_bytes(content.encode("utf-8"))
    return destination
