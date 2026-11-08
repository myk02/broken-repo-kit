"""Unit tests for the unified-diff applier."""

from __future__ import annotations

from pathlib import Path

import pytest

from kit.patching import (
    PatchError,
    apply_patch,
    apply_patch_file,
    parse_patch,
)

SAMPLE = """\
def total(items):
    return sum(items)
"""

PATCH = """\
--- a/pricing.py
+++ b/pricing.py
@@ -1,2 +1,3 @@
 def total(items):
-    return sum(items)
+    subtotal = sum(items)
+    return subtotal
"""


def write(root: Path, name: str, text: str) -> Path:
    """Write ``text`` to ``root/name`` and return the path."""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def test_apply_modifies_the_file(tmp_path: Path) -> None:
    write(tmp_path, "pricing.py", SAMPLE)
    applied = apply_patch(PATCH, tmp_path)
    assert (tmp_path / "pricing.py").read_text() == (
        "def total(items):\n    subtotal = sum(items)\n    return subtotal\n"
    )
    assert len(applied) == 1
    assert applied[0].path == "pricing.py"
    assert applied[0].status == "modified"
    assert applied[0].added_lines == 2
    assert applied[0].removed_lines == 1


def test_apply_multiple_hunks_uses_offsets(tmp_path: Path) -> None:
    original = "".join(f"line {n}\n" for n in range(1, 11))
    write(tmp_path, "f.txt", original)
    patch = """\
--- a/f.txt
+++ b/f.txt
@@ -2,3 +2,4 @@
 line 2
+inserted after two
 line 3
 line 4
@@ -8,3 +9,3 @@
 line 8
-line 9
+line nine
 line 10
"""
    apply_patch(patch, tmp_path)
    assert (tmp_path / "f.txt").read_text().splitlines() == [
        "line 1",
        "line 2",
        "inserted after two",
        "line 3",
        "line 4",
        "line 5",
        "line 6",
        "line 7",
        "line 8",
        "line nine",
        "line 10",
    ]


def test_create_and_delete_files(tmp_path: Path) -> None:
    write(tmp_path, "old.txt", "bye\n")
    patch = """\
--- /dev/null
+++ b/new.txt
@@ -0,0 +1,2 @@
+hello
+world
--- a/old.txt
+++ /dev/null
@@ -1 +0,0 @@
-bye
"""
    applied = apply_patch(patch, tmp_path)
    assert (tmp_path / "new.txt").read_text() == "hello\nworld\n"
    assert not (tmp_path / "old.txt").exists()
    assert [item.status for item in applied] == ["created", "deleted"]


def test_create_nested_directories(tmp_path: Path) -> None:
    patch = """\
--- /dev/null
+++ b/pkg/sub/mod.py
@@ -0,0 +1 @@
+VALUE = 1
"""
    apply_patch(patch, tmp_path)
    assert (tmp_path / "pkg" / "sub" / "mod.py").read_text() == "VALUE = 1\n"


def test_insertion_at_start_and_end(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "b\n")
    patch = """\
--- a/f.txt
+++ b/f.txt
@@ -0,0 +1 @@
+a
@@ -1,1 +2,2 @@
 b
+c
"""
    apply_patch(patch, tmp_path)
    assert (tmp_path / "f.txt").read_text() == "a\nb\nc\n"


def test_no_newline_marker_is_respected(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "one\ntwo")
    patch = """\
--- a/f.txt
+++ b/f.txt
@@ -1,2 +1,2 @@
 one
-two
\\ No newline at end of file
+three
"""
    apply_patch(patch, tmp_path)
    assert (tmp_path / "f.txt").read_bytes() == b"one\nthree\n"


def test_crlf_patch_text_is_normalised(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "a\nb\n")
    apply_patch(PATCH_CRLF := """\
--- a/f.txt
+++ b/f.txt
@@ -1,2 +1,2 @@
 a
-b
+c
""".replace("\n", "\r\n"), tmp_path)
    assert PATCH_CRLF.endswith("\r\n")
    assert (tmp_path / "f.txt").read_text() == "a\nc\n"


def test_context_mismatch_reports_file_and_hunk(tmp_path: Path) -> None:
    write(tmp_path, "pricing.py", "def total(items):\n    return WRONG\n")
    with pytest.raises(PatchError) as excinfo:
        apply_patch(PATCH, tmp_path)
    message = str(excinfo.value)
    assert "pricing.py" in message
    assert "hunk 1" in message
    assert "expected" in message and "found" in message


