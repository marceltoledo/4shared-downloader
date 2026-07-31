"""
Browsing/downloading files already fetched for an account.

folder_id and filename are both attacker-controlled URL path segments (an
attacker doesn't need to go through the normal crawl flow to reach these
routes), so every path here is validated to still resolve inside the
account's own download directory before touching the filesystem.
"""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app import config

router = APIRouter(prefix="/api/accounts", tags=["files"])

_FOLDER_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _account_dir(folder_id: str) -> Path:
    if not _FOLDER_ID_RE.match(folder_id):
        raise HTTPException(status_code=400, detail="Invalid folder_id")
    download_root = config.DOWNLOAD_DIR.resolve()
    account_dir = (download_root / folder_id).resolve()
    if not account_dir.is_relative_to(download_root):
        raise HTTPException(status_code=400, detail="Invalid folder_id")
    return account_dir


@router.get("/{folder_id}/files")
def list_files(folder_id: str) -> list[str]:
    account_dir = _account_dir(folder_id)
    if not account_dir.exists():
        return []
    return sorted(p.name for p in account_dir.iterdir() if p.is_file())


@router.get("/{folder_id}/files/{filename:path}")
def download_file(folder_id: str, filename: str):
    account_dir = _account_dir(folder_id)
    candidate = (account_dir / filename).resolve()
    if not candidate.is_relative_to(account_dir):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(candidate)
