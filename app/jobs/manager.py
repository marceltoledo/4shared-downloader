"""
In-memory job orchestration for web-triggered crawl runs.

Only one job may be active at a time — a second run while one is in progress
is rejected with JobAlreadyRunningError, surfaced as HTTP 409 by the API
layer. Rationale: headless Chromium is heavy, this is a personal single-user
tool, and interleaved logs from two simultaneous crawls would be genuinely
hard to follow in one live stream anyway. This also matters if this app is
ever scaled past one replica in Azure Container Apps: the lock lives in this
process's memory, so max_replicas must stay at 1 or the guarantee breaks.

Job/run metadata (status, timestamps, live log lines) lives only in memory
and is lost on restart — acceptable because the data that actually matters
for browsing history/results (histrory/, downloads/, download_log.txt)
is already file-backed and unaffected by this.
"""

import asyncio
import contextlib
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app import config
from app.core.accounts import read_accounts
from app.core.crawler import run_account
from app.core.filters import CrawlOptions, FileType
from app.core.history import load_history

log = logging.getLogger(__name__)

LOG_RING_SIZE = 2000
SUBSCRIBER_QUEUE_MAXSIZE = 500


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


ACTIVE_STATUSES = (JobStatus.PENDING, JobStatus.RUNNING)


@dataclass
class Job:
    id: str
    folder_ids: list[str]
    status: JobStatus = JobStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    task: asyncio.Task | None = None
    log_lines: deque = field(default_factory=lambda: deque(maxlen=LOG_RING_SIZE))
    subscribers: list[asyncio.Queue] = field(default_factory=list)


class JobAlreadyRunningError(Exception):
    def __init__(self, job_id: str):
        super().__init__(f"A job is already running: {job_id}")
        self.job_id = job_id


def _push(queue: asyncio.Queue, item) -> None:
    """Put an item on a bounded queue, dropping the oldest entry if full
    rather than back-pressuring the crawl because one SSE client is slow."""
    if queue.full():
        with contextlib.suppress(asyncio.QueueEmpty):
            queue.get_nowait()
    with contextlib.suppress(asyncio.QueueFull):
        queue.put_nowait(item)


class _QueueLogHandler(logging.Handler):
    """
    Captures log records for one job's duration and fans them out to any SSE
    subscribers. Records may be emitted from a worker thread (downloads run
    via asyncio.to_thread), so emit() can't touch asyncio objects directly —
    it hops back onto the event loop via call_soon_threadsafe.
    """

    def __init__(self, job: Job, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self._job = job
        self._loop = loop
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            formatted = self.format(record)
        except Exception:
            return
        self._loop.call_soon_threadsafe(self._fanout, formatted)

    def _fanout(self, formatted: str) -> None:
        for line in formatted.split("\n"):
            self._job.log_lines.append(line)
            for q in list(self._job.subscribers):
                _push(q, line)


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._active_job_id: str | None = None

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.started_at or datetime.min, reverse=True)

    async def start(self, folder_ids: list[str], name_filter: str | None = None,
                    file_type: FileType = "all") -> Job:
        if self._active_job_id is not None:
            active = self._jobs[self._active_job_id]
            if active.status in ACTIVE_STATUSES:
                raise JobAlreadyRunningError(self._active_job_id)

        job = Job(id=str(uuid.uuid4()), folder_ids=folder_ids)
        self._jobs[job.id] = job
        self._active_job_id = job.id

        loop = asyncio.get_running_loop()
        handler = _QueueLogHandler(job, loop)
        options = CrawlOptions(name_filter=name_filter, file_type=file_type)
        job.task = asyncio.create_task(self._run(job, handler, options))
        return job

    async def _run(self, job: Job, handler: logging.Handler, options: CrawlOptions) -> None:
        root_log = logging.getLogger()
        root_log.addHandler(handler)
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        try:
            accounts = {a.folder_id: a for a in read_accounts(config.ACCOUNTS_FILE, config.HISTORY_DIR)}
            for folder_id in job.folder_ids:
                account = accounts.get(folder_id)
                if account is None:
                    log.warning(f"[Job {job.id}] Unknown folder_id, skipping: {folder_id}")
                    continue

                dest_dir = config.DOWNLOAD_DIR / folder_id
                downloaded = load_history(config.HISTORY_DIR, folder_id)

                log.info(f"\n{'='*60}")
                log.info(f"[Account {folder_id}] {account.url}")
                log.info(f"  Already seen : {len(downloaded)} file(s) — strictly skipped")
                log.info(f"{'='*60}")

                try:
                    await run_account(
                        account.url, dest_dir, folder_id, config.HISTORY_DIR, downloaded, options
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    log.error(f"[Account {folder_id}] Fatal error, skipping to next account: {e}")

            job.status = JobStatus.DONE
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
        except Exception as e:
            job.status = JobStatus.ERROR
            job.error = str(e)
        finally:
            job.finished_at = datetime.now(timezone.utc)
            root_log.removeHandler(handler)
            if self._active_job_id == job.id:
                self._active_job_id = None
            for q in list(job.subscribers):
                _push(q, None)  # sentinel: tells subscribers the stream ended

    async def subscribe(self, job_id: str):
        job = self._jobs.get(job_id)
        if job is None:
            return
        for line in list(job.log_lines):
            yield line
        if job.status not in ACTIVE_STATUSES:
            return

        queue: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_MAXSIZE)
        job.subscribers.append(queue)
        try:
            while True:
                line = await queue.get()
                if line is None:
                    break
                yield line
        finally:
            with contextlib.suppress(ValueError):
                job.subscribers.remove(queue)

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None or job.task is None or job.status not in ACTIVE_STATUSES:
            return False
        job.task.cancel()
        return True


job_manager = JobManager()
