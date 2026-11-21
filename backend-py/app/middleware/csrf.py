"""Cookie 会话的 CSRF 双提交校验。

- Bearer 客户端（Authorization 头）不依赖 Cookie，直接放行；
- 未携带 `cw_access` Cookie 的请求（登录、公开接口）放行；
- 对 Cookie 认证的写请求要求 `X-CSRF-Token` 与 `cw_csrf` Cookie 完全一致。
"""
from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.utils.session_cookie import ACCESS_COOKIE, CSRF_COOKIE

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_EXEMPT_PREFIXES = (
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/login-verify",
    "/api/auth/passkey/login/options",
    "/api/auth/passkey/login/verify",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
    "/api/captcha",
    "/api/verify/",
    "/api/security/network-info",
    "/api/security/pixel",
    "/api/security/device-init",
    "/api/security/pow-challenge",
)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method in SAFE_METHODS:
            return await call_next(request)
        path = request.url.path
        if not path.startswith("/api") or any(path.startswith(p) for p in CSRF_EXEMPT_PREFIXES):
            return await call_next(request)
        # Bearer 客户端不依赖 Cookie，不会受 CSRF 影响。
        if (request.headers.get("authorization") or "").startswith("Bearer "):
            return await call_next(request)
        if not request.cookies.get(ACCESS_COOKIE):
            return await call_next(request)

        header = (request.headers.get("x-csrf-token") or "").strip()
        cookie = (request.cookies.get(CSRF_COOKIE) or "").strip()
        if not header or not cookie or not hmac.compare_digest(header, cookie):
            return JSONResponse(
                {"success": False, "message": "CSRF 校验失败，请刷新页面后重试"},
                status_code=403,
            )
        return await call_next(request)


__all__ = ["CSRFMiddleware"]
