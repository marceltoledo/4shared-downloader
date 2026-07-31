import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.core.filters import FileType
from app.core.paths import InvalidDestDirError
from app.jobs.manager import Job, JobAlreadyRunningError, JobStatus, job_manager

router = APIRouter(prefix="/api/runs", tags=["runs"])


class RunIn(BaseModel):
    folder_ids: list[str]
    name_filter: str | None = None
    file_type: FileType = "all"
    limit: int | None = Field(default=None, gt=0)
    dest_dir: str | None = None

    @field_validator("name_filter")
    @classmethod
    def _clean_name_filter(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() or None

    @field_validator("dest_dir")
    @classmethod
    def _clean_dest_dir(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not Path(v).is_absolute():
            raise ValueError("dest_dir must be an absolute path")
        return v


class RunOut(BaseModel):
    id: str
    folder_ids: list[str]
    status: JobStatus
    started_at: str | None
    finished_at: str | None
    error: str | None
    name_filter: str | None
    file_type: str
    limit: int | None
    dest_dir: str | None


def _to_out(job: Job) -> RunOut:
    return RunOut(
        id=job.id,
        folder_ids=job.folder_ids,
        status=job.status,
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        error=job.error,
        name_filter=job.name_filter,
        file_type=job.file_type,
        limit=job.limit,
        dest_dir=job.dest_dir,
    )


@router.post("", status_code=201)
async def start_run(body: RunIn):
    if not body.folder_ids:
        raise HTTPException(status_code=400, detail="folder_ids must not be empty")
    try:
        job = await job_manager.start(
            body.folder_ids,
            name_filter=body.name_filter,
            file_type=body.file_type,
            limit=body.limit,
            dest_dir=body.dest_dir,
        )
    except JobAlreadyRunningError as e:
        raise HTTPException(
            status_code=409,
            detail={"message": "A job is already running", "job_id": e.job_id},
        ) from e
    except InvalidDestDirError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"job_id": job.id}


@router.get("", response_model=list[RunOut])
def list_runs():
    return [_to_out(j) for j in job_manager.list_jobs()]


@router.get("/{job_id}", response_model=RunOut)
def get_run(job_id: str):
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return _to_out(job)


@router.get("/{job_id}/stream")
async def stream_run(job_id: str):
    if job_manager.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_source():
        agen = job_manager.subscribe(job_id)
        try:
            while True:
                try:
                    line = await asyncio.wait_for(agen.__anext__(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                except StopAsyncIteration:
                    break
                yield f"data: {line}\n\n"

            # The generator only ends this way once the job has reached a
            # terminal status (or already had, before this client connected).
            # Send an explicit named event so the client closes proactively —
            # otherwise EventSource's default auto-reconnect would open a new
            # subscription right after this one closes and replay the whole
            # ring buffer again, showing duplicated log lines.
            job = job_manager.get(job_id)
            status = job.status.value if job else "unknown"
            yield f"event: end\ndata: {status}\n\n"
        finally:
            await agen.aclose()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{job_id}/cancel", status_code=202)
def cancel_run(job_id: str):
    if not job_manager.cancel(job_id):
        raise HTTPException(status_code=404, detail="Run not found or not active")
    return {"status": "cancelling"}
