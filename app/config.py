"""
Central settings for the 4shared downloader web app.

DATA_DIR anchors every data path to the repo root (resolved from this file's
location), not the process's current working directory — a plain "./downloads"
default would silently create a second, empty data tree if uvicorn/gunicorn
happens to be launched from somewhere else. Override with DOWNLOADER_DATA_DIR
(e.g. pointing at a mounted volume in a container).
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("DOWNLOADER_DATA_DIR", str(REPO_ROOT)))

ACCOUNTS_FILE = DATA_DIR / "myaccounts.txt"
DOWNLOAD_DIR = DATA_DIR / "downloads"
HISTORY_DIR = DATA_DIR / "history_files"
LOG_FILE = DATA_DIR / "download_log.txt"
# Central metadata store, shared across all accounts and both the web app and
# cli.py — one JSON object appended per successfully downloaded file.
METADATA_FILE = DATA_DIR / "metadata.jsonl"

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
