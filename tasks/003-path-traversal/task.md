# Public file reader can escape its directory

`PublicFiles` serves downloadable files from one public directory. A security
review found that a crafted request can make it read a file outside that
directory and return its bytes to the caller.

The reader must reject a request with `UnsafePath` when it could leave the
public directory, including:

- `..` segments in any position, in forward or backward slash spelling;
- absolute paths (POSIX `/...`, Windows `C:\...`, and a leading `%2F`);
- paths whose percent-encoded dots or slashes only become traversal after
  decoding (the reader decodes exactly once);
- a symbolic link inside the public directory whose target is outside it.

An absolute path is always rejected, **even if it happens to point inside the
public directory**. A safe path that simply does not exist must still raise
`MissingPublicFile`, and every legitimate nested file must keep working,
including unicode names and percent-encoded spaces.

## Examples

```python
public.read_text("images/logo.png")        # works
public.read_text("./images/./icon.svg")    # works, dots are harmless here
public.read_text("../secret.txt")          # UnsafePath
public.read_text("images/../../secret.txt")# UnsafePath
public.read_text(str(secret_absolute))     # UnsafePath
public.read_text("images/missing.png")     # MissingPublicFile
```

## Constraints

- Keep the public API (`read`, `read_text`, `exists`, `list_files`, `root`).
- Do not change the exception hierarchy.
- Do not edit the visible tests.
- The fix must work on Windows, macOS and Linux.
