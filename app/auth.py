"""
Optional HTTP Basic Auth, applied app-wide.

No-op when DOWNLOADER_AUTH_USER/DOWNLOADER_AUTH_PASS are both unset, so local
dev stays frictionless. Once this app is deployed anywhere reachable off the
local machine (e.g. an Azure Container App), both must be set — the app
otherwise serves a personal media library with no access control at all.
"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app import config

_security = HTTPBasic(auto_error=False)


def require_auth(credentials: HTTPBasicCredentials | None = Depends(_security)) -> None:
    if config.AUTH_USER is None and config.AUTH_PASS is None:
        return

    valid = (
        credentials is not None
        and secrets.compare_digest(credentials.username, config.AUTH_USER or "")
        and secrets.compare_digest(credentials.password, config.AUTH_PASS or "")
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
