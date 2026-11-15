"""Connections: GET/PUT/DELETE /api/connections[/{site}], import and test.

Values go in and never come out: every answer is a ConnectionsView (status, dates).
"""

from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Path, Response, status
from pydantic import BaseModel, Field, field_validator

from anyget.api.deps import ERROR_RESPONSES, ServicesDep, UserDep
from anyget.connections.sites import BY_ID, Site
from anyget.connections.store import ConnectionsView, ConnectionValueError
from anyget.core.net import BlockedURLError

router = APIRouter(tags=["connections"])

MAX_COOKIES = 1024 * 1024
SiteId = Annotated[str, Path(pattern=r"^[a-z_]{1,32}$")]


def _proxy_ok(value: str | None) -> str | None:
    if value and not value.startswith(("http://", "https://", "socks5://", "socks5h://")):
        raise ValueError("the proxy must start with http://, https:// or socks5://")
    return value or None


class ConnectionIn(BaseModel):
    """Cookie sites take `cookies` (a cookies.txt); key sites take `fields`."""

    cookies: str | None = Field(default=None, max_length=MAX_COOKIES, repr=False)
    fields: dict[str, Annotated[str, Field(max_length=500)]] | None = Field(
        default=None, repr=False
    )
    proxy: str | None = Field(default=None, max_length=300, repr=False)

    _check_proxy = field_validator("proxy")(classmethod(lambda cls, v: _proxy_ok(v)))


class CookiesImport(BaseModel):
    cookies: str = Field(min_length=1, max_length=MAX_COOKIES, repr=False)


class ImportResult(BaseModel):
    imported: list[str]
    view: ConnectionsView


class TestResult(BaseModel):
    ok: bool
    # A code the web translates: ok, rejected, unreachable, expired, untested.
    result: str


def _site(site_id: str) -> Site:
    site = BY_ID.get(site_id)
    if site is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": "no such site"}
        )
    return site


def _bad(exc: Exception) -> HTTPException:
    code = exc.code if isinstance(exc, ConnectionValueError) else "invalid_connection"
    return HTTPException(status.HTTP_400_BAD_REQUEST, {"code": code, "message": str(exc)})


@router.get("/connections", operation_id="listConnections")
async def list_connections(services: ServicesDep, user: UserDep) -> ConnectionsView:
    return services.connections.view(user)


@router.put("/connections/{site_id}", operation_id="putConnection", responses=ERROR_RESPONSES)
async def put_connection(
    site_id: SiteId, body: ConnectionIn, services: ServicesDep, user: UserDep
) -> ConnectionsView:
    site = _site(site_id)
    store = services.connections
    try:
        if site.kind == "cookies" and body.cookies:
            store.save_cookies(user, site, body.cookies, body.proxy)
        elif site.kind == "key" and body.fields:
            store.save_fields(user, site, body.fields, body.proxy)
        elif body.cookies is None and body.fields is None and "proxy" in body.model_fields_set:
            if not store.set_proxy(user, site, body.proxy):
                raise ConnectionValueError(
                    "connect the site first, then add a proxy", "not_connected"
                )
        else:
            wanted = "a cookies.txt file" if site.kind == "cookies" else "the key"
            raise ConnectionValueError(f"{site.label} needs {wanted}", "missing_fields")
    except ConnectionValueError as exc:
        raise _bad(exc) from exc
    return store.view(user)


@router.post("/connections/import", operation_id="importCookies", responses=ERROR_RESPONSES)
async def import_cookies(body: CookiesImport, services: ServicesDep, user: UserDep) -> ImportResult:
    """One cookies.txt for several sites: each known site gets its own cookies."""
    try:
        imported = services.connections.import_cookies(user, body.cookies)
    except ConnectionValueError as exc:
        raise _bad(exc) from exc
    if not imported:
        raise _bad(
            ConnectionValueError(
                "this file has no cookies for the sites listed here", "cookies_wrong_site"
            )
        )
    return ImportResult(imported=imported, view=services.connections.view(user))


@router.delete(
    "/connections/{site_id}",
    operation_id="deleteConnection",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERROR_RESPONSES,
)
async def delete_connection(site_id: SiteId, services: ServicesDep, user: UserDep) -> Response:
    _site(site_id)
    services.connections.delete(user, site_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Cheap requests that prove a key works (nothing is downloaded).
KEY_TESTS: dict[str, tuple[str, str]] = {
    "github": ("https://api.github.com/user", "bearer"),
    "huggingface": ("https://huggingface.co/api/whoami-v2", "bearer"),
    "openrouter": ("https://openrouter.ai/api/v1/key", "bearer"),
    "tmdb": ("https://api.themoviedb.org/3/configuration?api_key={key}", "query"),
}


@router.post(
    "/connections/{site_id}/test", operation_id="testConnection", responses=ERROR_RESPONSES
)
async def test_connection(site_id: SiteId, services: ServicesDep, user: UserDep) -> TestResult:
    site = _site(site_id)
    store = services.connections
    view = next(v for v in store.view(user).sites if v.id == site_id)
    if view.status == "not_connected":
        raise _bad(ConnectionValueError(f"{site.label} is not connected", "not_connected"))
    if site.kind == "cookies":
        # No request is made: the cookies' own expiry date tells whether they still work.
        ok = view.status == "connected"
        result = TestResult(ok=ok, result="ok" if ok else "expired")
    elif site_id in KEY_TESTS and view.status == "connected":
        key = (store.payload(user, site_id).get("fields") or {}).get("token", "")
        url, style = KEY_TESTS[site_id]
        headers = {"Authorization": f"Bearer {key}"} if style == "bearer" else {}
        try:
            response = await services.net.request("GET", url.replace("{key}", key), headers=headers)
        except (httpx.HTTPError, BlockedURLError):
            result = TestResult(ok=False, result="unreachable")
        else:
            ok = response.status_code < 400
            result = TestResult(ok=ok, result="ok" if ok else "rejected")
    else:
        result = TestResult(ok=True, result="untested")
    if result.result != "untested":
        store.record_test(user, site_id, result.ok)
    return result
