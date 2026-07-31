"""
Reads/writes myaccounts.txt — the list of 4shared folder URLs to crawl.

Extracted from the original CLI's main() so both the web API and cli.py can
add/remove/list accounts through the same logic instead of requiring the file
to be hand-edited.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.history import load_history
from app.core.urls import folder_id_from_url, normalize_url

log = logging.getLogger(__name__)


@dataclass
class Account:
    folder_id: str
    url: str
    history_count: int


def _read_lines(accounts_file: Path) -> list[str]:
    if not accounts_file.exists():
        return []
    with open(accounts_file, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def read_accounts(accounts_file: Path, history_dir: Path) -> list[Account]:
    """Read myaccounts.txt, deduplicating by normalized URL (first line wins)."""
    seen: set[str] = set()
    accounts: list[Account] = []
    for raw in _read_lines(accounts_file):
        norm = normalize_url(raw)
        if norm in seen:
            continue
        seen.add(norm)
        folder_id = folder_id_from_url(norm)
        history_count = len(load_history(history_dir, folder_id))
        accounts.append(Account(folder_id=folder_id, url=norm, history_count=history_count))
    return accounts


def add_account(accounts_file: Path, history_dir: Path, raw_url: str) -> Account:
    """Normalize + append a new folder URL, unless it's already present."""
    norm = normalize_url(raw_url)
    folder_id = folder_id_from_url(norm)

    existing = {normalize_url(line) for line in _read_lines(accounts_file)}
    if norm not in existing:
        accounts_file.parent.mkdir(parents=True, exist_ok=True)
        with open(accounts_file, "a", encoding="utf-8") as f:
            f.write(norm + "\n")

    history_count = len(load_history(history_dir, folder_id))
    return Account(folder_id=folder_id, url=norm, history_count=history_count)


def remove_account(accounts_file: Path, folder_id: str) -> bool:
    """
    Remove any line(s) whose normalized URL resolves to this folder_id.
    Leaves downloads/ and histrory/ for that account untouched — those
    are a separate, deliberate decision from "no longer in my account list."
    Returns True if anything was removed.
    """
    lines = _read_lines(accounts_file)
    kept = [line for line in lines if folder_id_from_url(normalize_url(line)) != folder_id]
    if len(kept) == len(lines):
        return False
    with open(accounts_file, "w", encoding="utf-8") as f:
        for line in kept:
            f.write(line + "\n")
    return True
