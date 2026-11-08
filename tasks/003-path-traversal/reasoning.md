# 003-path-traversal - reasoning

## Root cause

`PublicFiles._resolve` used to reject absolute paths and to check that the
resolved candidate was inside the public root. The vulnerable version keeps
the type, empty-path and null-byte checks but drops both containment checks,
so it opens whatever `root / request` resolves to. `..`, a backslash spelling,
an encoded dot and an absolute path all reach outside the directory; a symlink
inside the root is followed to its target.

## Why this verifier is fair

All checks call `read`, `read_text`, `exists` or `list_files` on a directory
created in `tmp_path`. No test reads a fixed system path, so the suite behaves
the same on Windows, macOS and Linux. It expects `UnsafePath` for dangerous
requests and `MissingPublicFile` for safe missing ones; it never inspects how
the check was implemented.

## What valid variation it allows

- resolve and `Path.relative_to` (or `is_relative_to`);
- reject `..` and absolute spellings up front, then compare `os.path.realpath`
  values with `os.path.commonpath`;
- any equivalent scheme that produces the same exceptions.

The two shipped alternatives use different mechanisms and both pass.

## Cheats it blocks

- Blocking only literal `..` misses absolute paths and symlinks.
- A `str.startswith(root)` check accepts a sibling directory whose name shares
  the root prefix (`public-evil`).
- Checking the raw string before percent-decoding misses `%2e%2e`.
- Rejecting absolute paths only when they point outside the root is still
  wrong: the specification forbids absolute requests outright.
- Editing the visible tests is a violation before pytest starts.
