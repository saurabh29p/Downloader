"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from anyget import __version__
from anyget.api import archive, books, jobs, probe, system
from anyget.api import settings as settings_api
from anyget.core.filenames import UnsafePathError
from anyget.core.net import BlockedURLError
from anyget.core.queue import InvalidStateError, JobNotFoundError
from anyget.core.services import Services
from anyget.core.settings import Settings, get_settings
from anyget.handlers.base import HandlerError

HANDLER_ERROR_STATUS = {
    "unsupported": 422,
    "not_found": 404,
    "restricted": 403,
    "borrow_only": 403,
}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        services = Services.build(settings or get_settings())
        app.state.services = services
        await services.start()
        try:
            yield
        finally:
            await services.stop()

    app = FastAPI(
        title="AnyGet API",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )

    @app.exception_handler(BlockedURLError)
    async def blocked(_: Request, exc: BlockedURLError) -> JSONResponse:
        return _error(400, "blocked_url", str(exc))

    @app.exception_handler(UnsafePathError)
    async def unsafe(_: Request, exc: UnsafePathError) -> JSONResponse:
        return _error(400, "unsafe_path", str(exc))

    @app.exception_handler(HandlerError)
    async def handler_error(_: Request, exc: HandlerError) -> JSONResponse:
        return _error(HANDLER_ERROR_STATUS.get(exc.code, 502), exc.code, exc.message)

    @app.exception_handler(InvalidStateError)
    async def invalid_state(_: Request, exc: InvalidStateError) -> JSONResponse:
        return _error(409, "invalid_state", str(exc))

    @app.exception_handler(JobNotFoundError)
    async def missing(_: Request, exc: JobNotFoundError) -> JSONResponse:
        return _error(404, "not_found", "no such job")

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return _error(exc.status_code, "error", str(exc.detail))

    for module in (system, probe, jobs, settings_api, archive, books):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
