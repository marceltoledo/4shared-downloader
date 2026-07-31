"""
Playwright-dependent helpers: loading folder pages (JS-rendered lazy loading)
and resolving a file's direct media URL.

Detail pages are fetched with plain HTTP requests first — much faster than
driving a browser per file — falling back to the browser only if that fails.
The HTTP call is run via asyncio.to_thread so it can't block the event loop
(and therefore the SSE log stream) that a long-lived web server shares across
requests, unlike the original one-shot CLI process where this didn't matter.
"""

import asyncio
import logging

from app.core.downloader import _session
from app.core.parsing import _parse_media_url_from_html

log = logging.getLogger(__name__)


async def get_direct_media_url(page, detail_url: str):
    """Fast path via requests, browser fallback if needed."""
    try:
        r = await asyncio.to_thread(_session.get, detail_url, timeout=15)
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


async def load_page(page, url: str) -> str:
    for attempt in range(3):
        try:
            await page.goto(url, timeout=45000)
            break
        except Exception:
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
