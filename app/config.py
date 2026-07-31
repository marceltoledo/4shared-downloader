"""
Central settings for the 4shared downloader web app.

DATA_DIR anchors every data path to a fixed absolute directory, not the
process's current working directory — a plain "./downloads" default would
silently create a second, empty data tree if uvicorn/gunicorn happens to be
launched from somewhere else. Override with DOWNLOADER_DATA_DIR if needed.
"""

import os
from pathlib import Path

DEFAULT_DATA_DIR = Path("/home/marceltoledo/Python/4shared-downloader")

DATA_DIR = Path(os.environ.get("DOWNLOADER_DATA_DIR", str(DEFAULT_DATA_DIR)))

ACCOUNTS_FILE = DATA_DIR / "myaccounts.txt"
DOWNLOAD_DIR = DATA_DIR / "downloads"
HISTORY_DIR = DATA_DIR / "histrory"
LOG_FILE = DATA_DIR / "download_log.txt"

AUTH_USER = os.environ.get("DOWNLOADER_AUTH_USER")
AUTH_PASS = os.environ.get("DOWNLOADER_AUTH_PASS")

# Comma-separated extra Chromium launch args, e.g. "--no-sandbox,--disable-dev-shm-usage".
# Left empty by default so local dev keeps Chromium's sandbox; only set this in
# containers that must run Chromium as root (preferred: run as a non-root user instead).
CHROMIUM_LAUNCH_ARGS = [
    arg.strip() for arg in os.environ.get("CHROMIUM_LAUNCH_ARGS", "").split(",") if arg.strip()
]


def ensure_data_dirs() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
