# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local FastAPI web app that recursively crawls public 4shared folder URLs and downloads every file found — no file-type filtering. Accounts (folder URLs) are managed through the dashboard, runs are triggered and monitored live via Server-Sent Events, and results are browsable in the same UI. A thin `cli.py` preserves the original headless/scripted interactive flow for cron-style use. Originally a single-file CLI script; converted to a web app so it can eventually be containerized and deployed as a personal service (Azure Container App).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run the web app (http://127.0.0.1:8000)
uvicorn app.main:app --reload

# Run the headless CLI instead
python cli.py

# Run tests
pytest

# Run a single test
pytest tests/test_urls.py::test_normalize_url_splits_doubled_urls_on_one_line

# Docker
docker build -t 4shared-downloader .
docker run -p 8000:8000 -v $(pwd)/data:/data 4shared-downloader
```

There is no lint config in this repo.

## Architecture

**`app/core/`** holds all crawling/parsing logic with zero FastAPI imports and zero import-time side effects (no `logging.basicConfig()` at module scope) — this is what makes it importable by both the web app and `cli.py`, and testable without a running server:

- `urls.py` — `normalize_url()` / `folder_id_from_url()`. Handles messy `myaccounts.txt` input: doubled URLs joined on one line, stray query/hash fragments, double slashes, old (`_online.html`) vs new (`/folder/<id>/`) 4shared URL styles. `folder_id_from_url()` extracts the stable path segment used to name both the download directory and the history file.
- `history.py` — per-account history at `history_files/<folder_id>.txt`, one lowercased filename per line. **This is the source of truth for skip logic, not disk state** — deleting downloaded files does not cause re-download. Directory is passed as a parameter, not a hardcoded global.
- `parsing.py` — pure BeautifulSoup parsers for 4shared's page structure (file cards, subfolder cards, pagination). No side effects; covered by `tests/test_parsing.py`.
- `downloader.py` — `safe_filename()` (collision-safe naming) and `download_to_disk()` (streamed `requests` download). Synchronous by design — see `crawler.py`.
- `browser.py` — `load_page()` (Playwright page load with retry + scroll-to-bottom to force lazy-loaded cards to render) and `get_direct_media_url()` (HTTP fast path via `requests.Session`, falling back to the browser only if that fails). The fast-path HTTP call runs via `asyncio.to_thread` — this matters under `uvicorn` (unlike the original one-shot CLI process) because the same event loop also serves the SSE log stream, and a blocking call on it would stall that stream.
- `crawler.py` — `crawl_folder()` recurses through subfolders reusing **one already-open Playwright page for the whole account**, not one browser per recursion level (the original script opened a fresh browser per recursive call, which could mean several concurrent Chromium instances for a deeply nested account — fine in a one-shot CLI, risky in a long-lived container). `run_account()` is the entry point: opens the single browser, drives the crawl, closes it when the account finishes or errors. Downloads inside a crawl stay strictly sequential (`asyncio.to_thread` per download, no `asyncio.gather`) since the shared `requests.Session` isn't thread-safe and interleaving would scramble the live log ordering.
- `accounts.py` — `read_accounts()` / `add_account()` / `remove_account()` against `myaccounts.txt`, replacing hand-editing the file. Dedupes by normalized URL (first line wins), matching the original CLI's dedup behavior.

**`app/jobs/manager.py`** — in-memory `JobManager`, a single global instance (`job_manager`). **Only one job may be active at a time**; a second `start()` while one is running raises `JobAlreadyRunningError` (surfaced as HTTP 409 with the running job's id). This isn't just a UX choice — it's load-bearing if this is ever deployed with more than one replica, since the lock lives in process memory (`max_replicas` must stay 1). Log lines from a running job are captured by a per-job `logging.Handler` and fanned out to SSE subscribers; because downloads run via `asyncio.to_thread`, log records can arrive from a worker thread, so the handler hops back onto the event loop with `call_soon_threadsafe` rather than touching `asyncio.Queue` objects directly from `emit()`. Job/run metadata (status, timestamps, live log ring buffer) is **in-memory only** and lost on restart — acceptable because the data that matters for browsing history (`history_files/`, `downloads/`, `download_log.txt`) is already file-backed regardless.

**`app/api/`** — FastAPI routers: `accounts.py` (CRUD over `myaccounts.txt`), `runs.py` (trigger/list/detail/SSE stream/cancel), `files.py` (list/download files per account). Every filesystem-touching route in `files.py` validates `folder_id` against `^[A-Za-z0-9_\-]+$` and checks the resolved path is still inside `DOWNLOAD_DIR` (`Path.is_relative_to`) before touching disk — both `folder_id` and `filename` are attacker-controlled URL path segments.

**`app/main.py`** — FastAPI app factory. Auth (`app/auth.py`) is applied once at the app level (`dependencies=[Depends(require_auth)]`), covering the dashboard pages and all `app/api/*` routers; it's a no-op when `DOWNLOADER_AUTH_USER`/`DOWNLOADER_AUTH_PASS` are both unset. FastAPI's `/docs`/`/redoc`/`/openapi.json` are plain Starlette routes that the app-level dependency does **not** reach, so `create_app()` disables them outright (`docs_url=None` etc.) whenever auth is actually configured, rather than leaving them open. The `/static` mount is intentionally left unauthenticated in all cases — it only serves CSS/JS. Logging is configured once via `app/logging_setup.py`, shared with `cli.py` so both write the same format to `download_log.txt`/stdout.

**`app/config.py`** — all data paths (`ACCOUNTS_FILE`, `DOWNLOAD_DIR`, `HISTORY_DIR`, `LOG_FILE`) derive from `DATA_DIR`, which defaults to the repo root resolved via `Path(__file__)` rather than `"."` — a `.`-relative default would silently create a second, empty data tree if the process's cwd isn't the repo root. Overridable via `DOWNLOADER_DATA_DIR` (used in the container, pointing at a mounted volume).

**Templates/static** (`app/templates/`, `app/static/`) — plain Jinja2 + vanilla JS, no SPA/build toolchain. `app.js` handles the small amount of interactivity that genuinely needs it: `fetch()` calls for add/remove-account and run-trigger/cancel, and one `EventSource` for the live log stream on the run detail page.

## Key files

- `myaccounts.txt` — list of 4shared folder URLs (managed via the dashboard now, not hand-edited)
- `downloads/<folder_id>/`, `history_files/<folder_id>.txt`, `download_log.txt` — runtime output, gitignored
- `cli.py` — headless entry point built on the same `app.core` modules
- `tests/test_urls.py`, `tests/test_parsing.py` — cover the pure functions only; `crawler.py`/`browser.py` aren't unit-tested (would need live network or heavy Playwright mocking) — verify those manually by running a real crawl through the UI
