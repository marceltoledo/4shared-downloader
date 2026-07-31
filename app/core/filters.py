"""Pure predicates for optional per-run filename and media-type filters."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FileType = Literal["all", "video", "audio"]

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".m4v", ".flv"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"}

_FILE_TYPE_EXTENSIONS: dict[str, set[str]] = {
    "video": VIDEO_EXTENSIONS,
    "audio": AUDIO_EXTENSIONS,
}


@dataclass(frozen=True)
class CrawlOptions:
    name_filter: str | None = None
    file_type: FileType = "all"


def matches(filename: str, options: CrawlOptions) -> bool:
    """Return whether a filename satisfies every configured filter."""
    if options.name_filter and options.name_filter.lower() not in filename.lower():
        return False
    if options.file_type != "all":
        extension = Path(filename).suffix.lower()
        if extension not in _FILE_TYPE_EXTENSIONS[options.file_type]:
            return False
    return True