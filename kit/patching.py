"""A small, strict unified-diff applier written in pure Python.

The kit must work on a machine that has neither ``git`` nor ``patch`` on the
``PATH`` (plain Windows is exactly such a machine), so patches are applied by
this module instead of by an external program.

The applier is intentionally *strict*: every context line and every removed
line must match the target file exactly, at the line number named in the hunk
header. There is no fuzz factor and no offset search. A patch that does not
belong to the file it is aimed at fails loudly, with the file name, the hunk
number and the first line that did not match.

Supported: modifications, file creation (``--- /dev/null``), file deletion
(``+++ /dev/null``) and the ``\\ No newline at end of file`` marker. Not
supported: renames, binary patches and file modes. Those are rejected with a
clear error rather than silently ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

__all__ = [
    "AppliedFile",
    "FilePatch",
    "Hunk",
    "PatchError",
    "apply_patch",
    "apply_patch_file",
    "parse_patch",
]

DEV_NULL: Final = "/dev/null"
_HUNK_HEADER: Final = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_len>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_len>\d+))? @@"
)
_GIT_HEADER_PREFIXES: Final = (
    "diff --git ",
    "index ",
    "new file mode ",
    "deleted file mode ",
    "old mode ",
    "new mode ",
)


class PatchError(Exception):
    """Raised when a patch is malformed or does not apply to the target file."""


@dataclass(frozen=True)
class Hunk:
    """One ``@@`` block of a unified diff.

    ``lines`` holds ``(tag, text)`` pairs where ``tag`` is one of ``" "``,
    ``"-"`` or ``"+"``. ``no_newline`` holds the side markers found after the
    last line: ``"old"``, ``"new"`` or ``None``.
    """

    old_start: int
    old_length: int
    new_start: int
    new_length: int
    lines: tuple[tuple[str, str], ...]
    no_newline: str | None = None


@dataclass(frozen=True)
class FilePatch:
    """The hunks that turn ``old_path`` into ``new_path``.

    ``None`` on either side means ``/dev/null``: the file is created or deleted.
    """

    old_path: str | None
    new_path: str | None
    hunks: tuple[Hunk, ...]


@dataclass(frozen=True)
class AppliedFile:
    """What happened to one file while applying a patch."""

    path: str
    status: str  # "modified", "created" or "deleted"
    added_lines: int
    removed_lines: int


def _clean_path(raw: str) -> str | None:
    """Turn a diff header path into a relative POSIX path, or ``None`` for /dev/null."""
    path = raw.split("\t", 1)[0].strip()
    if path == DEV_NULL:
        return None
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    for prefix in ("a/", "b/"):
        if path.startswith(prefix):
            path = path[len(prefix) :]
            break
    path = path.replace("\\", "/")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise PatchError(f"patch refers to an absolute path: {raw!r}")
    parts = [part for part in path.split("/") if part not in ("", ".")]
    if not parts:
        raise PatchError(f"patch refers to an empty path: {raw!r}")
    if any(part == ".." for part in parts):
        raise PatchError(f"patch tries to escape the project root: {raw!r}")
    return "/".join(parts)


def parse_patch(text: str) -> list[FilePatch]:
    """Parse unified-diff text into :class:`FilePatch` objects.

    The parser accepts the plain ``---``/``+++`` form and tolerates the
    informational ``diff --git``, ``index`` and ``* file mode`` lines that git
    adds. Anything it does not understand is an error, never a silent skip.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    patches: list[FilePatch] = []
    index = 0
    hunks = []
    old_path = None
    new_path = None
    in_file = False

    def flush() -> None:
        nonlocal hunks, old_path, new_path, in_file
        if not in_file:
            return
        patches.append(FilePatch(old_path, new_path, tuple(hunks)))
        hunks = []
        old_path = None
        new_path = None
        in_file = False

    while index < len(lines):
        line = lines[index]
        if line.startswith(_GIT_HEADER_PREFIXES):
            index += 1
            continue
        if line.startswith("rename from ") or line.startswith("rename to "):
            raise PatchError("renames are not supported by this applier")
        if line.startswith("GIT binary patch"):
            raise PatchError("binary patches are not supported by this applier")
        if line.startswith("--- "):
            flush()
            old_path = _clean_path(line[4:])
            if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
                raise PatchError(f"line {index + 1}: '---' header without a '+++' header")
            new_path = _clean_path(lines[index + 1][4:])
            if old_path is None and new_path is None:
                raise PatchError(f"line {index + 1}: both sides of the patch are /dev/null")
            in_file = True
            index += 2
            continue
        if line.startswith("@@ "):
            if not in_file:
                raise PatchError(f"line {index + 1}: hunk before any file header")
            match = _HUNK_HEADER.match(line)
            if match is None:
                raise PatchError(f"line {index + 1}: malformed hunk header {line!r}")
            hunk, index = _parse_hunk_body(lines, index, match)
            hunks.append(hunk)
            continue
        if line.strip() == "":
            index += 1
            continue
        raise PatchError(f"line {index + 1}: unexpected content outside a hunk: {line!r}")
    flush()
    if not patches:
        raise PatchError("patch contains no file changes")
    return patches


