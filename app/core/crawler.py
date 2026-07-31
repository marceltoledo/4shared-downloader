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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

from app.config import CHROMIUM_LAUNCH_ARGS
from app.core.browser import get_direct_media_url, load_page
from app.core.downloader import download_to_disk, safe_filename
from app.core.filters import CrawlOptions, categorize_extension, matches
from app.core.history import record_download
from app.core.metadata import MetadataRecord, append_metadata
from app.core.parsing import (
    parse_file_cards,
    parse_next_page,
    parse_subfolder_cards,
    parse_total_pages,
)

log = logging.getLogger(__name__)


@dataclass
class AccountCrawlContext:
    """
    Bundles everything that's constant across one account's whole recursive
    crawl, plus the account-scoped mutable state (visited_urls, downloaded,
    downloaded_count). CrawlOptions itself stays frozen/immutable — it holds
    only run-level filter config, so the same instance is shared unchanged
    across every account in a run.
    """

    dest_dir: Path
    folder_id: str
    history_dir: Path
    account_url: str
    metadata_file: Path
    options: CrawlOptions
    visited_urls: set = field(default_factory=set)
    downloaded: set = field(default_factory=set)
    downloaded_count: int = 0

    def limit_reached(self) -> bool:
        return self.options.limit is not None and self.downloaded_count >= self.options.limit


async def crawl_folder(page, url: str, ctx: AccountCrawlContext, depth: int = 0) -> None:
    """
    Crawl a folder page (all paginated pages) then recurse into subfolders.

    ctx.downloaded: set of lowercased filenames from this account's history
                    file. Strictly skipped regardless of disk state.
                    Successful downloads are added here AND written to
                    history file.
    """
    if ctx.limit_reached():
        return

    if url in ctx.visited_urls:
        log.info(f"{'  '*depth}[SKIP] Already visited: {url}")
        return
    ctx.visited_urls.add(url)

    log.info(f"{'  '*depth}Crawling: {url}")
    html = await load_page(page, url)

    total_pages = parse_total_pages(html)
    log.info(f"{'  '*depth}  Total pages: {total_pages}")

    subfolders = parse_subfolder_cards(html)
    log.info(f"{'  '*depth}  Subfolders found: {len(subfolders)}")

    current_html = html
    page_num = 1

    while True:
        files = parse_file_cards(current_html)
        log.info(f"{'  '*depth}  Page {page_num}: {len(files)} media file(s)")

        for filename, detail_url in files:
            if ctx.limit_reached():
                log.info(
                    f"{'  '*depth}    [LIMIT] Reached {ctx.options.limit} new file(s) "
                    f"for {ctx.folder_id} — stopping this account"
                )
                return

            if filename.lower() in ctx.downloaded:
                log.info(f"{'  '*depth}    [SKIP] {filename}")
                continue

            if not matches(filename, ctx.options):
                log.debug(f"{'  '*depth}    [FILTERED] {filename}")
                continue

            log.info(f"{'  '*depth}    Fetching URL: {filename}")
            media_url = await get_direct_media_url(page, detail_url)

            if not media_url:
                log.warning(f"{'  '*depth}    [FAIL] No URL for {filename}")
                continue

            dest_path = safe_filename(filename, ctx.dest_dir)
            ok = await asyncio.to_thread(download_to_disk, media_url, dest_path)
            if ok:
                ctx.downloaded.add(filename.lower())
                record_download(ctx.history_dir, ctx.folder_id, filename)
                ctx.downloaded_count += 1
                _write_metadata(ctx, filename, detail_url, dest_path, depth)
                log.info(f"{'  '*depth}    [OK] {filename}")
            else:
                log.warning(f"{'  '*depth}    [FAIL] {filename}")

        next_url = parse_next_page(current_html)
        if not next_url or page_num >= total_pages or ctx.limit_reached():
            break
        page_num += 1
        log.info(f"{'  '*depth}  -> Page {page_num}: {next_url}")
        current_html = await load_page(page, next_url)

    if ctx.limit_reached():
        return

    for sub_name, sub_url in subfolders:
        if ctx.limit_reached():
            return
        if sub_url not in ctx.visited_urls:
            log.info(f"{'  '*depth}  Entering: {sub_name}")
            await crawl_folder(page, sub_url, ctx, depth + 1)


def _write_metadata(ctx: AccountCrawlContext, filename: str, detail_url: str,
                     dest_path: Path, depth: int) -> None:
    """
    Append a metadata record for a successful download. A write failure here
    must never look like a failed download or abort the rest of the crawl —
    the file is already safely on disk and in the history file.
    """
    try:
        ext = Path(filename).suffix.lower()
        record = MetadataRecord(
            filename=filename,
            folder_id=ctx.folder_id,
            account_url=ctx.account_url,
            detail_url=detail_url,
            dest_path=str(dest_path),
            size_bytes=dest_path.stat().st_size,
            extension=ext,
            category=categorize_extension(ext),
            downloaded_at=datetime.now(timezone.utc).isoformat(),
        )
        append_metadata(ctx.metadata_file, record)
    except Exception as e:
        log.warning(f"{'  '*depth}    [METADATA] Failed to record metadata for {filename}: {e}")


async def run_account(url: str, dest_dir: Path, folder_id: str,
                       history_dir: Path, downloaded: set, metadata_file: Path,
                       options: CrawlOptions | None = None) -> None:
    """
    Open one Chromium browser for this account, drive the recursive crawl
    over it, and close it when the whole account finishes (success or error).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    ctx = AccountCrawlContext(
        dest_dir=dest_dir,
        folder_id=folder_id,
        history_dir=history_dir,
        account_url=url,
        metadata_file=metadata_file,
        options=options or CrawlOptions(),
        downloaded=downloaded,
    )

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=CHROMIUM_LAUNCH_ARGS)
        page = await browser.new_page()
        try:
            await crawl_folder(page, url, ctx)
        finally:
            await page.close()
            await browser.close()
