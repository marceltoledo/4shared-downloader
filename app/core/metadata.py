"""
Central metadata store: one metadata.jsonl across all accounts, one JSON
object appended per successfully downloaded file.

Appending to a file that's created lazily on first write is exactly "reuse it
if it already exists, create it if not" — there's no separate existence check
needed. Matches the flat-file, gitignored-runtime-output convention used by
history.py rather than introducing a database.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class MetadataRecord:
    filename: str
    folder_id: str
    account_url: str
    detail_url: str
    dest_path: str  # str(Path), not Path — Path isn't JSON-serializable
    size_bytes: int
    extension: str
    category: str
    downloaded_at: str  # datetime.now(timezone.utc).isoformat()


def append_metadata(metadata_file: Path, record: MetadataRecord) -> None:
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
