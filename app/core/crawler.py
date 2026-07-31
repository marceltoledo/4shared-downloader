"""
Recursive folder crawler.

crawl_folder() reuses a single already-open Playwright page for the entire
account crawl, passed down through every recursive subfolder call. The
original CLI script opened a new Chromium browser at the top of every
recursive call, which meant a deeply nested folder tree could have many
Chromium instances alive simultaneously — harmless in a one-shot process, but
a real memory risk in a long-lived web server/container. run_account() is the
new entry point: it opens exactly one browser for the whole account, drives
the crawl, and closes it when the account finishes (or errors).
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

from app.config import CHROMIUM_LAUNCH_ARGS
from app.core.browser import get_direct_media_url, load_page
from app.core.downloader import download_to_disk, safe_filename
from app.core.filters import CrawlOptions, matches
from app.core.history import metadata_history_path
from app.core.metadata import MetadataRecord, append_metadata, read_recorded_filenames
from app.core.parsing import (
    parse_file_cards,
    parse_next_page,
    parse_subfolder_cards,
    parse_total_pages,
)

log = logging.getLogger(__name__)


def _raise_if_cancelling() -> None:
    """Stop work quickly after a cancellation request, even between awaits."""
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        raise asyncio.CancelledError()


async def crawl_folder(page, url: str, dest_dir: Path,
                        folder_id: str, account_url: str, history_dir: Path,
                        metadata_file: Path, visited_urls: set, downloaded: set,
                        options: CrawlOptions, depth: int = 0) -> None:
    """
    Crawl a folder page (all paginated pages) then recurse into subfolders.

    downloaded: set of lowercased filenames from this account's history file.
                Strictly skipped regardless of disk state.
                Successful downloads are added here AND written to history file.
    """
    _raise_if_cancelling()

    if url in visited_urls:
        log.info(f"{'  '*depth}[SKIP] Already visited: {url}")
        return
    visited_urls.add(url)

    log.info(f"{'  '*depth}Crawling: {url}")
    html = await load_page(page, url)

    total_pages = parse_total_pages(html)
    log.info(f"{'  '*depth}  Total pages: {total_pages}")

    subfolders = parse_subfolder_cards(html)
    log.info(f"{'  '*depth}  Subfolders found: {len(subfolders)}")

    current_html = html
    page_num = 1

    while True:
        _raise_if_cancelling()
        files = parse_file_cards(current_html)
        log.info(f"{'  '*depth}  Page {page_num}: {len(files)} media file(s)")

        for filename, detail_url in files:
            _raise_if_cancelling()
            if filename.lower() in downloaded:
                log.info(f"{'  '*depth}    [SKIP] {filename}")
                continue

            if not matches(filename, options):
                log.info(f"{'  '*depth}    [FILTERED] {filename}")
                continue

            log.info(f"{'  '*depth}    Fetching URL: {filename}")
            media_url = await get_direct_media_url(page, detail_url)

            if not media_url:
                log.warning(f"{'  '*depth}    [FAIL] No URL for {filename}")
                continue

            dest_path = safe_filename(filename, dest_dir)
            ok = await asyncio.to_thread(download_to_disk, media_url, dest_path)
            if ok:
                downloaded.add(filename.lower())
                _append_download_metadata(
                    metadata_file=metadata_file,
                    filename=filename,
                    folder_id=folder_id,
                    account_url=account_url,
                    detail_url=detail_url,
                    media_url=media_url,
                    dest_path=dest_path,
                )
                log.info(f"{'  '*depth}    [OK] {filename}")
            else:
                log.warning(f"{'  '*depth}    [FAIL] {filename}")

        next_url = parse_next_page(current_html)
        if not next_url or page_num >= total_pages:
            break
        page_num += 1
        log.info(f"{'  '*depth}  -> Page {page_num}: {next_url}")
        current_html = await load_page(page, next_url)

    for sub_name, sub_url in subfolders:
        _raise_if_cancelling()
        if sub_url not in visited_urls:
            log.info(f"{'  '*depth}  Entering: {sub_name}")
            await crawl_folder(
                page,
                sub_url,
                dest_dir,
                folder_id,
                account_url,
                history_dir,
                metadata_file,
                visited_urls,
                downloaded,
                options,
                depth + 1,
            )


def _append_download_metadata(
    metadata_file: Path,
    filename: str,
    folder_id: str,
    account_url: str,
    detail_url: str,
    media_url: str,
    dest_path: Path,
) -> None:
    """Best-effort metadata write; must not fail the crawl."""
    try:
        append_metadata(
            metadata_file,
            MetadataRecord(
                filename=filename,
                folder_id=folder_id,
                account_url=account_url,
                detail_url=detail_url,
                media_url=media_url,
                dest_path=str(dest_path),
                size_bytes=dest_path.stat().st_size,
                downloaded_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
    except Exception as e:
        log.warning(f"[METADATA] Failed to write metadata for {filename}: {e}")


async def run_account(url: str, dest_dir: Path, folder_id: str,
                       history_dir: Path, downloaded: set,
                       options: CrawlOptions | None = None) -> None:
    """
    Open one Chromium browser for this account, drive the recursive crawl
    over it, and close it when the whole account finishes (success or error).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)
    metadata_file = metadata_history_path(history_dir, folder_id)
    _migrate_legacy_metadata(dest_dir, metadata_file)
    _backfill_existing_files_metadata(dest_dir, folder_id, url, metadata_file)
    options = options or CrawlOptions()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=CHROMIUM_LAUNCH_ARGS)
        page = await browser.new_page()
        visited: set = set()
        try:
            await crawl_folder(
                page,
                url,
                dest_dir,
                folder_id,
                url,
                history_dir,
                metadata_file,
                visited,
                downloaded,
                options,
            )
        finally:
            await page.close()
            await browser.close()


def _backfill_existing_files_metadata(
    dest_dir: Path,
    folder_id: str,
    account_url: str,
    metadata_file: Path,
) -> None:
    """Write metadata rows for files already on disk but missing from metadata.jsonl."""
    recorded = read_recorded_filenames(metadata_file)
    for file_path in sorted(dest_dir.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.name == metadata_file.name:
            continue
        if file_path.name in recorded:
            continue

        _append_download_metadata(
            metadata_file=metadata_file,
            filename=file_path.name,
            folder_id=folder_id,
            account_url=account_url,
            detail_url="",
            media_url="",
            dest_path=file_path,
        )


def _migrate_legacy_metadata(dest_dir: Path, metadata_file: Path) -> None:
    """Move old downloads/<folder>/metadata.jsonl to histrory once."""
    legacy_file = dest_dir / "metadata.jsonl"
    if not legacy_file.exists():
        return
    if metadata_file.exists():
        return
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.replace(metadata_file)
