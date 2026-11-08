"""The quality gate: prove that every task is actually a good task.

For each task ``selftest`` proves all of the following, and prints the evidence
as a matrix:

1. the base library passes the visible tests;
2. the broken state still passes the visible tests (the defect is not obvious),
   fails every fail-to-pass test and passes every pass-to-pass test;
3. the golden patch passes everything;
4. every ``solutions/valid`` patch passes;
5. every ``solutions/invalid`` patch is rejected;
6. repeating all of that N times gives identical results;
7. the task folder is complete and ``task.md`` does not leak the fix.

If any of these is not true, ``selftest`` exits non-zero.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TextIO

from .patching import PatchError, parse_patch_file
from .result import VerifyResult
from .runner import verify_patch, verify_visible_tests, verify_workspace
from .task import Task, check_structure
from .workspace import create_base_tree, create_solver_tree, make_temp_dir

__all__ = ["Check", "SelftestReport", "TaskReport", "leaked_lines", "run_selftest"]

MIN_LEAK_LENGTH = 15
_GENERIC_PREFIXES = ("\"\"\"", "'''", "#", "import ", "from ", ")", "]", "}", "return ", "raise ")


@dataclass(frozen=True)
class Check:
    """One named assertion about a task."""

    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class TaskReport:
    """Everything selftest learned about one task."""

    task_id: str
    checks: tuple[Check, ...]
    invalid: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @property
    def ok(self) -> bool:
        """True when every check passed."""
        return all(check.ok for check in self.checks)

    def check(self, name: str) -> Check:
        """Look up one check by name."""
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(name)


@dataclass(frozen=True)
class SelftestReport:
    """The result of running selftest over a list of tasks."""

    reports: tuple[TaskReport, ...] = ()
    repeated: int = 3
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """True when every task passed and there were no setup errors."""
        return bool(self.reports) and not self.errors and all(r.ok for r in self.reports)


def leaked_lines(task: Task) -> list[str]:
    """Lines added by ``golden.patch`` that also appear in ``task.md``.

    A long, distinctive added line showing up in the prompt is a hint: the
    solver can copy it instead of thinking. Short lines, comments and imports
    are ignored because they say nothing about the fix.
    """
    task_md = task.file("task.md").read_text(encoding="utf-8")
    try:
        patches = parse_patch_file(task.file("golden.patch"))
    except (PatchError, OSError):
        return []
    leaked: list[str] = []
    for patch in patches:
        for hunk in patch.hunks:
            for tag, text in hunk.lines:
                if tag != "+":
                    continue
                stripped = text.strip()
                if len(stripped) < MIN_LEAK_LENGTH:
                    continue
                if stripped.startswith(_GENERIC_PREFIXES):
                    continue
                if stripped in task_md:
                    leaked.append(stripped)
    return leaked


def _format_suite(result: VerifyResult) -> str:
    return (
        f"f2p {result.fail_to_pass.passed}/{result.fail_to_pass.failed} failed, "
        f"p2p {result.pass_to_pass.passed}/{result.pass_to_pass.failed} failed"
    )


def _run_base(task: Task) -> VerifyResult:
    root = make_temp_dir()
    try:
        create_base_tree(root)
        return verify_visible_tests(task, root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _attempt(task: Task, root: Path, structure_valid: Sequence[str], structure_invalid: Sequence[str]) -> dict[str, VerifyResult]:
    """Run every solution of one task once, keyed by a stable label."""
    broken = root / "broken"
    runs: dict[str, VerifyResult] = {
        "broken": verify_workspace(task, broken),
        "golden": verify_patch(task, task.file("golden.patch")),
    }
    for name in structure_valid:
        runs[f"valid/{name}"] = verify_patch(task, task.file("solutions/valid") / name)
    for name in structure_invalid:
        runs[f"invalid/{name}"] = verify_patch(task, task.file("solutions/invalid") / name)
    return runs


def evaluate_task(task: Task, *, repeat: int = 3) -> TaskReport:
    """Run every selftest check for one task."""
    checks: list[Check] = []
    structure = check_structure(task)
    checks.append(Check("structure", structure.ok, "; ".join(structure.problems)))
    if not structure.ok:
        return TaskReport(task_id=task.id, checks=tuple(checks))

    base = _run_base(task)
    checks.append(
        Check("base", base.passed, f"pristine visible suite: {_format_suite(base)}")
    )

    root = make_temp_dir()
    try:
        create_solver_tree(task, root / "broken")
        visible = verify_visible_tests(task, root / "broken")
        checks.append(
            Check(
                "visible",
                visible.passed,
                "the broken state must still pass the visible tests: "
                + (", ".join(visible.pass_to_pass.failures[:3]) or "all green"),
            )
        )

        attempts = [
            _attempt(task, root, structure.valid_patches, structure.invalid_patches)
            for _ in range(repeat)
        ]
    finally:
        shutil.rmtree(root, ignore_errors=True)

    first = attempts[0]
    broken = first["broken"]
    broken_ok = (
        not broken.passed
        and broken.fail_to_pass.failed > 0
        and broken.fail_to_pass.passed == 0
        and broken.pass_to_pass.ok
        and not broken.violations
    )
    checks.append(
        Check(
            "broken",
            broken_ok,
            "broken state must fail every fail-to-pass test and pass pass-to-pass: "
            + _format_suite(broken),
        )
    )

    golden = first["golden"]
    golden_ok = (
        golden.passed
        and golden.fail_to_pass.passed > 0
        and golden.pass_to_pass.passed > 0
        and not golden.violations
    )
    checks.append(Check("golden", golden_ok, "golden solution: " + _format_suite(golden)))

    valid_ok = all(
        first[f"valid/{name}"].passed for name in structure.valid_patches
    )
    valid_detail = "; ".join(
        f"{name}: {'pass' if first[f'valid/{name}'].passed else 'REJECTED'}"
        for name in structure.valid_patches
    )
    checks.append(Check("valid", valid_ok, valid_detail))

    invalid_reasons: list[tuple[str, tuple[str, ...]]] = []
    invalid_ok = True
    for name in structure.invalid_patches:
        result = first[f"invalid/{name}"]
        if result.passed:
            invalid_ok = False
        reasons = result.violations or result.fail_to_pass.failures or result.pass_to_pass.failures
        invalid_reasons.append((name, tuple(reasons)))
    checks.append(
        Check(
            "invalid",
            invalid_ok,
            f"{len(structure.invalid_patches)} wrong fixes, "
            f"{sum(1 for n in structure.invalid_patches if not first[f'invalid/{n}'].passed)} rejected",
        )
    )

    unstable: list[str] = []
    labels = sorted(first)
    for label in labels:
        signatures = {attempts[index][label].signature() for index in range(len(attempts))}
        if len(signatures) > 1:
            unstable.append(label)
    checks.append(
        Check(
            "stable",
            not unstable,
            f"{repeat} identical runs" if not unstable else f"unstable: {', '.join(unstable)}",
        )
    )

    leaked = leaked_lines(task)
    checks.append(
        Check(
            "leak",
            not leaked,
            "task.md repeats the fix: " + "; ".join(leaked[:3]) if leaked else "no fix text in task.md",
        )
    )

    return TaskReport(
        task_id=task.id,
        checks=tuple(checks),
        invalid=tuple(invalid_reasons),
    )


_ORDER = ("structure", "base", "visible", "broken", "golden", "valid", "invalid", "stable", "leak")
_HEADERS = {
    "structure": "struct",
    "base": "base",
    "visible": "visible",
    "broken": "broken",
    "golden": "golden",
    "valid": "valid",
    "invalid": "invalid",
    "stable": "stable",
    "leak": "leak",
}


def _cell(report: TaskReport, name: str) -> str:
    try:
        return "ok" if report.check(name).ok else "FAIL"
    except KeyError:
        return "-"


def print_matrix(report: SelftestReport, out: TextIO = sys.stdout) -> None:
    """Print the pass/fail matrix, then the reasons for anything that failed."""
    width = max([len(r.task_id) for r in report.reports] + [len("task")])
    header = "  ".join([f"{'task':<{width}}", *(_HEADERS[name].ljust(7) for name in _ORDER)])
    print(header, file=out)
    print("-" * len(header), file=out)
    for task_report in report.reports:
        cells = "  ".join(_cell(task_report, name).ljust(7) for name in _ORDER)
        print(f"{task_report.task_id:<{width}}  {cells}", file=out)

    failures = [check for task_report in report.reports for check in task_report.checks if not check.ok]
    if failures:
        print("\nfailures:", file=out)
        for task_report in report.reports:
            for check in task_report.checks:
                if not check.ok:
                    print(f"  {task_report.task_id} / {check.name}: {check.detail}", file=out)

    print("\ninvalid solutions and what rejected them:", file=out)
    for task_report in report.reports:
        for name, reasons in task_report.invalid:
            shown = "; ".join(reasons[:2]) or "rejected"
            print(f"  {task_report.task_id}  {name}: {shown}", file=out)

    for error in report.errors:
        print(f"error: {error}", file=out)
    total = len(report.reports)
    good = sum(1 for task_report in report.reports if task_report.ok)
    print(
        f"\n{good}/{total} tasks passed all checks "
        f"({report.repeated} repeats each)",
        file=out,
    )


def run_selftest(tasks: Sequence[Task], *, repeat: int = 3, out: TextIO = sys.stdout) -> SelftestReport:
    """Run every check for every task and print the matrix."""
    if repeat < 1:
        raise ValueError("repeat must be at least 1")
    reports: list[TaskReport] = []
    errors: list[str] = []
    for task in tasks:
        if not task.is_ready:
            errors.append(f"{task.id}: status is {task.status!r}, not 'ready'")
            continue
        try:
            reports.append(evaluate_task(task, repeat=repeat))
        except Exception as exc:  # noqa: BLE001 - a crashed check is a failed check
            errors.append(f"{task.id}: selftest crashed: {exc}")
    result = SelftestReport(reports=tuple(reports), repeated=repeat, errors=tuple(errors))
    print_matrix(result, out=out)
    return result
