import logging
import os
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})


def safe_filename(name: str, dest_dir: Path) -> Path:
    """Return a unique path in dest_dir, appending _2, _3 etc. on collision."""
    base, ext = os.path.splitext(name)
    candidate = dest_dir / name
    counter = 2
    while candidate.exists():
        candidate = dest_dir / f"{base}_{counter}{ext}"
        counter += 1
    return candidate


def download_to_disk(url: str, dest_path: Path) -> bool:
    try:
        r = _session.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        return True
    except Exception as e:
        log.error(f"  Download error: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False
