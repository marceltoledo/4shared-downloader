"""
4shared Multi-Account Media Downloader
=======================================
- Reads public folder URLs from myaccounts.txt (one per line)
- Recursively crawls all subfolders and paginated pages
- Each account gets its own download folder named by folder ID (stable)
- Per-account history files track every file ever downloaded
  -> Skips are based on history, not disk - deleting files won't cause re-downloads
- Logs results to download_log.txt

Speed note: detail pages are fetched with plain HTTP requests (no browser),
which is ~10x faster than the previous approach. Browser is only used for
folder page crawling (which requires JS for lazy loading).

Requirements:
    pip install playwright requests beautifulsoup4
    playwright install chromium
"""

import os
import re
import asyncio
import requests
import logging
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# -- Config -------------------------------------------------------------------
ACCOUNTS_FILE = "myaccounts.txt"
DOWNLOAD_DIR  = "./downloads"
HISTORY_DIR   = "./history_files"   # one .txt file per account
LOG_FILE      = "download_log.txt"

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi", ".mkv"}

# -- Logging ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# -- Shared HTTP session ------------------------------------------------------
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})


# -- Per-account history helpers ----------------------------------------------

def history_path(folder_id: str) -> str:
    return os.path.join(HISTORY_DIR, f"{folder_id}.txt")


def load_history(folder_id: str) -> set:
    """
    Load the set of filenames (lowercased) ever successfully downloaded
    for this account. Returns empty set if no history file exists yet.
    """
    path = history_path(folder_id)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}


