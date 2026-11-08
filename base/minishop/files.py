"""Serving download files from one public directory.

Product images, manuals and sample files live in a single directory on disk and
are addressed by URL-style relative paths such as ``"images/logo.png"``.

The only paths this module will open are paths *inside* that directory. A
request that tries to leave it, by any spelling, is rejected with
:class:`UnsafePath` before any file is read: ``..`` segments, absolute paths,
backslashes, percent-encoded dots, null bytes, and symlinks that point outside
the public directory. A request for a file that is inside the directory but
does not exist raises :class:`MissingPublicFile`.

Percent-decoding happens *before* the check, because browsers send ``%2e``
where a user typed ``.``. Checking after decoding is what makes the check
meaningful.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

__all__ = ["MissingPublicFile", "PublicFileError", "PublicFiles", "UnsafePath"]

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


class PublicFileError(Exception):
    """Base class for problems serving a public file."""


class UnsafePath(PublicFileError):
    """Raised when a path tries to reach outside the public directory."""


class MissingPublicFile(PublicFileError):
    """Raised when a path is safe but there is no such file."""

    def __init__(self, relative_path: str) -> None:
        super().__init__(f"no such public file: {relative_path!r}")
        self.relative_path = relative_path


class PublicFiles:
    """Read-only access to the files under one directory."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        if not self._root.is_dir():
            raise ValueError(f"public directory does not exist: {self._root}")

    @property
    def root(self) -> Path:
        """The resolved public directory."""
        return self._root

    def read(self, relative_path: str) -> bytes:
        """Return the bytes of the requested file."""
        return self._resolve(relative_path).read_bytes()

    def read_text(self, relative_path: str, encoding: str = "utf-8") -> str:
        """Return the decoded text of the requested file."""
        return self._resolve(relative_path).read_text(encoding=encoding)

    def exists(self, relative_path: str) -> bool:
        """True if the path is safe and points at an existing file."""
        try:
            self._resolve(relative_path)
        except PublicFileError:
            return False
        return True

    def list_files(self) -> tuple[str, ...]:
        """Every regular file under the root, as sorted POSIX paths."""
        found: list[str] = []
        for path in self._root.rglob("*"):
            if path.is_symlink():
                continue
            if not path.is_file():
                continue
            found.append(path.relative_to(self._root).as_posix())
        return tuple(sorted(found))

    def _resolve(self, relative_path: str) -> Path:
        """Turn a URL path into a real file inside the root, or raise."""
        if not isinstance(relative_path, str):
            raise UnsafePath("path must be a string")
        if not relative_path:
            raise UnsafePath("path must not be empty")
        if "\x00" in relative_path:
            raise UnsafePath("path must not contain null bytes")
        decoded = unquote(relative_path)
        if "\x00" in decoded:
            raise UnsafePath("path must not contain null bytes")
        if decoded.startswith("/") or _WINDOWS_DRIVE.match(decoded):
            raise UnsafePath(f"absolute paths are not served: {relative_path!r}")
        candidate = (self._root / decoded.replace("\\", "/")).resolve()
        if candidate != self._root and not candidate.is_relative_to(self._root):
            raise UnsafePath(f"path leaves the public directory: {relative_path!r}")
        if not candidate.is_file():
            raise MissingPublicFile(relative_path)
        return candidate
