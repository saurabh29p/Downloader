"""Settings endpoints. Phase 4: an optional cookies.txt for sites you are logged in to.

The file is stored in the data folder with 0600 permissions. Its content is never
returned by the API and never logged; only whether it exists and when it changed.
"""

import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from anyget.api.deps import ERROR_RESPONSES, ServicesDep
from anyget.handlers.ytdlp import cookies_path

router = APIRouter(tags=["settings"])

MAX_COOKIES_BYTES = 1024 * 1024


class CookiesUpload(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_COOKIES_BYTES, repr=False)


class CookiesStatus(BaseModel):
    present: bool
    updated_at: datetime | None = None
    lines: int | None = None


def _looks_like_netscape(text: str) -> bool:
    """Netscape cookie files: comment header or 7 tab-separated fields per cookie line."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    if lines[0].startswith(("# Netscape HTTP Cookie File", "# HTTP Cookie File")):
        return True
    cookies = [line for line in lines if not line.startswith("#")]
    return bool(cookies) and all(len(line.split("\t")) == 7 for line in cookies)


def _status(path: Path) -> CookiesStatus:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return CookiesStatus(present=False)
    with path.open(encoding="utf-8", errors="replace") as fh:
        count = sum(1 for line in fh if line.strip() and not line.startswith("#"))
    return CookiesStatus(
        present=True, updated_at=datetime.fromtimestamp(stat.st_mtime, UTC), lines=count
    )


@router.get("/settings/cookies", operation_id="getCookiesStatus")
async def get_cookies(services: ServicesDep) -> CookiesStatus:
    return _status(cookies_path(services.settings))


@router.put("/settings/cookies", operation_id="putCookies", responses=ERROR_RESPONSES)
async def put_cookies(body: CookiesUpload, services: ServicesDep) -> CookiesStatus:
    if not _looks_like_netscape(body.content):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"code": "invalid_cookies", "message": "this is not a Netscape cookies.txt file"},
        )
    path = cookies_path(services.settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(body.content)
    tmp.chmod(0o600)
    tmp.replace(path)
    return _status(path)


@router.delete(
    "/settings/cookies", operation_id="deleteCookies", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_cookies(services: ServicesDep) -> Response:
    cookies_path(services.settings).unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
