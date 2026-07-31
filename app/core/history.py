"""Metadata-backed per-account history used by skip logic."""

from pathlib import Path

from app.core.metadata import read_recorded_filenames


def metadata_history_path(history_dir: Path, folder_id: str) -> Path:
    return history_dir / f"{folder_id}.metadata.jsonl"


def load_history(history_dir: Path, folder_id: str) -> set[str]:
    """Load previously downloaded filenames from metadata history."""
    return {name.lower() for name in read_recorded_filenames(metadata_history_path(history_dir, folder_id))}


def record_download(history_dir: Path, folder_id: str, filename: str) -> None:
    """Compatibility no-op: history now comes from metadata files."""
    _ = (history_dir, folder_id, filename)
