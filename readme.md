# 4shared Multi-Account Media Downloader

A local web app for recursively downloading files from public 4shared folder accounts. Add folder URLs through a dashboard, kick off a run, watch it happen live, and browse what got downloaded — all from the browser.

## Features

- **Web dashboard** — manage accounts, trigger runs, and browse results without touching a config file or a terminal.
- **Live monitoring** — watch a run's log stream in real time (Server-Sent Events), with the option to cancel mid-run.
- **Recursive crawling** — follows subfolders and pagination automatically.
- **History-based skipping** — every account remembers what it's already downloaded, so re-running one only fetches what's new.
- **Headless mode** — `cli.py` for cron jobs or scripted runs, no server required.
- **Container-ready** — ships with a `Dockerfile`, built with an eventual Azure Container App deployment in mind.

## Requirements

Python 3.12 or higher.

## Quick Start

```bash
git clone <this repo>
cd 4shared-downloader

python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium

uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**.

> Using a virtual environment isn't optional in practice — if you skip it, make sure whichever `python`/`python3` is first on your `PATH` is the one you installed dependencies into, or the app will fail with `ModuleNotFoundError`.

## Using the Dashboard

| Action | What happens |
|---|---|
| **Add account** | Paste a 4shared folder URL into the form. It's normalized (stray query strings/fragments stripped, doubled-up URLs split apart) and appended to `myaccounts.txt`. |
| **Accounts table** | Lists every account with its folder ID, URL, and download count. New accounts are pre-checked by default; accounts with existing history are unchecked, so re-scanning one is a deliberate choice. |
| **Run selected** | Starts a crawl for the checked accounts and opens a live log view. Only one run can be active at a time — starting another redirects you to the one already in progress. |
| **Cancel** | Stops the active run. Takes effect at the next safe point (typically after the current file finishes), not instantly. |
| **Files** | Click a file count to browse and download everything fetched for that account. |
| **Remove account** | Drops the account from the list only — downloaded files and history are left alone. |

## How It Works

**History & skip system.** Every downloaded file is recorded in `histrory/<folder_id>.metadata.jsonl`. Skip decisions are based on metadata history, **not on what's on disk** — deleting downloaded files won't cause them to be re-fetched. This is deliberate: it lets you re-scan an account later and only pick up files added since your last run.

**URL handling.** Both current (`/folder/<id>/`) and legacy (`_online.html`) 4shared URL formats are accepted, and messy input is cleaned up automatically — query strings and `#` fragments are stripped, double slashes after the domain are fixed, and two URLs accidentally pasted onto one line are split apart.

**Crawling.** A headless Chromium browser (via Playwright) loads folder pages, since 4shared renders its listings with JavaScript. One browser is opened per account and reused across all of its subfolders. Actual file downloads go over plain HTTP, which is much faster than driving a browser per file. Page loads retry up to 3 times before giving up, and a failed account is logged and skipped rather than aborting the whole run.

**Logs.** Every skip, success, and failure is timestamped and written to `download_log.txt` — the same lines shown live on a run's page.

## Command-Line Usage

For a headless run without the web server — a cron job, for example — `cli.py` walks through the same accounts interactively: `y/N` for ones that already have history, auto-queued if brand new.

```bash
python cli.py
```

## Authentication

The app has **no login by default** — fine for local use on your own machine. Before exposing it beyond localhost, set:

```bash
export DOWNLOADER_AUTH_USER=yourusername
export DOWNLOADER_AUTH_PASS=yourpassword
```

With both set, every dashboard page and API route requires HTTP Basic Auth, and the auto-generated `/docs`, `/redoc`, and `/openapi.json` endpoints are disabled outright (they're plain Starlette routes the auth dependency can't otherwise reach). `/static/*` stays open regardless — it's just CSS/JS. With either variable unset, the app is fully open.

## Deployment

A `Dockerfile` is included, running the app under `uvicorn` as a non-root user (Chromium's sandbox won't start as root):

```bash
docker build -t 4shared-downloader .
docker run -p 8000:8000 \
	-v /home/marceltoledo/Python/4shared-downloader:/home/marceltoledo/Python/4shared-downloader \
	--env-file .env \
	4shared-downloader
```

`DOWNLOADER_DATA_DIR` (defaults to `/home/marceltoledo/Python/4shared-downloader`) controls where `myaccounts.txt`, `downloads/`, `histrory/`, and `download_log.txt` live — point it at a mounted volume so data survives restarts. If a bind-mounted host directory isn't writable inside the container, `chown` it to UID 1000 or run with `--user $(id -u):$(id -g)`.

> The image builds a working container in principle but hasn't been build-tested end to end — verify it once yourself before relying on it.

The intended eventual home is an **Azure Container App** rather than Azure Functions, since the headless-Chromium, long-running-crawl workload doesn't suit a consumption-plan function. Two things matter there:
- **`max_replicas` must stay at 1.** The single-active-run lock lives in this process's memory; more than one replica would let each start its own run independently.
- **Set the auth env vars as secrets.** There's no other access control once this is reachable off your machine.

