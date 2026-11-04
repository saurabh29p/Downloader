"""Shared API helpers: the services dependency and the error model."""

from typing import Annotated

from fastapi import Depends, Request
from pydantic import BaseModel

from anyget.core.services import Services


class ApiError(BaseModel):
    code: str
    message: str


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


ServicesDep = Annotated[Services, Depends(get_services)]

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    400: {"model": ApiError, "description": "Blocked or invalid link"},
    404: {"model": ApiError, "description": "Not found"},
    409: {"model": ApiError, "description": "Action does not fit the job state"},
    422: {"model": ApiError, "description": "Link not supported"},
    502: {"model": ApiError, "description": "The remote server failed"},
}
