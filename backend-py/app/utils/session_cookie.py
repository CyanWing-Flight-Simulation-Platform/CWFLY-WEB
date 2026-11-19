"""HttpOnly 会话 Cookie + 双提交 CSRF Cookie。

浏览器端不再把 JWT 放进 localStorage：
- `cw_access`：HttpOnly / Secure / SameSite=Lax，保存 access token；
- `cw_csrf`：非 HttpOnly，前端读取后放进 `X-CSRF-Token`，用于双提交校验。
"""
from __future__ import annotations

import secrets

from fastapi import Request, Response

from app.config import settings

ACCESS_COOKIE = "cw_access"
CSRF_COOKIE = "cw_csrf"
COOKIE_PATH = "/"


def cookie_secure(request: Request) -> bool:
    # 生产强制 Secure；本地开发仍允许 http://localhost 调试。
    if settings.is_prod:
        return True
    forwarded = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    return request.url.scheme == "https" or forwarded == "https"


def access_token_from_request(request: Request) -> str:
    return (request.cookies.get(ACCESS_COOKIE) or "").strip()


def set_auth_cookies(response: Response, request: Request, token: str) -> None:
    secure = cookie_secure(request)
    max_age = max(60, int(settings.jwt_expires_seconds))
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=COOKIE_PATH,
    )
    # 双提交 CSRF token：轮换登录时复用当前值，缺失时新建。
    csrf = (request.cookies.get(CSRF_COOKIE) or "").strip() or secrets.token_urlsafe(32)
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path=COOKIE_PATH,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path=COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE, path=COOKIE_PATH)


__all__ = [
    "ACCESS_COOKIE",
    "CSRF_COOKIE",
    "COOKIE_PATH",
    "cookie_secure",
    "access_token_from_request",
    "set_auth_cookies",
    "clear_auth_cookies",
]
