"""Pass-to-pass checks for 003-path-traversal."""

from __future__ import annotations

from pathlib import Path

import pytest

from minishop.files import MissingPublicFile, PublicFiles, UnsafePath


def make_public(tmp_path: Path) -> PublicFiles:
    root = tmp_path / "public"
    (root / "images").mkdir(parents=True)
    (root / "images" / "logo.png").write_bytes(b"PNG")
    (root / "images" / "icon.svg").write_text("<svg />", encoding="utf-8")
    (root / "manual.txt").write_text("read me", encoding="utf-8")
    (root / "café.txt").write_text("accent", encoding="utf-8")
    (root / "a b.txt").write_text("space", encoding="utf-8")
    return PublicFiles(root)


def test_nested_and_dotted_but_safe_paths(tmp_path: Path) -> None:
    public = make_public(tmp_path)
    assert public.read("images/logo.png") == b"PNG"
    assert public.read_text("./images/./icon.svg") == "<svg />"


def test_unicode_and_percent_encoded_names(tmp_path: Path) -> None:
    public = make_public(tmp_path)
    assert public.read_text("café.txt") == "accent"
    assert public.read_text("caf%C3%A9.txt") == "accent"
    assert public.read_text("a%20b.txt") == "space"


def test_encoded_percent_is_decoded_only_once(tmp_path: Path) -> None:
    public = make_public(tmp_path)
    with pytest.raises(MissingPublicFile):
        public.read("%252e%252e/secret.txt")


def test_safe_missing_file_is_still_missing(tmp_path: Path) -> None:
    public = make_public(tmp_path)
    with pytest.raises(MissingPublicFile):
        public.read("images/missing.png")


def test_missing_file_reports_the_original_request(tmp_path: Path) -> None:
    public = make_public(tmp_path)
    with pytest.raises(MissingPublicFile) as excinfo:
        public.read("images/missing.png")
    assert excinfo.value.relative_path == "images/missing.png"


def test_exists_listing_and_root(tmp_path: Path) -> None:
    public = make_public(tmp_path)
    assert public.exists("images/icon.svg") is True
    assert public.exists("images") is False
    assert public.exists("images/missing.png") is False
    assert public.list_files() == (
        "a b.txt",
        "café.txt",
        "images/icon.svg",
        "images/logo.png",
        "manual.txt",
    )
    assert public.root.is_dir()


def test_empty_and_null_requests_are_unsafe(tmp_path: Path) -> None:
    public = make_public(tmp_path)
    for request in ("", "images/logo.png\x00.txt"):
        with pytest.raises(UnsafePath):
            public.read(request)


def test_listing_skips_symlinks(tmp_path: Path) -> None:
    public = make_public(tmp_path)
    target = tmp_path / "public" / "manual.txt"
    link = tmp_path / "public" / "linked.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("this OS does not allow creating symlinks without extra rights")
    assert "linked.txt" not in public.list_files()