def record_download(folder_id: str, filename: str):
    """Append a filename to this account's history file."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    with open(history_path(folder_id), "a", encoding="utf-8") as f:
        f.write(filename.lower() + "\n")


# -- HTML Parsers -------------------------------------------------------------

def parse_file_cards(html: str):
    """
    Parse media file cards from the new-style public folder page.
    Returns list of (filename, detail_url).
    """
    soup = BeautifulSoup(html, "html.parser")
    files = []
    for card in soup.find_all("div", class_=lambda c: c and "jsCardItem" in c.split()):
        name_div = card.find("div", class_=lambda c: c and "jsFileName" in c.split())
        if not name_div:
            continue
        filename = name_div.get_text(strip=True)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXT:
            continue
        link = card.find("a", class_=lambda c: c and "jsGoFile" in c.split())
        if not link or not link.get("href"):
            continue
        href = link["href"]
        if not href.startswith("http"):
            href = "https://www.4shared.com" + href
        files.append((filename, href))
    return files


def parse_subfolder_cards(html: str):
    """
    Parse subfolder cards from the new-style public folder page.
    Returns list of (folder_name, folder_url).
    """
    soup = BeautifulSoup(html, "html.parser")
    folders = []
    for card in soup.find_all("div", class_=lambda c: c and "dir-card" in c.split()):
        link = card.find("a", class_=lambda c: c and "jsFolderLink" in c.split())
        if not link or not link.get("href"):
            continue
        href = link["href"]
        if not href.startswith("http"):
            href = "https://www.4shared.com" + href
        name_div = card.find("div", class_="dir-name")
        folder_name = name_div.get_text(strip=True) if name_div else href
        folders.append((folder_name, href))
    return folders


def parse_next_page(html: str):
    soup = BeautifulSoup(html, "html.parser")
    inp = soup.find("input", class_="jsNextPageLink")
    if inp and inp.get("value"):
        path = inp["value"]
        if path.startswith("http"):
            return path
        return "https://www.4shared.com" + path
    return None


def parse_total_pages(html: str):
    soup = BeautifulSoup(html, "html.parser")
    inp = soup.find("input", class_="jsPagesTotalCount")
    if inp and inp.get("value"):
        try:
            return int(inp["value"])
        except ValueError:
            pass
    return 1


# -- Detail page URL extraction -----------------------------------------------

def _parse_media_url_from_html(html: str):
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img", class_="jsFilePreviewImage")
    if img and img.get("src"):
        return img["src"]
    vid = soup.find("video")
    if vid:
        if vid.get("src"):
            return vid["src"]
        src_tag = vid.find("source")
        if src_tag and src_tag.get("src"):
            return src_tag["src"]
    m = re.search(r'https://dc\d+\.4shared\.com/(?:download|img)/[^\s"\'&]+', html)
    if m:
        return m.group(0)
    return None


async def get_direct_media_url(page, detail_url: str):
    """Fast path via requests, browser fallback if needed."""
    try:
        r = _session.get(detail_url, timeout=15)
        if r.status_code == 200:
            media_url = _parse_media_url_from_html(r.text)
            if media_url:
                return media_url
    except Exception as e:
        log.debug(f"  Fast-path failed ({e}), trying browser")

    log.debug(f"  Browser fallback: {detail_url}")
    try:
        await page.goto(detail_url)
        await page.wait_for_selector("img.jsFilePreviewImage, video", timeout=12000)
    except Exception:
        log.warning(f"  Detail page load failed: {detail_url}")
        return None

    media_url = await page.evaluate("""
        () => {
            const img = document.querySelector("img.jsFilePreviewImage");
            if (img && img.src) return img.src;
            const vid = document.querySelector("video");
            if (vid && vid.src) return vid.src;
            const src = document.querySelector("video source");
            if (src && src.src) return src.src;
            return null;
        }
    """)
    return media_url or None


# -- Browser helpers ----------------------------------------------------------

async def load_page(page, url: str) -> str:
    for attempt in range(3):
        try:
            await page.goto(url, timeout=45000)
            break
        except Exception as e:
            if attempt == 2:
                raise
            log.warning(f"  Timeout on attempt {attempt + 1}, retrying in 3s: {url}")
            await page.wait_for_timeout(3000)
    try:
        await page.wait_for_selector("div.jsCardItem, div.dir-card", timeout=15000)
    except Exception:
        log.warning(f"  No cards detected (page may be empty): {url}")
    prev = 0
    for _ in range(20):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(600)
        cur = await page.evaluate("document.body.scrollHeight")
        if cur == prev:
            break
        prev = cur
    return await page.content()


# -- Downloader ---------------------------------------------------------------

def safe_filename(name: str, dest_dir: str) -> str:
    """Return a unique path in dest_dir, appending _2, _3 etc. on collision."""
    base, ext = os.path.splitext(name)
    candidate = os.path.join(dest_dir, name)
    counter = 2
    while os.path.exists(candidate):
        candidate = os.path.join(dest_dir, f"{base}_{counter}{ext}")
        counter += 1
    return candidate


def download_to_disk(url: str, dest_path: str) -> bool:
    try:
        r = _session.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        return True
    except Exception as e:
        log.error(f"  Download error: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


# -- Recursive folder crawler -------------------------------------------------

async def crawl_folder(playwright, url: str, dest_dir: str,
                       folder_id: str, visited_urls: set,
                       downloaded: set, depth: int = 0):
    """
    Crawl a folder page (all paginated pages) then recurse into subfolders.

    downloaded: set of lowercased filenames from this account's history file.
                Strictly skipped regardless of disk state.
                Successful downloads are added here AND written to history file.
    """
    if url in visited_urls:
        log.info(f"{'  '*depth}[SKIP] Already visited: {url}")
        return
    visited_urls.add(url)

    browser = await playwright.chromium.launch(headless=True)
    page    = await browser.new_page()

    try:
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
                if filename.lower() in downloaded:
                    log.info(f"{'  '*depth}    [SKIP] {filename}")
                    continue

                log.info(f"{'  '*depth}    Fetching URL: {filename}")
                media_url = await get_direct_media_url(page, detail_url)

                if not media_url:
                    log.warning(f"{'  '*depth}    [FAIL] No URL for {filename}")
                    continue

                dest_path = safe_filename(filename, dest_dir)
                ok = download_to_disk(media_url, dest_path)
                if ok:
                    downloaded.add(filename.lower())
                    record_download(folder_id, filename)  # persist to history
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
            if sub_url not in visited_urls:
                log.info(f"{'  '*depth}  Entering: {sub_name}")
                await crawl_folder(playwright, sub_url, dest_dir,
                                   folder_id, visited_urls, downloaded, depth + 1)

    finally:
        await page.close()
        await browser.close()


# -- URL helpers --------------------------------------------------------------

def folder_id_from_url(url: str) -> str:
    """
    Extract the stable 4shared folder ID from a URL.
    e.g. https://www.4shared.com/folder/F6YhfbPq/_online.html -> F6YhfbPq
    """
    m = re.search(r"/folder/([A-Za-z0-9_\-]+)/", url)
    if m:
        return m.group(1)
    return re.sub(r"[^\w\-]", "_", url)[-40:]


def normalize_url(raw: str) -> str:
    """
    Accept any 4shared folder URL format and return a clean, single URL.
    Fixes accidentally joined URLs (two https:// on the same line),
    double slashes after domain, and hash/query fragments.
    """
    raw = raw.strip()

    # Fix doubled URLs e.g. "...html https://..." or "...htmlhttps://..."
    # Keep only the first URL if two are joined on one line
    m = re.search(r'(https?://\S+?\.html)\S*https?://', raw)
    if m:
        raw = m.group(1)

    # Remove hash fragments and query strings
    raw = re.sub(r"[?#].*$", "", raw)

    # Fix double slashes after domain
    raw = re.sub(r"(https://www\.4shared\.com)//+", r"\1/", raw)

    # New-style /folder/ URL — return as-is
    if re.search(r"4shared\.(com|io)/folder/[A-Za-z0-9_\-]+/", raw):
        return raw

    # Old _online.html style
    m = re.search(r"folder/([A-Za-z0-9_\-]+)/_online", raw)
    if m:
        folder_id = m.group(1)
        return f"https://www.4shared.com/folder/{folder_id}/_online.html"

    return raw


# -- Main ---------------------------------------------------------------------

async def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)

    if not os.path.exists(ACCOUNTS_FILE):
        log.error(f"'{ACCOUNTS_FILE}' not found. Create it with one folder URL per line.")
        return

    # Read and deduplicate accounts
    seen = set()
    unique_lines = []
    with open(ACCOUNTS_FILE, encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            norm = normalize_url(raw)
            if norm not in seen:
                seen.add(norm)
                unique_lines.append(raw)

    if not unique_lines:
        log.error(f"No URLs found in {ACCOUNTS_FILE}")
        return

    log.info(f"Loaded {len(unique_lines)} unique account URL(s)")

    # -- Upfront review -------------------------------------------------------
    accounts_to_run = []

    print("\n" + "=" * 60)
    print("  ACCOUNT REVIEW — answer all questions before downloading")
    print("=" * 60)

    for i, line in enumerate(unique_lines, 1):
        url         = normalize_url(line)
        folder_id   = folder_id_from_url(url)
        account_dir = os.path.join(DOWNLOAD_DIR, folder_id)

        # History file is the source of truth, not the disk
        history       = load_history(folder_id)
        history_count = len(history)

        print(f"\n  Account {i} [{folder_id}]: {url}")

        if history_count > 0:
            print(f"  History: {history_count} file(s) previously downloaded")
            print(f"  (Only NEW files will be fetched — history entries are")
            print(f"   strictly skipped even if deleted from disk)")
            answer = input(f"  Run this account? (y/N): ").strip().lower()
            if answer == "y":
                accounts_to_run.append((i, url, account_dir, folder_id))
                print(f"  -> Queued")
            else:
                print(f"  -> Skipped")
        else:
            print(f"  No history found — new account, will download everything.")
            accounts_to_run.append((i, url, account_dir, folder_id))

    print("\n" + "=" * 60)

    if not accounts_to_run:
        print("  Nothing to do. Exiting.")
        return

    print(f"  Running {len(accounts_to_run)} account(s): "
          f"{[a[0] for a in accounts_to_run]}")
    print("=" * 60 + "\n")

    # -- Run selected accounts ------------------------------------------------
    async with async_playwright() as pw:
        for i, url, account_dir, folder_id in accounts_to_run:
            os.makedirs(account_dir, exist_ok=True)

            downloaded = load_history(folder_id)

            log.info(f"\n{'='*60}")
            log.info(f"[Account {i} / {folder_id}] {url}")
            log.info(f"  Download folder : {account_dir}")
            log.info(f"  History file    : {history_path(folder_id)}")
            log.info(f"  Already seen    : {len(downloaded)} file(s) — strictly skipped")
            log.info(f"{'='*60}")

            visited = set()
            try:
                await crawl_folder(pw, url, account_dir, folder_id, visited, downloaded)
            except Exception as e:
                log.error(f"[Account {i}] Fatal error, skipping to next account: {e}")

    log.info("\nAll done! Check download_log.txt for details.")


if __name__ == "__main__":
    asyncio.run(main())