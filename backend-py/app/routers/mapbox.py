"""Mapbox 反向代理 + 月度调用配额。

目的：
1. Mapbox access token 只保存在服务器环境变量（MAPBOX_TOKEN），绝不进前端包/不暴露给浏览器；
2. 所有 Mapbox 请求都经本代理，按「真正回源次数」计数，超过 MAPBOX_MONTHLY_LIMIT 直接 429；
3. 回源响应写入 Redis 缓存，缓存命中不计数（否则 10000/月 根本不够用）；
4. 样式 / TileJSON 里的 mapbox:// 与 api.mapbox.com 链接统一改写为本站代理地址。

环境变量：
- MAPBOX_TOKEN            必填，服务端 token
- MAPBOX_MONTHLY_LIMIT    默认 10000
- MAPBOX_ENABLED          默认 1；设 0 关闭代理（前端自动回退高德）
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.config import settings

log = logging.getLogger("cwfly.mapbox")

router = APIRouter(prefix="/mapbox", tags=["mapbox"])

MAPBOX_API = "https://api.mapbox.com"
ALLOWED_PREFIXES = ("styles/", "sprites/", "fonts/", "v4/")
USAGE_PREFIX = "cwfly:mapbox:usage:"
CACHE_PREFIX = "cwfly:mapbox:cache:"

_client: httpx.AsyncClient | None = None
_redis = None
_redis_checked = False


def _token() -> str:
    return (getattr(settings, "MAPBOX_TOKEN", "") or "").strip()


def _enabled() -> bool:
    if not _token():
        return False
    return str(getattr(settings, "MAPBOX_ENABLED", "1")).strip() not in ("0", "false", "False", "off")


def _limit() -> int:
    try:
        return max(1, int(getattr(settings, "MAPBOX_MONTHLY_LIMIT", 10000)))
    except (TypeError, ValueError):
        return 10000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _month_key(now: datetime | None = None) -> str:
    return (now or _now()).strftime("%Y-%m")


def _day_key(now: datetime | None = None) -> str:
    return (now or _now()).strftime("%Y%m%d")


def _redis_client():
    global _redis, _redis_checked
    if _redis_checked:
        return _redis
    _redis_checked = True
    url = (
        os.getenv("REDIS_URL")
        or os.getenv("TOKEN_STATE_REDIS_URL")
        or os.getenv("SOCKETIO_REDIS_URL")
        or ""
    ).strip()
    if not url:
        log.warning("[mapbox] 未配置 Redis，无法执行配额控制")
        return None
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(url, socket_timeout=1.0, socket_connect_timeout=1.0)
        client.ping()
        _redis = client
        log.info("[mapbox] 配额/缓存使用 Redis: %s", url.rsplit("@", 1)[-1])
    except Exception as exc:  # noqa: BLE001
        log.warning("[mapbox] Redis 不可用: %s", exc)
        _redis = None
    return _redis


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=64, max_keepalive_connections=32),
        )
    return _client


def _base_url(request: Request) -> str:
    """本站代理前缀（用于改写样式里的绝对地址）。"""
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",")[0].strip()
    host = request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}/api/mapbox"


def _cache_ttl(path: str) -> int:
    if path.startswith("styles/") and "/tiles/" not in path:
        return 86400 * 2
    if path.startswith("sprites/") or path.startswith("fonts/"):
        return 86400 * 14
    return 86400 * 3  # 瓦片 / TileJSON


def _is_json_path(path: str) -> bool:
    if path.startswith("styles/") and "/tiles/" not in path:
        return True
    if path.startswith("v4/"):
        return True
    return False


def _strip_token(url: str) -> str:
    """去掉 URL 查询串里的 access_token（避免把服务端 token 下发到前端）。"""
    parts = urlsplit(url)
    if not parts.query:
        return url
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() != "access_token"]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


_TILES_HOST_RE = re.compile(r"^https?://(?:[a-c]\.)?tiles\.mapbox\.com/", re.IGNORECASE)


def _rewrite(value, base: str):
    if isinstance(value, str):
        s = value
        if s.startswith("mapbox://"):
            rest = s[len("mapbox://"):]
            seg = rest.split("?", 1)[0]
            if seg.startswith("sprites/"):
                parts = seg.split("/")
                # mapbox://sprites/{owner}/{style}/{version} -> /styles/v1/{owner}/{style}/sprite
                if len(parts) >= 3:
                    return f"{base}/styles/v1/{parts[1]}/{parts[2]}/sprite"
                return f"{base}/{seg}"
            if seg.startswith("fonts/"):
                return f"{base}/fonts/v1/{seg[len('fonts/'):]}"
            if seg.startswith("styles/"):
                return f"{base}/styles/v1/{seg[len('styles/'):]}"
            return f"{base}/v4/{seg}.json"
        if s.startswith(MAPBOX_API):
            s = s.replace(MAPBOX_API, base, 1)
        # TileJSON 里的瓦片模板会用 a/b/c.tiles.mapbox.com 的 http 地址，同样改写到本站
        if _TILES_HOST_RE.match(s):
            s = _TILES_HOST_RE.sub(base + "/", s, count=1)
        if "access_token=" in s:
            s = _strip_token(s)
        return s
    if isinstance(value, list):
        return [_rewrite(v, base) for v in value]
    if isinstance(value, dict):
        return {k: _rewrite(v, base) for k, v in value.items()}
    return value


def _usage(redis) -> dict:
    month = _month_key()
    used = 0
    try:
        used = int(redis.get(USAGE_PREFIX + month) or 0)
    except Exception:  # noqa: BLE001
        pass
    limit = _limit()
    daily = {}
    try:
        for i in range(7):
            d = _now()
            from datetime import timedelta

            key = d - timedelta(days=i)
            v = redis.get(f"{USAGE_PREFIX}d:{key.strftime('%Y%m%d')}")
            daily[key.strftime("%Y-%m-%d")] = int(v or 0)
    except Exception:  # noqa: BLE001
        pass
    return {
        "month": month,
        "used": used,
        "limit": limit,
        "remaining": max(limit - used, 0),
        "daily": daily,
        "enabled": _enabled(),
    }


@router.get("/usage")
async def mapbox_usage() -> JSONResponse:
    redis = _redis_client()
    if redis is None:
        return JSONResponse(
            {"success": False, "message": "配额服务不可用", "enabled": _enabled()},
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )
    data = _usage(redis)
    return JSONResponse(
        {"success": True, "data": data},
        headers={"Cache-Control": "no-store"},
    )


@router.api_route("/{path:path}", methods=["GET"])
async def mapbox_proxy(path: str, request: Request) -> Response:
    if not _enabled():
        return JSONResponse(
            {"success": False, "code": "MAPBOX_DISABLED", "message": "3D 地图服务未启用"},
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )

    path = unquote(path or "").lstrip("/")
    # 只允许 Mapbox 固定几类路径，避免被当成任意 URL 读取器
    if not path.startswith(ALLOWED_PREFIXES) or ".." in path:
        return JSONResponse({"success": False, "message": "不支持的路径"}, status_code=400)

    redis = _redis_client()
    if redis is None:
        # 没有配额存储就不放行，避免无上限刷 Mapbox
        return JSONResponse(
            {"success": False, "code": "MAPBOX_QUOTA_UNAVAILABLE", "message": "配额服务不可用"},
            status_code=503,
        )

    query = [(k, v) for k, v in request.query_params.multi_items() if k.lower() != "access_token"]
    cache_src = path + "?" + urlencode(sorted(query))
    digest = hashlib.sha256(cache_src.encode("utf-8")).hexdigest()
    cache_key = (CACHE_PREFIX + digest).encode()

    # 1) 缓存命中：不消耗额度
    try:
        cached = redis.get(cache_key)
    except Exception:  # noqa: BLE001
        cached = None
    if cached:
        try:
            meta = json.loads(cached)
            body = bytes.fromhex(meta["hex"])
            return Response(
                content=body,
                media_type=meta.get("ct") or "application/octet-stream",
                headers={
                    "X-Mapbox-Cache": "hit",
                    "Cache-Control": "public, max-age=600",
                },
            )
        except Exception:  # noqa: BLE001
            pass

    # 2) 配额：先扣后判，超限回滚并 429
    month = _month_key()
    usage_key = USAGE_PREFIX + month
    try:
        used = int(redis.incr(usage_key))
        redis.expire(usage_key, 60 * 60 * 24 * 45)
        redis.incr(USAGE_PREFIX + "d:" + _day_key())
        redis.expire(USAGE_PREFIX + "d:" + _day_key(), 60 * 60 * 24 * 45)
    except Exception as exc:  # noqa: BLE001
        log.warning("[mapbox] 计数失败: %s", exc)
        return JSONResponse(
            {"success": False, "code": "MAPBOX_QUOTA_UNAVAILABLE", "message": "配额服务不可用"},
            status_code=503,
        )
    limit = _limit()
    if used > limit:
        try:
            redis.decr(usage_key)
            redis.decr(USAGE_PREFIX + "d:" + _day_key())
        except Exception:  # noqa: BLE001
            pass
        return JSONResponse(
            {
                "success": False,
                "code": "MAPBOX_QUOTA_EXHAUSTED",
                "message": f"3D 地图本月调用额度已用完（{limit} 次），已自动切换 2D 高德地图",
                "used": limit,
                "limit": limit,
            },
            status_code=429,
            headers={"Cache-Control": "no-store", "X-Mapbox-Usage": f"{limit}/{limit}"},
        )

    # 3) 回源
    upstream = f"{MAPBOX_API}/{path}"
    params = dict(query)
    params["access_token"] = _token()
    try:
        resp = await _http().get(upstream, params=params)
    except Exception as exc:  # noqa: BLE001
        log.warning("[mapbox] 回源失败 %s: %s", path, exc)
        return JSONResponse(
            {"success": False, "code": "MAPBOX_UPSTREAM_ERROR", "message": "地图服务暂时不可用"},
            status_code=502,
        )

    body = resp.content
    ctype = (resp.headers.get("content-type") or "application/octet-stream").split(";")[0].strip()

    if resp.status_code == 200 and _is_json_path(path):
        try:
            obj = json.loads(body)
            obj = _rewrite(obj, _base_url(request))
            body = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ctype = "application/json"
        except Exception as exc:  # noqa: BLE001
            log.warning("[mapbox] 样式改写失败 %s: %s", path, exc)

    headers = {
        "X-Mapbox-Cache": "miss",
        "X-Mapbox-Usage": f"{used}/{limit}",
        "Cache-Control": "public, max-age=600",
    }

    if resp.status_code == 200 and len(body) <= 8 * 1024 * 1024:
        try:
            payload = json.dumps({"ct": ctype, "hex": body.hex()})
            redis.set(cache_key, payload, ex=_cache_ttl(path))
        except Exception:  # noqa: BLE001
            pass

    if resp.status_code >= 400:
        # 上游 4xx/5xx 透传状态，前端据此决定回退
        headers["Cache-Control"] = "no-store"
    return Response(content=body, status_code=resp.status_code, media_type=ctype, headers=headers)
