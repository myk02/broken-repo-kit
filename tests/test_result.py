"""Tests for the verification result contract."""

from __future__ import annotations

import json

from kit.result import CaseResult, SuiteResult, VerifyResult


def sample_result(**overrides: object) -> VerifyResult:
    values: dict[str, object] = {
        "task": "001-discount-stacking",
        "passed": True,
        "fail_to_pass": SuiteResult(passed=6, failed=0),
        "pass_to_pass": SuiteResult(passed=101, failed=0),
        "violations": (),
        "duration_seconds": 1.23456,
    }
    values.update(overrides)
    return VerifyResult(**values)  # type: ignore[arg-type]


def test_json_contract_has_exactly_the_documented_keys() -> None:
    payload = sample_result().to_dict()
    assert set(payload) == {
        "task",
        "passed",
        "fail_to_pass",
        "pass_to_pass",
        "violations",
        "duration_seconds",
    }
    assert payload["fail_to_pass"] == {"passed": 6, "failed": 0}
    assert payload["pass_to_pass"] == {"passed": 101, "failed": 0}
    assert payload["duration_seconds"] == 1.235


def test_to_json_is_parseable() -> None:
    payload = json.loads(sample_result().to_json())
    assert payload["task"] == "001-discount-stacking"
    assert payload["passed"] is True


def test_signature_ignores_duration_and_individual_cases() -> None:
    slow = sample_result(
        duration_seconds=9.5,
        cases=(CaseResult("tests/x.py", "test_a", "passed"),),
    )
    fast = sample_result(
        duration_seconds=0.1,
        cases=(CaseResult("tests/x.py", "test_b", "passed"),),
    )
    assert slow.signature() == fast.signature()


def test_signature_includes_violations_and_counts() -> None:
    left = sample_result()
    right = sample_result(violations=("modified tests",))
    assert left.signature() != right.signature()
    assert sample_result(fail_to_pass=SuiteResult(passed=5, failed=1)).signature() != left.signature()


def test_suite_ok_requires_a_ran_test_and_no_failures() -> None:
    assert SuiteResult().ok is False
    assert SuiteResult(passed=1).ok is True
    assert SuiteResult(passed=1, failed=1).ok is False
    assert SuiteResult(passed=1, skipped=2).ok is True
