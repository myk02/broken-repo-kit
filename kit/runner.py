"""Running a verifier against a workspace, safely.

The runner never executes the solver's tests, ``conftest.py`` or anything else
that is not inside ``allowed_paths``. It builds a throw-away directory that
contains:

* ``minishop/`` - copied from the solver's workspace (the only editable part);
* ``tests/``   - the pristine visible suite, copied from the kit;
* ``verifier/``- the pristine fail-to-pass and pass-to-pass files, from the kit.

pytest then runs in that directory with a scrubbed environment, so
``PYTEST_ADDOPTS``, a stray ``pytest.ini`` or a ``sitecustomize.py`` in the
solver's folder cannot influence the outcome.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .anticheat import check_violations, expected_manifest
from .patching import apply_patch_file
from .paths import BASE_TESTS
from .result import CaseResult, SuiteResult, VerifyResult
from .task import Task
from .workspace import copy_allowed_paths, create_solver_tree, make_temp_dir

__all__ = [
    "CaseResult",
    "SuiteResult",
    "VerifyResult",
    "run_suite",
    "verify_patch",
    "verify_workspace",
]

_MISSING_PYTEST = "pytest is not available"


@dataclass(frozen=True)
class PytestRun:
    """Raw outcome of one pytest process."""

    cases: tuple[CaseResult, ...]
    exit_code: int
    output: str
    timed_out: bool = False


def _clean_env(root: Path) -> dict[str, str]:
    """Environment for the verifier process, with the usual escape hatches closed."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "PYTEST_ADDOPTS",
            "PYTEST_PLUGINS",
            "PYTHONSTARTUP",
            "PYTHONHOME",
            "PYTHONPATH",
            "PYTHONWARNINGS",
        }
    }
    env["PYTHONPATH"] = str(root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _parse_junit(path: Path) -> tuple[CaseResult, ...]:
    """Read pytest's JUnit XML into case results."""
    cases: list[CaseResult] = []
    tree = ElementTree.parse(path)
    for element in tree.iter("testcase"):
        file_name = (element.get("file") or element.get("classname") or "").replace("\\", "/")
        name = element.get("name") or "<unknown>"
        failure = element.find("failure")
        if failure is None:
            failure = element.find("error")
        skipped = element.find("skipped")
        if failure is not None:
            raw = (failure.get("message") or failure.text or "").strip()
            first_line = raw.splitlines()[0] if raw else "failed"
            cases.append(CaseResult(file_name, name, "failed", first_line[:300]))
        elif skipped is not None:
            cases.append(CaseResult(file_name, name, "skipped", skipped.get("message") or ""))
        else:
            cases.append(CaseResult(file_name, name, "passed"))
    return tuple(cases)


def run_suite(
    root: Path,
    targets: Sequence[str],
    *,
    timeout_seconds: int,
) -> PytestRun:
    """Run pytest inside ``root`` over ``targets`` and collect per-test outcomes.

    A timeout or a crash is reported as a failed run rather than an exception:
    a verifier that cannot run has not passed.
    """
    report = Path(root) / "report.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        *targets,
        "-p",
        "no:cacheprovider",
        "-q",
        "--junit-xml",
        str(report),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=_clean_env(root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        exit_code = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        output = f"timed out after {timeout_seconds}s\n{exc.stdout or ''}{exc.stderr or ''}"
        exit_code = -1
        timed_out = True
    except OSError as exc:  # pragma: no cover - depends on the install
        output = f"{_MISSING_PYTEST}: {exc}"
        exit_code = -1
        timed_out = False

    cases: tuple[CaseResult, ...] = ()
    if report.is_file():
        try:
            cases = _parse_junit(report)
        except ElementTree.ParseError:  # pragma: no cover - truncated report
            cases = ()
    if not cases and exit_code != 0:
        detail = output.strip().splitlines()
        message = detail[-1] if detail else "pytest produced no report"
        cases = (CaseResult("", "<collection>", "failed", message[:300]),)
    return PytestRun(cases=cases, exit_code=exit_code, output=output, timed_out=timed_out)


def _partition(cases: Sequence[CaseResult]) -> tuple[SuiteResult, SuiteResult]:
    """Split cases into the fail-to-pass suite and the pass-to-pass suite."""
    f2p: list[CaseResult] = []
    p2p: list[CaseResult] = []
    for case in cases:
        # JUnit reports either a path (``verifier/test_fail_to_pass.py``) or a
        # dotted class name (``verifier.test_fail_to_pass``), depending on the
        # pytest version. Match the distinctive stem in both spellings.
        if "test_fail_to_pass" in case.file.replace("\\", "/"):
            f2p.append(case)
        else:
            p2p.append(case)

    def summarise(group: Sequence[CaseResult]) -> SuiteResult:
        passed = sum(1 for case in group if case.outcome == "passed")
        failed = sum(1 for case in group if case.outcome == "failed")
        skipped = sum(1 for case in group if case.outcome == "skipped")
        failures = tuple(
            f"{case.name}: {case.message}" for case in group if case.outcome == "failed"
        )
        return SuiteResult(passed=passed, failed=failed, skipped=skipped, failures=failures)

    return summarise(f2p), summarise(p2p)


def _copy_pristine_tests(destination: Path) -> None:
    """Copy the kit's own visible tests, never the solver's copy of them."""
    shutil.copytree(
        BASE_TESTS,
        destination / "tests",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def _prepare_verifier_dir(task: Task, workspace: Path) -> Path:
    """Build the clean directory that the verifier will run in."""
    root = make_temp_dir()
    copy_allowed_paths(task, workspace, root)
    _copy_pristine_tests(root)
    (root / "verifier").mkdir()
    for name in ("test_fail_to_pass.py", "test_pass_to_pass.py"):
        shutil.copyfile(task.file(f"verifier/{name}"), root / "verifier" / name)
    return root


def verify_workspace(task: Task, workspace: Path) -> VerifyResult:
    """Verify a solver's workspace and return the result."""
    started = time.perf_counter()
    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        return VerifyResult(
            task=task.id,
            passed=False,
            fail_to_pass=SuiteResult(),
            pass_to_pass=SuiteResult(),
            violations=(f"workspace does not exist: {workspace}",),
            duration_seconds=time.perf_counter() - started,
        )

    violations = check_violations(task, workspace, expected_manifest(task))
    if violations:
        return VerifyResult(
            task=task.id,
            passed=False,
            fail_to_pass=SuiteResult(),
            pass_to_pass=SuiteResult(),
            violations=violations,
            duration_seconds=time.perf_counter() - started,
        )

    root = _prepare_verifier_dir(task, workspace)
    try:
        run = run_suite(root, ["tests", "verifier"], timeout_seconds=task.time_limit_seconds)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    fail_to_pass, pass_to_pass = _partition(run.cases)
    passed = fail_to_pass.ok and pass_to_pass.ok and not run.timed_out
    violations = []
    if run.timed_out:
        violations.append(f"verifier exceeded {task.time_limit_seconds}s")
    if not fail_to_pass.passed and not fail_to_pass.failed:
        violations.append("fail-to-pass suite did not run")
    return VerifyResult(
        task=task.id,
        passed=passed,
        fail_to_pass=fail_to_pass,
        pass_to_pass=pass_to_pass,
        violations=tuple(violations),
        duration_seconds=time.perf_counter() - started,
        cases=run.cases,
    )


def verify_patch(task: Task, patch: Path) -> VerifyResult:
    """Apply ``patch`` to a fresh broken workspace and verify the result."""
    started = time.perf_counter()
    root = make_temp_dir()
    try:
        workspace = root / "workspace"
        create_solver_tree(task, workspace)
        try:
            apply_patch_file(Path(patch), workspace)
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            return VerifyResult(
                task=task.id,
                passed=False,
                fail_to_pass=SuiteResult(),
                pass_to_pass=SuiteResult(),
                violations=(f"patch did not apply: {exc}",),
                duration_seconds=time.perf_counter() - started,
            )
        result = verify_workspace(task, workspace)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return VerifyResult(
        task=result.task,
        passed=result.passed,
        fail_to_pass=result.fail_to_pass,
        pass_to_pass=result.pass_to_pass,
        violations=result.violations,
        duration_seconds=time.perf_counter() - started,
        cases=result.cases,
    )


def verify_visible_tests(task: Task, workspace: Path) -> VerifyResult:
    """Run only the pristine visible suite against a workspace's library.

    Used by ``selftest`` to prove two things: the base is green, and the broken
    state does not break the tests a solver can see.
    """
    root = make_temp_dir()
    try:
        copy_allowed_paths(task, workspace, root)
        _copy_pristine_tests(root)
        run = run_suite(root, ["tests"], timeout_seconds=task.time_limit_seconds)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    _, pass_to_pass = _partition(run.cases)
    return VerifyResult(
        task=task.id,
        passed=pass_to_pass.ok,
        fail_to_pass=SuiteResult(),
        pass_to_pass=pass_to_pass,
        violations=() if pass_to_pass.ok else ("visible tests failed",),
        duration_seconds=0.0,
        cases=run.cases,
    )
