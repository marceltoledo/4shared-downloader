# syntax=docker/dockerfile:1
# 4shared Downloader — web app container image
# Build: docker build -t 4shared-downloader .
# Run:   docker run -p 8000:8000 -v /home/marceltoledo/Python/4shared-downloader:/home/marceltoledo/Python/4shared-downloader --env-file .env 4shared-downloader

# ── Stage 1: dependencies ─────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /srv

ENV PYTHONPATH=/srv
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
ENV DOWNLOADER_DATA_DIR=/home/marceltoledo/Python/4shared-downloader

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Playwright resolves its own apt dependency list per Chromium version, which
# is more reliable than hand-listing the ~20 shared libs it needs. Must run as
# root (apt-get), before the USER switch below.
RUN playwright install --with-deps chromium

COPY app/ /srv/app/
COPY cli.py /srv/cli.py

# Run as non-root so Chromium can use its own sandbox (headless Chromium
# refuses --sandbox as root, and running with --no-sandbox instead is the
# weaker option Playwright itself recommends against). The default data path
# is host-mount-friendly so downloads and history persist outside the container.
# That directory is created and owned by the runtime user here so mounted files
# are writable when permissions allow.
RUN useradd --create-home --uid 1000 downloader \
 && mkdir -p /home/marceltoledo/Python/4shared-downloader \
 && chown -R downloader:downloader /srv /opt/pw-browsers /home/marceltoledo/Python/4shared-downloader
USER downloader

EXPOSE 8000
ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
