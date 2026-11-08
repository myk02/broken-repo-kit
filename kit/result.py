"""The result of a verification, and its JSON form.

The JSON contract is stable and documented in the README:

.. code-block:: json

    {
      "task": "001-discount-stacking",
      "passed": true,
      "fail_to_pass": {"passed": 12, "failed": 0},
      "pass_to_pass": {"passed": 103, "failed": 0},
      "violations": [],
      "duration_seconds": 1.23
    }

``duration_seconds`` is informational. It is never compared, never asserted on
and never part of ``passed``: timing depends on the machine, and a verifier
that depends on the machine is not a verifier.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

__all__ = ["CaseResult", "SuiteResult", "VerifyResult"]


@dataclass(frozen=True)
class CaseResult:
    """One test that ran inside the verifier."""

    file: str
    name: str
    outcome: str  # "passed", "failed", "skipped"
    message: str = ""


@dataclass(frozen=True)
class SuiteResult:
    """The tally for one suite (fail-to-pass or pass-to-pass)."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """True when at least one test ran and none failed."""
        return self.passed > 0 and self.failed == 0

    def to_dict(self) -> dict[str, int]:
        """JSON form: counts only."""
        return {"passed": self.passed, "failed": self.failed}


@dataclass(frozen=True)
class VerifyResult:
    """The whole outcome of verifying one workspace."""

    task: str
    passed: bool
    fail_to_pass: SuiteResult
    pass_to_pass: SuiteResult
    violations: tuple[str, ...] = ()
    duration_seconds: float = 0.0
    cases: tuple[CaseResult, ...] = field(default=(), repr=False)

    def to_dict(self) -> dict[str, object]:
        """The documented JSON object."""
        return {
            "task": self.task,
            "passed": self.passed,
            "fail_to_pass": self.fail_to_pass.to_dict(),
            "pass_to_pass": self.pass_to_pass.to_dict(),
            "violations": list(self.violations),
            "duration_seconds": round(self.duration_seconds, 3),
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Serialise :meth:`to_dict` as JSON."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False)

    def signature(self) -> tuple[object, ...]:
        """Everything that must be identical across repeated runs.

        Deliberately excludes ``duration_seconds`` and the order of test cases.
        """
        return (
            self.task,
            self.passed,
            self.fail_to_pass.passed,
            self.fail_to_pass.failed,
            self.pass_to_pass.passed,
            self.pass_to_pass.failed,
            self.violations,
        )
