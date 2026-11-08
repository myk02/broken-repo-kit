"""Fail-to-pass checks for 003-path-traversal.

Every test builds its own public directory in pytest's tmp_path, so nothing
outside the test's folder is ever needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from minishop.files import PublicFiles, UnsafePath

SECRET = "TOP-SECRET-CONTENT"


def make_public(tmp_path: Path) -> tuple[PublicFiles, Path, Path]:
    """Create a public directory, a sibling secret and a sibling lookalike."""
    root = tmp_path / "public"
    (root / "images").mkdir(parents=True)
    (root / "images" / "logo.png").write_bytes(b"PNG")
    (root / "manual.txt").write_text("read me", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text(SECRET, encoding="utf-8")
    lookalike = tmp_path / "public-evil"
    lookalike.mkdir()
    (lookalike / "secret.txt").write_text(SECRET, encoding="utf-8")
    return PublicFiles(root), root, secret


def assert_unsafe(public: PublicFiles, path: str) -> None:
    with pytest.raises(UnsafePath):
        public.read(path)


def test_dotdot_from_the_root(tmp_path: Path) -> None:
    public, _, _ = make_public(tmp_path)
    assert_unsafe(public, "../secret.txt")


def test_dotdot_after_a_legitimate_prefix(tmp_path: Path) -> None:
    public, _, _ = make_public(tmp_path)
    assert_unsafe(public, "images/../../secret.txt")


def test_backslash_traversal(tmp_path: Path) -> None:
    public, _, _ = make_public(tmp_path)
    assert_unsafe(public, "..\\secret.txt")


def test_percent_encoded_dot_segments(tmp_path: Path) -> None:
    public, _, _ = make_public(tmp_path)
    assert_unsafe(public, "%2e%2e/secret.txt")
    assert_unsafe(public, "images/%2E%2E/%2E%2E/secret.txt")


def test_encoded_absolute_slash(tmp_path: Path) -> None:
    public, _, secret = make_public(tmp_path)
    assert_unsafe(public, "%2F" + str(secret).lstrip("/").replace("\\", "/"))


def test_absolute_path_outside_the_root(tmp_path: Path) -> None:
    public, _, secret = make_public(tmp_path)
    assert_unsafe(public, str(secret.resolve()))


def test_absolute_path_inside_the_root_is_still_rejected(tmp_path: Path) -> None:
    public, root, _ = make_public(tmp_path)
    assert_unsafe(public, str((root / "manual.txt").resolve()))


def test_traversal_to_a_directory_is_unsafe_not_missing(tmp_path: Path) -> None:
    public, _, _ = make_public(tmp_path)
    assert_unsafe(public, "..")


def test_sibling_directory_with_the_same_name_prefix(tmp_path: Path) -> None:
    public, _, _ = make_public(tmp_path)
    assert_unsafe(public, "../public-evil/secret.txt")


def test_exists_never_reports_a_file_outside_the_root(tmp_path: Path) -> None:
    public, _, _ = make_public(tmp_path)
    assert public.exists("../secret.txt") is False
    assert public.exists("images/../../secret.txt") is False


def test_symlink_that_points_outside_the_root(tmp_path: Path) -> None:
    public, root, secret = make_public(tmp_path)
    link = root / "images" / "escape.txt"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("this OS does not allow creating symlinks without extra rights")
    assert_unsafe(public, "images/escape.txt")
