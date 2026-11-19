"""当前请求上下文：供审计日志在任意深层函数中读取 IP/UA，无需逐层透传 Request。"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_current_request: ContextVar[Request | None] = ContextVar("audit_current_request", default=None)


class AuditContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any):
        token = _current_request.set(request)
        try:
            return await call_next(request)
        finally:
            _current_request.reset(token)


def current_request() -> Request | None:
    return _current_request.get()


__all__ = ["AuditContextMiddleware", "current_request"]
