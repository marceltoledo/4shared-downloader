from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config
from app.api import accounts as accounts_api
from app.api import files as files_api
from app.api import runs as runs_api
from app.auth import require_auth
from app.core.accounts import read_accounts
from app.jobs.manager import job_manager
from app.logging_setup import configure_logging

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield


def create_app() -> FastAPI:
    # FastAPI's auto-generated docs/OpenAPI routes are plain Starlette routes,
    # not APIRoutes, so the app-level `dependencies=` below does not cover
    # them. When auth is actually configured, disable them outright rather
    # than leave an unauthenticated route that dumps the full API surface.
    docs_kwargs = {}
    if config.AUTH_USER or config.AUTH_PASS:
        docs_kwargs = {"docs_url": None, "redoc_url": None, "openapi_url": None}

    app = FastAPI(
        title="4shared Downloader",
        lifespan=lifespan,
        dependencies=[Depends(require_auth)],
        **docs_kwargs,
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(accounts_api.router)
    app.include_router(runs_api.router)
    app.include_router(files_api.router)

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        accounts = read_accounts(config.ACCOUNTS_FILE, config.HISTORY_DIR)
        runs = job_manager.list_jobs()
        return templates.TemplateResponse(
            request, "dashboard.html", {"accounts": accounts, "runs": runs}
        )

    @app.get("/runs/{job_id}", response_class=HTMLResponse)
    def run_detail(request: Request, job_id: str):
        if job_manager.get(job_id) is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return templates.TemplateResponse(request, "run.html", {"job_id": job_id})

    @app.get("/files/{folder_id}", response_class=HTMLResponse)
    def files_page(request: Request, folder_id: str):
        files = files_api.list_files(folder_id)
        return templates.TemplateResponse(
            request, "files.html", {"folder_id": folder_id, "files": files}
        )

    return app


app = create_app()
