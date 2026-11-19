"""自研轻量 WAF：在 FastAPI 层拦截明显的扫描/注入特征。

只检查 URL 路径、查询串和请求方法，不读取请求体，避免影响上传/JSON 业务；
复杂规则由 Nginx limit_req/limit_conn 与 PoW/登录锁定共同承担。
"""
from __future__ import annotations

import logging
import re
from urllib.parse import unquote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

log = logging.getLogger("cwfly.waf")

ALLOWED_METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}

_PATH_RULES = [
    re.compile(r"(^|/)\.(git|env|svn|hg)(/|$)", re.I),
    re.compile(r"(^|/)(phpmyadmin|pma|adminer|actuator|swagger-ui|wp-admin|wp-login)(/|$)", re.I),
    re.compile(r"(\.\./|\.\.\\|%2e%2e)", re.I),
    re.compile(r"\x00|%00", re.I),
]

_QUERY_RULES = [
    re.compile(r"\bunion\s+(all\s+)?select\b", re.I),
    re.compile(r"\bselect\b[\s\S]{0,120}\bfrom\b", re.I),
    re.compile(r"\b(or|and)\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+", re.I),
    re.compile(r"\b(sleep|benchmark|pg_sleep)\s*\(", re.I),
    re.compile(r"\b(information_schema|load_file|into\s+outfile)\b", re.I),
    re.compile(r"<\s*script|javascript\s*:|on(error|load|click)\s*=", re.I),
]

_BLOCKED_UA = ("sqlmap", "nikto", "nessus", "acunetix", "nuclei", "masscan", "zgrab", "nmap")


def _is_bad(value: str) -> bool:
    text = unquote(value or "")
    if not text:
        return False
    return any(rule.search(text) for rule in _PATH_RULES + _QUERY_RULES)


class WAFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method not in ALLOWED_METHODS:
            return JSONResponse({"success": False, "message": "请求方法不被允许"}, status_code=405)
        ua = (request.headers.get("user-agent") or "").lower()
        if any(bot in ua for bot in _BLOCKED_UA):
            return JSONResponse({"success": False, "message": "请求被拒绝"}, status_code=403)
        raw_target = request.url.path + "?" + (request.url.query or "")
        if _is_bad(raw_target):
            client = request.client.host if request.client else "-"
            log.warning("[WAF] blocked path=%s ip=%s", request.url.path[:200], client)
            return JSONResponse({"success": False, "message": "请求包含非法字符"}, status_code=403)
        return await call_next(request)


__all__ = ["WAFMiddleware"]
