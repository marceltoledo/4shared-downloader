"""
Per-run download filters: filename substring match and file-type category.

Pure and side-effect-free, like urls.py/parsing.py, so it's unit-testable
without network or Playwright. This is a new opt-in feature, not a restore of
the original single-file script's hardcoded ALLOWED_EXT — parse_file_cards()
in parsing.py stays extension-agnostic; filtering happens as a separate step
applied by the crawler.
"""

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


def categorize_extension(ext: str) -> str:
    """Return "video", "audio", or "other" for a lowercased extension like ".mp4"."""
    ext = ext.lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    return "other"


@dataclass(frozen=True)
class CrawlOptions:
    """
    Run-level filter config. Frozen/immutable and holds no mutable state, so
    the same instance is reused unchanged across every account in a run —
    the per-account download counter lives on AccountCrawlContext instead.
    """

    name_filter: str | None = None
    file_type: FileType = "all"
    limit: int | None = None


def matches(filename: str, opts: CrawlOptions) -> bool:
    """True if filename passes both the name substring filter and the file-type filter."""
    if opts.name_filter and opts.name_filter.lower() not in filename.lower():
        return False
    if opts.file_type != "all":
        ext = Path(filename).suffix.lower()
        if ext not in _FILE_TYPE_EXTENSIONS.get(opts.file_type, set()):
            return False
    return True
