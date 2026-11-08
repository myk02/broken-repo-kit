"""The ``python -m kit`` command line.

Subcommands:

* ``list``      - show every task with its type and difficulty
* ``build``     - turn a task into a ready-to-solve workspace
* ``verify``    - score a workspace or a patch
* ``selftest``  - prove that the tasks themselves are sound
* ``new-task``  - scaffold an empty task folder

Exit codes: ``0`` success, ``1`` verification or selftest failed, ``2`` a usage
or environment error (unknown task, bad patch, non-empty output folder).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence, TextIO

from .patching import PatchError
from .paths import KIT_ROOT
from .result import VerifyResult
from .runner import verify_patch, verify_workspace
from .scaffold import ScaffoldError, new_task
from .selftest import run_selftest
from .task import MetadataError, Task, load_one, load_tasks
from .workspace import WorkspaceError, build_workspace

__all__ = ["main"]

DEFAULT_OUT = KIT_ROOT / "workspaces"


def _cmd_list(args: argparse.Namespace, out: TextIO) -> int:
    tasks = load_tasks(include_drafts=True)
    if args.json:
        payload = [
            {
                "id": task.id,
                "type": task.kind,
                "difficulty": task.difficulty,
                "status": task.status,
                "estimated_minutes": task.estimated_minutes,
                "summary": task.summary,
            }
            for task in tasks
        ]
        print(json.dumps(payload, indent=2), file=out)
        return 0
    if not tasks:
        print("no tasks yet - run 'python -m kit new-task 001-my-task'", file=out)
        return 0
    width = max(len(task.id) for task in tasks)
    print(f"{'id':<{width}}  {'type':<12} {'difficulty':<12} {'status':<7} summary", file=out)
    for task in tasks:
        print(
            f"{task.id:<{width}}  {task.kind:<12} {task.difficulty:<12} {task.status:<7} {task.summary}",
            file=out,
        )
    return 0


def _cmd_build(args: argparse.Namespace, out: TextIO) -> int:
    target = Path(args.out) if args.out else DEFAULT_OUT / args.task
    workspace = build_workspace(args.task, target, force=args.force)
    print(f"workspace ready: {workspace}", file=out)
    print("", file=out)
    print("next steps:", file=out)
    print(f"  cd {workspace}", file=out)
    print("  python -m pytest tests        # the visible suite, green before you start", file=out)
    print("  ... edit minishop/ ...", file=out)
    print("  python -m kit verify " + args.task + f" --workspace {workspace}", file=out)
    return 0


def _print_result(result: VerifyResult, out: TextIO) -> None:
    status = "PASSED" if result.passed else "FAILED"
    print(f"{result.task}: {status}", file=out)
    print(
        f"  fail-to-pass: {result.fail_to_pass.passed} passed, "
        f"{result.fail_to_pass.failed} failed",
        file=out,
    )
    print(
        f"  pass-to-pass: {result.pass_to_pass.passed} passed, "
        f"{result.pass_to_pass.failed} failed",
        file=out,
    )
    if result.violations:
        print("  violations:", file=out)
        for violation in result.violations:
            print(f"    - {violation}", file=out)
    for failure in result.fail_to_pass.failures[:10]:
        print(f"  f2p failure: {failure}", file=out)
    print(f"  duration: {result.duration_seconds:.2f}s (informational only)", file=out)


def _cmd_verify(args: argparse.Namespace, out: TextIO) -> int:
    task = load_one(args.task)
    if args.workspace:
        result = verify_workspace(task, Path(args.workspace))
    else:
        result = verify_patch(task, Path(args.patch))
    if args.json:
        print(result.to_json(), file=out)
    else:
        _print_result(result, out)
    return 0 if result.passed else 1


def _cmd_selftest(args: argparse.Namespace, out: TextIO) -> int:
    if args.task:
        tasks: Sequence[Task] = [load_one(args.task)]
    else:
        tasks = load_tasks(include_drafts=False)
    if not tasks:
        print("no ready tasks to check", file=out)
        return 1
    report = run_selftest(tasks, repeat=args.repeat, out=out)
    return 0 if report.ok else 1


def _cmd_new_task(args: argparse.Namespace, out: TextIO) -> int:
    destination = new_task(args.task)
    print(f"created {destination}", file=out)
    print("", file=out)
    print("next steps:", file=out)
    print("  1. describe the symptom in task.md (no hints about the fix)", file=out)
    print("  2. write the fix in the base library, then derive inject.patch", file=out)
    print("  3. write golden.patch, the verifier tests and reasoning.md", file=out)
    print("  4. add at least 2 valid and 3 invalid patches", file=out)
    print('  5. set "status": "ready" in metadata.json and run python -m kit selftest', file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m kit",
        description="Reproducible coding challenges: seeded defects, golden patches and verifiers.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser("list", help="show all tasks")
    listing.add_argument("--json", action="store_true", help="print machine-readable JSON")
    listing.set_defaults(func=_cmd_list)

    build = subparsers.add_parser("build", help="create a ready-to-solve workspace")
    build.add_argument("task", help="task id, e.g. 001-discount-stacking")
    build.add_argument("--out", help="destination folder (default: workspaces/<task>)")
    build.add_argument("--force", action="store_true", help="replace a non-empty destination")
    build.set_defaults(func=_cmd_build)

    verify = subparsers.add_parser("verify", help="score a workspace or a patch")
    verify.add_argument("task", help="task id")
    source = verify.add_mutually_exclusive_group(required=True)
    source.add_argument("--workspace", help="folder containing the solver's minishop/")
    source.add_argument("--patch", help="patch to apply to a fresh broken workspace")
    verify.add_argument("--json", action="store_true", help="print only the JSON result")
    verify.set_defaults(func=_cmd_verify)

    selftest = subparsers.add_parser("selftest", help="run the quality gate over every task")
    selftest.add_argument("--task", help="only check this task")
    selftest.add_argument("--repeat", type=int, default=3, help="repeat every verification N times")
    selftest.set_defaults(func=_cmd_selftest)

    scaffold = subparsers.add_parser("new-task", help="scaffold an empty task folder")
    scaffold.add_argument("task", help="new task id, e.g. 006-my-idea")
    scaffold.set_defaults(func=_cmd_new_task)

    return parser


def main(argv: Sequence[str] | None = None, *, out: TextIO | None = None) -> int:
    """Entry point. Returns the process exit code."""
    stream = out if out is not None else sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args, stream))
    except (MetadataError, WorkspaceError, ScaffoldError, PatchError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr if out is None else stream)
        return 2
