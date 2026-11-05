"""Owner sign-in: POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me."""

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from anyget.api.deps import ApiError, ServicesDep
from anyget.core.auth import client_ip
from anyget.core.session import COOKIE, CSRF_HEADER, CSRF_VALUE

router = APIRouter(tags=["auth"])

# Sign-in attempts per minute: per client and for everyone together.
LOGIN_PER_CLIENT = 5
LOGIN_TOTAL = 30


class LoginBody(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class Me(BaseModel):
    signed_in: bool
    # How the request was let in: session, token, access, local (or "" when not).
    method: str
    # True when this AnyGet asks for a sign-in (an owner is set or it is on the internet).
    login_required: bool
    # True when an owner email and password hash are set (sign-in can work).
    owner_configured: bool
    email: str | None = None


def _secure(request: Request, hosted: bool) -> bool:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return hosted or proto.split(",")[0].strip() == "https"


def _me(request: Request, services: ServicesDep) -> Me:
    s = services.settings
    user = getattr(request.state, "user", None)
    method = getattr(request.state, "auth", "") or ""
    return Me(
        signed_in=user is not None,
        method=method if user is not None else "",
        login_required=s.login_required,
        owner_configured=s.owner_configured,
        email=s.owner_email.strip() if user is not None and s.owner_configured else None,
    )


@router.get("/auth/me", operation_id="getMe")
async def me(request: Request, services: ServicesDep) -> Me:
    return _me(request, services)


@router.post(
    "/auth/login",
    operation_id="login",
    responses={code: {"model": ApiError} for code in (401, 403, 429, 503)},
)
async def login(body: LoginBody, request: Request, response: Response, services: ServicesDep) -> Me:
    s = services.settings
    if not s.owner_configured:
        raise HTTPException(
            503,
            {
                "code": "owner_required",
                "message": "no owner is set: add ANYGET_OWNER_EMAIL and "
                "ANYGET_OWNER_PASSWORD_HASH (anyget hash-password), then restart",
            },
        )
    if request.headers.get(CSRF_HEADER, "").lower() != CSRF_VALUE:
        raise HTTPException(
            403, {"code": "csrf", "message": "this request must come from the AnyGet website"}
        )
    headers = {k.lower().encode(): v.encode() for k, v in request.headers.items()}
    scope = request.scope
    client = client_ip(headers, scope, s)
    limiter = services.login_limiter
    wait = limiter.hit(client, "login", LOGIN_PER_CLIENT) or limiter.hit("*", "login", LOGIN_TOTAL)
    if wait is not None:
        raise HTTPException(
            429, {"code": "rate_limited", "message": "too many sign-in attempts; wait a minute"}
        )
    user = services.sessions.check_password(body.email, body.password)
    if user is None:
        raise HTTPException(401, {"code": "auth_invalid", "message": "wrong email or password"})
    response.set_cookie(
        COOKIE,
        services.sessions.issue(user),
        max_age=services.sessions.max_age,
        httponly=True,
        secure=_secure(request, s.hosted),
        samesite="lax",
        path="/",
    )
    request.state.user = user
    request.state.auth = "session"
    return _me(request, services)


@router.post("/auth/logout", operation_id="logout", status_code=204)
async def logout(request: Request, services: ServicesDep) -> Response:
    response = Response(status_code=204)
    response.delete_cookie(
        COOKIE,
        path="/",
        httponly=True,
        secure=_secure(request, services.settings.hosted),
        samesite="lax",
    )
    return response
