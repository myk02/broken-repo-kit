"""Tests for the quality gate itself.

A quality gate that cannot fail is worthless, so these tests feed it a
deliberately broken task and check that it says so.
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

from kit.paths import TASKS_DIR
from kit.scaffold import new_task
from kit.selftest import evaluate_task, leaked_lines, run_selftest
from kit.task import check_structure, load_task


def copy_task(tmp_path: Path, task_id: str = "001-discount-stacking") -> Path:
    destination = tmp_path / "tasks" / task_id
    shutil.copytree(TASKS_DIR / task_id, destination)
    return destination


def test_evaluate_task_accepts_the_real_task() -> None:
    task = load_task(TASKS_DIR / "001-discount-stacking")
    report = evaluate_task(task, repeat=1)
    assert report.ok is True


def test_evaluate_task_detects_a_golden_patch_that_does_not_fix(tmp_path: Path) -> None:
    path = copy_task(tmp_path)
    wrong = path / "solutions" / "invalid" / "reverses_discount_order.patch"
    shutil.copyfile(wrong, path / "golden.patch")
    task = load_task(path)
    report = evaluate_task(task, repeat=1)
    assert report.ok is False
    assert report.check("golden").ok is False


def test_leaked_lines_finds_a_copied_fix_line(tmp_path: Path) -> None:
    path = copy_task(tmp_path)
    task = load_task(path)
    assert leaked_lines(task) == []

    golden = task.file("golden.patch").read_text(encoding="utf-8")
    added = next(
        line[1:].strip()
        for line in golden.splitlines()
        if line.startswith("+") and not line.startswith("+++") and len(line.strip()) > 25
    )
    task.file("task.md").write_text(
        task.file("task.md").read_text(encoding="utf-8") + "\n" + added + "\n",
        encoding="utf-8",
    )
    assert added in leaked_lines(task)


def test_scaffolded_task_is_incomplete(tmp_path: Path) -> None:
    path = new_task("999-draft-task", tasks_dir=tmp_path / "tasks")
    task = load_task(path)
    structure = check_structure(task)
    assert structure.ok is False
    assert any("valid solutions" in problem for problem in structure.problems)
    assert any("invalid solutions" in problem for problem in structure.problems)


def test_run_selftest_refuses_a_draft(tmp_path: Path) -> None:
    path = new_task("999-draft-task", tasks_dir=tmp_path / "tasks")
    task = load_task(path)
    report = run_selftest([task], repeat=1, out=io.StringIO())
    assert report.ok is False
    assert any("draft" in error for error in report.errors)