def test_wrong_line_number_is_rejected(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "a\nb\nc\n")
    patch = """\
--- a/f.txt
+++ b/f.txt
@@ -3,1 +3,1 @@
-a
+z
"""
    with pytest.raises(PatchError):
        apply_patch(patch, tmp_path)


def test_hunk_body_length_must_match_header(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "a\n")
    patch = """\
--- a/f.txt
+++ b/f.txt
@@ -1,3 +1,3 @@
 a
-b
+B
"""
    with pytest.raises(PatchError, match="promises"):
        apply_patch(patch, tmp_path)


def test_failed_patch_leaves_tree_untouched(tmp_path: Path) -> None:
    write(tmp_path, "one.txt", "a\n")
    write(tmp_path, "two.txt", "x\n")
    patch = """\
--- a/one.txt
+++ b/one.txt
@@ -1 +1 @@
-a
+CHANGED
--- a/two.txt
+++ b/two.txt
@@ -1 +1 @@
-nope
+y
"""
    with pytest.raises(PatchError):
        apply_patch(patch, tmp_path)
    assert (tmp_path / "one.txt").read_text() == "a\n"
    assert (tmp_path / "two.txt").read_text() == "x\n"


def test_patch_paths_must_stay_inside_root(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "a\n")
    for header in ("--- /etc/passwd", "--- ../escape.txt", "--- C:/Windows/win.ini"):
        patch = f"{header}\n+++ b/f.txt\n@@ -1 +1 @@\n-a\n+b\n"
        with pytest.raises(PatchError):
            apply_patch(patch, tmp_path)


def test_empty_patch_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(PatchError, match="no file changes"):
        apply_patch("", tmp_path)


def test_missing_target_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(PatchError, match="no such file"):
        apply_patch(PATCH, tmp_path)


def test_create_fails_if_the_file_already_exists(tmp_path: Path) -> None:
    write(tmp_path, "new.txt", "already here\n")
    patch = """\
--- /dev/null
+++ b/new.txt
@@ -0,0 +1 @@
+hello
"""
    with pytest.raises(PatchError, match="already exists"):
        apply_patch(patch, tmp_path)


def test_git_style_headers_are_tolerated(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "a\n")
    patch = """\
diff --git a/f.txt b/f.txt
index 1234567..89abcde 100644
--- a/f.txt
+++ b/f.txt
@@ -1 +1 @@
-a
+b
"""
    apply_patch(patch, tmp_path)
    assert (tmp_path / "f.txt").read_text() == "b\n"


def test_renames_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(PatchError, match="rename"):
        parse_patch("rename from a.txt\nrename to b.txt\n")


def test_parse_patch_exposes_structure() -> None:
    patches = parse_patch(PATCH)
    assert len(patches) == 1
    patch = patches[0]
    assert (patch.old_path, patch.new_path) == ("pricing.py", "pricing.py")
    assert len(patch.hunks) == 1
    hunk = patch.hunks[0]
    assert (hunk.old_start, hunk.old_length) == (1, 2)
    assert (hunk.new_start, hunk.new_length) == (1, 3)
    assert [tag for tag, _ in hunk.lines] == [" ", "-", "+", "+"]


def test_apply_patch_file_reads_from_disk(tmp_path: Path) -> None:
    write(tmp_path, "pricing.py", SAMPLE)
    patch_path = write(tmp_path, "fix.patch", PATCH)
    apply_patch_file(patch_path, tmp_path)
    assert "subtotal" in (tmp_path / "pricing.py").read_text()


def test_hunk_outside_file_is_reported(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "a\n")
    patch = """\
--- a/f.txt
+++ b/f.txt
@@ -10,1 +10,1 @@
-a
+b
"""
    with pytest.raises(PatchError, match="outside the file"):
        apply_patch(patch, tmp_path)


def test_blank_line_terminates_a_hunk(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "a\n\nb\n")
    patch = """\
--- a/f.txt
+++ b/f.txt
@@ -1,3 +1,3 @@
 a
-
+c
 b
"""
    apply_patch(patch, tmp_path)
    assert (tmp_path / "f.txt").read_text() == "a\nc\nb\n"
