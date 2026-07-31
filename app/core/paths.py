"""
Resolving the (optional) custom destination root for a run.

dest_dir is a fully arbitrary, user-supplied absolute filesystem path with no
subtree restriction — unlike api/files.py's folder_id/filename validation,
which guards against attacker-controlled URL path segments, this path is
something the authenticated user typed into their own personal tool (e.g. a
Docker volume mount), so the only requirements are "absolute" and "writable".
"""

import tempfile
from pathlib import Path


class InvalidDestDirError(Exception):
    pass


def resolve_dest_root(dest_dir: str | None, default: Path) -> Path:
    """
    Return `default` if dest_dir is falsy, otherwise resolve dest_dir, create
    it if missing, and verify it's writable. Raises InvalidDestDirError on
    any failure (e.g. the path isn't mounted into the container).
    """
    if not dest_dir:
        return default

    root = Path(dest_dir).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=root):
            pass
    except OSError as e:
        raise InvalidDestDirError(
            f"Cannot write to '{dest_dir}': {e}. If running in Docker, make sure "
            "this path is mounted into the container (e.g. `-v /host/path:/host/path`)."
        ) from e
    return root
