"""Tests for ``python -m kit`` through its public entry point."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from kit.cli import main
from kit.patching import apply_patch_file
from kit.paths import KIT_ROOT
from kit.task import load_one


def run(*argv: str) -> tuple[int, str]:
    buffer = io.StringIO()
    code = main(list(argv), out=buffer)
    return code, buffer.getvalue()


def test_list_shows_the_tasks() -> None:
    code, output = run("list")
    assert code == 0
    assert "001-discount-stacking" in output
    assert "005-coupon-feature" in output


def test_list_json_is_machine_readable() -> None:
    code, output = run("list", "--json")
    assert code == 0
    payload = json.loads(output)
    assert isinstance(payload, list)
    assert {entry["id"] for entry in payload} >= {
        "001-discount-stacking",
        "005-coupon-feature",
    }
    assert all({"id", "type", "difficulty"} <= set(entry) for entry in payload)


def test_build_then_verify_broken_then_golden(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    code, output = run("build", "001-discount-stacking", "--out", str(workspace))
    assert code == 0
    assert workspace.joinpath("minishop", "pricing.py").is_file()
    assert "workspace ready" in output

    code, _ = run("verify", "001-discount-stacking", "--workspace", str(workspace))
    assert code == 1

    task = load_one("001-discount-stacking")
    apply_patch_file(task.file("golden.patch"), workspace)
    code, output = run("verify", "001-discount-stacking", "--workspace", str(workspace))
    assert code == 0, output
    assert "PASSED" in output


def test_verify_patch_json_and_exit_codes() -> None:
    task = load_one("001-discount-stacking")
    code, output = run(
        "verify",
        task.id,
        "--patch",
        str(task.file("golden.patch")),
        "--json",
    )
    assert code == 0
    payload = json.loads(output)
    assert payload["passed"] is True
    assert payload["fail_to_pass"]["failed"] == 0
    assert isinstance(payload["duration_seconds"], float)

    bad = task.file("solutions/invalid/reverses_discount_order.patch")
    code, output = run("verify", task.id, "--patch", str(bad), "--json")
    assert code == 1
    assert json.loads(output)["passed"] is False


def test_unknown_task_exits_two(tmp_path: Path) -> None:
    code, output = run("build", "999-no-such-task", "--out", str(tmp_path / "x"))
    assert code == 2
    assert "error:" in output


def test_verify_requires_a_workspace_or_a_patch() -> None:
    with pytest.raises(SystemExit) as excinfo:
        run("verify", "001-discount-stacking")
    assert excinfo.value.code == 2


def test_selftest_of_one_task_passes() -> None:
    code, output = run("selftest", "--task", "001-discount-stacking", "--repeat", "1")
    assert code == 0, output
    assert "001-discount-stacking" in output
    assert "1/1 tasks passed all checks" in output


def test_python_m_kit_works_without_an_installed_entry_point() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "kit", "list"],
        cwd=KIT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "001-discount-stacking" in completed.stdout
