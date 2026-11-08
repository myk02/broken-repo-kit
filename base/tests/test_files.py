"""Visible tests for minishop.files."""

from __future__ import annotations

from pathlib import Path

import pytest

from minishop.files import MissingPublicFile, PublicFiles, UnsafePath


def make_public(root: Path) -> PublicFiles:
    """Create a small public directory and return a reader for it."""
    root.mkdir(parents=True)
    (root / "images").mkdir()
    (root / "images" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (root / "images" / "icon.svg").write_text("<svg />", encoding="utf-8")
    (root / "manual.txt").write_text("read me", encoding="utf-8")
    (root / "café.txt").write_text("accent", encoding="utf-8")
    return PublicFiles(root)


def test_read_returns_bytes(tmp_path: Path) -> None:
    public = make_public(tmp_path / "public")
    assert public.read("images/logo.png") == b"\x89PNG\r\n\x1a\n"


def test_read_text_decodes_utf8(tmp_path: Path) -> None:
    public = make_public(tmp_path / "public")
    assert public.read_text("manual.txt") == "read me"


def test_read_supports_unicode_names(tmp_path: Path) -> None:
    public = make_public(tmp_path / "public")
    assert public.read_text("café.txt") == "accent"


def test_exists_is_true_only_for_real_files(tmp_path: Path) -> None:
    public = make_public(tmp_path / "public")
    assert public.exists("images/icon.svg") is True
    assert public.exists("images") is False
    assert public.exists("images/missing.png") is False


def test_missing_file_raises_its_own_error(tmp_path: Path) -> None:
    public = make_public(tmp_path / "public")
    with pytest.raises(MissingPublicFile) as excinfo:
        public.read("images/missing.png")
    assert excinfo.value.relative_path == "images/missing.png"


def test_list_files_is_sorted_and_uses_forward_slashes(tmp_path: Path) -> None:
    public = make_public(tmp_path / "public")
    assert public.list_files() == (
        "café.txt",
        "images/icon.svg",
        "images/logo.png",
        "manual.txt",
    )


def test_dotted_but_legal_paths_are_served(tmp_path: Path) -> None:
    public = make_public(tmp_path / "public")
    assert public.read_text("./images/./icon.svg") == "<svg />"


def test_empty_and_null_paths_are_rejected(tmp_path: Path) -> None:
    public = make_public(tmp_path / "public")
    with pytest.raises(UnsafePath):
        public.read("")
    with pytest.raises(UnsafePath):
        public.read("images/logo.png\x00.txt")


def test_constructor_requires_an_existing_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        PublicFiles(tmp_path / "does-not-exist")
