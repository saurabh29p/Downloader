"""FastAPI application factory."""

from fastapi import FastAPI

from anyget import __version__
from anyget.api import system


def create_app() -> FastAPI:
    app = FastAPI(
        title="AnyGet API",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.include_router(system.router, prefix="/api")
    return app


app = create_app()
