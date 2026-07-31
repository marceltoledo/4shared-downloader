"""Metadata persistence helpers for downloaded files."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class MetadataRecord:
    filename: str
    folder_id: str
    account_url: str
    detail_url: str
    media_url: str
    dest_path: str
    size_bytes: int
    downloaded_at: str


def append_metadata(metadata_file: Path, record: MetadataRecord) -> None:
    """Append a JSON-line metadata record to metadata_file."""
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    with metadata_file.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def read_recorded_filenames(metadata_file: Path) -> set[str]:
    """Return filenames already present in the metadata file."""
    if not metadata_file.exists():
        return set()

    recorded: set[str] = set()
    with metadata_file.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            filename = payload.get("filename")
            if isinstance(filename, str) and filename:
                recorded.add(filename)
    return recorded