"""当前请求上下文 + API 操作审计。

- 业务代码通过 `current_request()` 读取 IP/UA；
- 显式调用过 `audit_log.write()` 的请求会打上 semantic 标记，避免兜底重复；
- 兜底审计只记录写操作（POST/PUT/PATCH/DELETE），不再记录 GET/HEAD 轮询与浏览；
- 地图 FSD 轮询等公开只读接口永久排除，避免审计表被高频轮询灌满。
"""
from __future__ import annotations

import asyncio
import logging
import time
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings

log = logging.getLogger("cwfly.audit.middleware")

_current_request: ContextVar[Request | None] = ContextVar("audit_current_request", default=None)
_semantic_written: ContextVar[bool] = ContextVar("audit_semantic_written", default=False)

# 高频无业务语义请求：轮询、验证码、安全像素、会话刷新，不写兜底审计
_IGNORED_NOISE_PREFIXES = (
    "/api/flightplans/fsd/",
    "/api/captcha/",
    "/api/security/pixel.gif",
    "/api/auth/refresh",
    "/api/auth/login",
    "/api/auth/passkey/",
)
_READ_METHODS = {"GET", "HEAD", "OPTIONS"}


class AuditContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any):
        request_token = _current_request.set(request)
        semantic_token = _semantic_written.set(False)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            try:
                method = request.method.upper()
                should_log = (
                    settings.AUDIT_LOG_ALL_REQUESTS
                    and request.url.path.startswith("/api/")
                    and method not in _READ_METHODS
                    and not request.url.path.startswith(_IGNORED_NOISE_PREFIXES)
                    and not _semantic_written.get()
                )
                if should_log:
                    asyncio.get_running_loop().create_task(
                        _write_generic_audit(
                            request.method.upper(),
                            request.url.path,
                            status,
                            duration_ms,
                            request,
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                log.debug("[audit] 提交兜底审计失败: %s", exc)
            _semantic_written.reset(semantic_token)
            _current_request.reset(request_token)


async def _write_generic_audit(
    method: str, path: str, status: int, duration_ms: int, request: Request
) -> None:
    try:
        from app.db.session import SessionLocal
        from app.services.audit_log import write_generic_request

        async with SessionLocal() as db:
            await write_generic_request(
                db,
                method=method,
                path=path,
                status=status,
                duration_ms=duration_ms,
                request=request,
            )
    except Exception as exc:  # noqa: BLE001
        log.debug("[audit] 写入兜底审计失败: %s", exc)


def current_request() -> Request | None:
    return _current_request.get()


def mark_semantic_audit() -> None:
    _semantic_written.set(True)


def semantic_audit_written() -> bool:
    return bool(_semantic_written.get())


__all__ = [
    "AuditContextMiddleware",
    "current_request",
    "mark_semantic_audit",
    "semantic_audit_written",
]