def _parse_hunk_body(
    lines: list[str], header_index: int, match: re.Match[str]
) -> tuple[Hunk, int]:
    """Read the lines of one hunk, starting just after its header."""
    old_length = int(match.group("old_len") or "1")
    new_length = int(match.group("new_len") or "1")
    body: list[tuple[str, str]] = []
    no_newline: str | None = None
    index = header_index + 1
    old_seen = 0
    new_seen = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("\\"):
            if not body:
                raise PatchError(f"line {index + 1}: '\\' marker before any hunk line")
            no_newline = "old" if body[-1][0] == "-" else "new"
            index += 1
            continue
        if line.startswith("@@ ") or line.startswith("--- "):
            break
        if line.startswith(_GIT_HEADER_PREFIXES):
            break
        if line == "":
            break
        tag, text = line[0], line[1:]
        if tag not in (" ", "-", "+"):
            raise PatchError(f"line {index + 1}: unknown hunk line prefix {tag!r}")
        if tag in (" ", "-"):
            old_seen += 1
        if tag in (" ", "+"):
            new_seen += 1
        body.append((tag, text))
        index += 1
        if old_seen >= old_length and new_seen >= new_length:
            break
    if old_seen != old_length or new_seen != new_length:
        raise PatchError(
            f"line {header_index + 1}: hunk header promises "
            f"-{old_length}/+{new_length} lines but the body has "
            f"-{old_seen}/+{new_seen}"
        )
    return (
        Hunk(
            old_start=int(match.group("old_start")),
            old_length=old_length,
            new_start=int(match.group("new_start")),
            new_length=new_length,
            lines=tuple(body),
            no_newline=no_newline,
        ),
        index,
    )


def parse_patch_file(path: Path) -> list[FilePatch]:
    """Read and parse a patch file from disk."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - depends on the filesystem
        raise PatchError(f"cannot read patch {path}: {exc}") from exc
    return parse_patch(text)


def apply_patch(text: str, root: Path) -> list[AppliedFile]:
    """Apply unified-diff ``text`` to the directory tree ``root``.

    All files are read and checked before anything is written, so a patch that
    fails half way through leaves the tree untouched. Raises
    :class:`PatchError` on any mismatch.
    """
    root = Path(root).resolve()
    patches = parse_patch(text)
    results: list[AppliedFile] = []
    pending: list[tuple[Path, str | None]] = []

    for patch in patches:
        results.append(_stage_file(patch, root, pending))

    for path, content in pending:
        if content is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
    return results


def apply_patch_file(path: Path, root: Path) -> list[AppliedFile]:
    """Apply the patch stored in ``path`` to the tree at ``root``."""
    return apply_patch(path.read_text(encoding="utf-8"), root)


def _stage_file(
    patch: FilePatch, root: Path, pending: list[tuple[Path, str | None]]
) -> AppliedFile:
    """Check one file's hunks and queue the result in ``pending``."""
    target = patch.new_path if patch.new_path is not None else patch.old_path
    assert target is not None  # parse_patch rejects both-None entries
    destination = root / target
    added = sum(1 for hunk in patch.hunks for tag, _ in hunk.lines if tag == "+")
    removed = sum(1 for hunk in patch.hunks for tag, _ in hunk.lines if tag == "-")

    if patch.old_path is None:
        if destination.exists():
            raise PatchError(f"cannot create {target}: the file already exists")
        lines, has_newline = [], True
        status = "created"
    else:
        source = root / patch.old_path
        if not source.is_file():
            raise PatchError(f"cannot patch {patch.old_path}: no such file")
        try:
            original = source.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise PatchError(f"cannot patch {patch.old_path}: not UTF-8 text") from exc
        has_newline = original.endswith("\n") or original == ""
        lines = original.splitlines() if original else []
        status = "deleted" if patch.new_path is None else "modified"

    lines = _apply_hunks(lines, patch, target)
    if patch.new_path is not None and patch.hunks:
        last = patch.hunks[-1]
        if last.no_newline == "new":
            has_newline = False
        elif last.no_newline == "old":
            has_newline = True

    if patch.new_path is None:
        pending.append((destination, None))
        return AppliedFile(target, status, added, removed)

    body = "\n".join(lines)
    if lines and has_newline:
        body += "\n"
    if not lines:
        body = ""
    pending.append((destination, body))
    return AppliedFile(target, status, added, removed)


def _apply_hunks(lines: list[str], patch: FilePatch, target: str) -> list[str]:
    """Return the patched lines, checking every hunk strictly."""
    result = list(lines)
    offset = 0
    for hunk_number, hunk in enumerate(patch.hunks, start=1):
        start = hunk.old_start if hunk.old_length == 0 else hunk.old_start - 1
        start += offset
        if start < 0 or start > len(result) or start + hunk.old_length > len(result):
            raise PatchError(
                f"{target}: hunk {hunk_number} starts at line {hunk.old_start}, "
                f"outside the file ({len(result)} lines)"
            )
        cursor = start
        for tag, text in hunk.lines:
            if tag == "+":
                result.insert(cursor, text)
                cursor += 1
                continue
            if cursor >= len(result):
                raise PatchError(
                    f"{target}: hunk {hunk_number} runs past the end of the file"
                )
            actual = result[cursor]
            if actual != text:
                raise PatchError(
                    f"{target}: hunk {hunk_number}, line {cursor + 1}: "
                    f"expected {text!r}, found {actual!r}"
                )
            if tag == "-":
                del result[cursor]
            else:
                cursor += 1
        offset += hunk.new_length - hunk.old_length
    return result
