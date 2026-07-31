"""
Per-account download history: one history_files/<folder_id>.txt per account,
listing every filename (lowercased) ever successfully downloaded.

Skip logic elsewhere is based on this history, not on what's on disk — so
deleting downloaded files does not cause them to be re-downloaded. This is
intentional: it lets an account be re-scanned later to pick up newly added
files without re-fetching everything.
"""

from pathlib import Path


def history_path(history_dir: Path, folder_id: str) -> Path:
    return history_dir / f"{folder_id}.txt"


def load_history(history_dir: Path, folder_id: str) -> set[str]:
    """Load the set of filenames (lowercased) ever downloaded for this account."""
    path = history_path(history_dir, folder_id)
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}


def record_download(history_dir: Path, folder_id: str, filename: str) -> None:
    """Append a filename to this account's history file."""
    history_dir.mkdir(parents=True, exist_ok=True)
    with open(history_path(history_dir, folder_id), "a", encoding="utf-8") as f:
        f.write(filename.lower() + "\n")
