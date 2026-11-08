"""Building solver workspaces and comparing directory trees.

A *workspace* is the folder a solver works in: the broken ``minishop`` package,
the visible test suite and ``task.md``. Nothing else. In particular it does not
contain ``metadata.json`` (which would name the files that were touched), the
verifier or the golden patch.

Everything is created inside a temporary directory and moved into place, so a
failed build never leaves half a workspace behind.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from .patching import apply_patch_file
from .paths import BASE_PACKAGE, BASE_TESTS, IGNORED_NAMES, IGNORED_SUFFIXES
from .task import Task

__all__ = [
    "WorkspaceError",
    "build_workspace",
    "copy_allowed_paths",
    "create_base_tree",
    "create_broken_tree",
    "create_solver_tree",
    "hash_tree",
    "make_temp_dir",
]

MAX_FILES = 2_000
MAX_BYTES = 20 * 1024 * 1024
_COPY_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache")


class WorkspaceError(Exception):
    """Raised when a workspace cannot be built or read."""


def _ignored(path: Path) -> bool:
    """True for caches and byte-code that are not part of a solution."""
    if path.name in IGNORED_NAMES:
        return True
    return path.name.endswith(IGNORED_SUFFIXES)


def create_base_tree(destination: Path) -> None:
    """Copy the clean base library and its visible tests into ``destination``."""
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BASE_PACKAGE, destination / "minishop", ignore=_COPY_IGNORE)
    shutil.copytree(BASE_TESTS, destination / "tests", ignore=_COPY_IGNORE)


def create_broken_tree(task: Task, destination: Path) -> None:
    """Materialise base + ``inject.patch`` in ``destination``.

    A feature task may ship an empty ``inject.patch``: its starting point is
    the unaffected base library, because the capability to add simply does not
    exist yet.
    """
    create_base_tree(destination)
    inject = task.file("inject.patch")
    if inject.stat().st_size:
        apply_patch_file(inject, destination)


def create_solver_tree(task: Task, destination: Path) -> None:
    """Materialise exactly what a solver receives: broken library, visible tests, task.md."""
    create_broken_tree(task, destination)
    shutil.copyfile(task.file("task.md"), destination / "task.md")


def build_workspace(task_id: str, out: Path, *, force: bool = False) -> Path:
    """Create a ready-to-solve workspace for ``task_id`` at ``out``.

    The target must be missing or empty, unless ``force`` is set, in which case
    its previous contents are replaced.
    """
    from .task import load_one

    task = load_one(task_id)
    out = Path(out).resolve()
    if out.exists() and any(out.iterdir()):
        if not force:
            raise WorkspaceError(
                f"{out} is not empty; choose another --out or pass --force to replace it"
            )
        shutil.rmtree(out)

    staging = Path(tempfile.mkdtemp(prefix="kit-build-"))
    try:
        work = staging / "workspace"
        create_solver_tree(task, work)
        if out.exists():
            out.rmdir()
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(work), str(out))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return out


def make_temp_dir() -> Path:
    """Create a temporary directory outside the repository."""
    return Path(tempfile.mkdtemp(prefix="kit-verify-"))


def hash_tree(root: Path) -> dict[str, str]:
    """Map every file under ``root`` to a digest of its contents.

    Paths are POSIX-style and relative to ``root``. Caches are skipped. A
    symbolic link is hashed as the link target, never followed, so a link
    cannot smuggle in a file from outside the tree.
    """
    root = Path(root)
    if not root.is_dir():
        raise WorkspaceError(f"not a directory: {root}")
    manifest: dict[str, str] = {}
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in IGNORED_NAMES)
        for name in sorted(filenames):
            path = Path(current) / name
            if _ignored(path):
                continue
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                manifest[relative] = "symlink:" + os.readlink(path)
                continue
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
            manifest[relative] = digest.hexdigest()
    return manifest


def copy_allowed_paths(task: Task, workspace: Path, destination: Path) -> None:
    """Copy only the paths a solver is allowed to change into a clean directory."""
    total_files = 0
    total_bytes = 0
    for entry in task.allowed_paths:
        source = workspace / entry
        if not source.exists():
            raise WorkspaceError(f"workspace is missing {entry!r}")
        if source.is_dir():
            for path in source.rglob("*"):
                if path.is_file() and not _ignored(path):
                    total_files += 1
                    total_bytes += path.stat().st_size
        else:
            total_files += 1
            total_bytes += source.stat().st_size
    if total_files > MAX_FILES or total_bytes > MAX_BYTES:
        raise WorkspaceError(
            f"solution is too large to verify ({total_files} files, {total_bytes} bytes)"
        )

    for entry in task.allowed_paths:
        source = workspace / entry
        target = destination / entry
        if source.is_dir():
            shutil.copytree(source, target, ignore=_COPY_IGNORE, symlinks=False)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
