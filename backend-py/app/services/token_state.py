"""令牌吊销状态：jti 黑名单 + 用户级 token_epoch（安全审计 P1-1 / P1-2）。

设计目标
--------
1. **登出即失效**：`POST /api/auth/logout` 把当前 token 的 `jti` 写入黑名单，
   剩余有效期（TTL）到期自动清理；`app/deps.py` 每个请求校验黑名单。
2. **改密/封禁/降权/删号即失效**：这些动作调用 `bump_token_epoch(cid)`，
   用户级 epoch 前进；token 里携带签发时的 `tokep`，`tokep < 当前 epoch` 一律拒绝。
3. **可用性优先**：Redis 不可用时**不抛错、不拖垮登录**（fail-open），仅记 warning；
   同时保留**进程内内存实现**，保证单进程部署下吊销仍然真实生效。

存储
----
- Redis（多 worker/多实例一致，优先）：`cw:jwtbl:{jti}`（TTL=剩余有效期）、
  `cw:tokep:{cid}`（用户 epoch，TTL 30 天，每次 bump 续期）
- 内存回退（进程内）：`_MEM_JTI` / `_MEM_EPOCH`，带容量上限与过期清理

兼容性
------
- 旧 token 没有 `jti`/`tokep`：黑名单查不到（放行），epoch 视为 0；
  一旦该用户改密/被封禁（epoch 前进 > 0），旧 token 立即失效。
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional

log = logging.getLogger("cwfly.token_state")

JTI_KEY_PREFIX = "cw:jwtbl:"
EPOCH_KEY_PREFIX = "cw:tokep:"
EPOCH_TTL_SECONDS = 30 * 24 * 3600
MAX_MEMORY_JTI = 50000

_REDIS_JTI_PREFIX = JTI_KEY_PREFIX
_REDIS_EPOCH_PREFIX = EPOCH_KEY_PREFIX

_redis_client: Any = None
_redis_checked = False
_redis_warned = False
_lock = threading.Lock()

# 进程内回退（Redis 不可用 / 未配置时仍然生效）
_MEM_JTI: dict[str, float] = {}
_MEM_EPOCH: dict[str, int] = {}


# ---------------------------------------------------------------- Redis
def _redis() -> Any:
    """惰性初始化 Redis；不可用返回 None（回退内存，不抛错）。"""
    global _redis_client, _redis_checked, _redis_warned
    if _redis_checked:
        return _redis_client
    with _lock:
        if _redis_checked:
            return _redis_client
        _redis_checked = True
        url = (
            os.getenv("TOKEN_STATE_REDIS_URL")
            or os.getenv("SOCKETIO_REDIS_URL")
            or os.getenv("REDIS_URL")
            or ""
        ).strip()
        if not url:
            log.warning(
                "[token_state] 未配置 Redis：令牌吊销（登出黑名单/token_epoch）仅在本进程内生效"
            )
            _redis_warned = True
            _redis_client = None
            return None
        try:
            import redis  # type: ignore

            client = redis.Redis.from_url(url, socket_timeout=0.3, socket_connect_timeout=0.3)
            client.ping()
            _redis_client = client
            log.info("[token_state] 使用 Redis 存储吊销状态（多 worker 一致）")
        except Exception as exc:  # noqa: BLE001
            _redis_warned = True
            log.warning(
                "[token_state] Redis 不可用，吊销状态回退进程内（fail-open，不阻塞登录）: %s", exc
            )
            _redis_client = None
        return _redis_client


def _warn_fail_open(operation: str, exc: BaseException) -> None:
    # 只在真正发生错误时告警（限流日志量）
    log.warning("[token_state] %s 失败（fail-open，不阻塞请求）: %s", operation, exc)


# ---------------------------------------------------------------- 内存回退
def _prune_memory(now: float) -> None:
    if len(_MEM_JTI) < MAX_MEMORY_JTI:
        return
    expired = [key for key, exp in _MEM_JTI.items() if exp <= now]
    for key in expired:
        _MEM_JTI.pop(key, None)
    # 极端情况：仍然超限则丢弃最早过期的 10%
    if len(_MEM_JTI) >= MAX_MEMORY_JTI:
        for key in sorted(_MEM_JTI, key=lambda k: _MEM_JTI[k])[: MAX_MEMORY_JTI // 10]:
            _MEM_JTI.pop(key, None)


# ---------------------------------------------------------------- jti 黑名单
def add_blacklisted_jti(jti: str, ttl_seconds: int) -> bool:
    """把 jti 加入黑名单（TTL=剩余有效期）。返回是否成功持久化到 Redis。"""
    key_id = (jti or "").strip()
    if not key_id:
        return False
    ttl = int(ttl_seconds)
    if ttl <= 0:
        return False  # 已过期的 token 无需拉黑
    now = time.time()
    _MEM_JTI[key_id] = now + ttl
    _prune_memory(now)
    client = _redis()
    if client is None:
        return False
    try:
        client.setex(_REDIS_JTI_PREFIX + key_id, ttl, "1")
        return True
    except Exception as exc:  # noqa: BLE001
        _warn_fail_open("写入 jti 黑名单", exc)
        return False


def is_jti_blacklisted(jti: str | None) -> bool:
    key_id = (jti or "").strip()
    if not key_id:
        return False
    now = time.time()
    exp = _MEM_JTI.get(key_id)
    if exp is not None:
        if exp > now:
            return True
        _MEM_JTI.pop(key_id, None)
    client = _redis()
    if client is None:
        return False
    try:
        return bool(client.exists(_REDIS_JTI_PREFIX + key_id))
    except Exception as exc:  # noqa: BLE001
        _warn_fail_open("查询 jti 黑名单", exc)
        return False


# ---------------------------------------------------------------- token epoch
def bump_token_epoch(cid: str) -> int:
    """前移用户 epoch（改密/封禁/降权/删号），使旧 token 失效。"""
    user_id = str(cid or "").strip()
    if not user_id:
        return 0
    value = int(time.time() * 1000)
    previous = _MEM_EPOCH.get(user_id)
    if previous is not None and previous >= value:
        value = previous + 1
    _MEM_EPOCH[user_id] = value
    client = _redis()
    if client is not None:
        try:
            # 以「单调递增」方式写入：Redis 里的值更大时保留 Redis 的值 +1
            script = (
                "local v = redis.call('GET', KEYS[1]) "
                "local n = tonumber(ARGV[1]) "
                "if v then local c = tonumber(v) if c and c >= n then n = c + 1 end end "
                "redis.call('SET', KEYS[1], tostring(n), 'EX', ARGV[2]) "
                "return n"
            )
            raw = client.eval(script, 1, _REDIS_EPOCH_PREFIX + user_id, value, EPOCH_TTL_SECONDS)
            if raw is not None:
                value = int(raw)
                _MEM_EPOCH[user_id] = value
        except Exception as exc:  # noqa: BLE001
            _warn_fail_open("写入 token_epoch", exc)
    log.info("[token_state] token_epoch 前移: cid=%s epoch=%s", user_id, value)
    return value


def token_epoch(cid: str) -> Optional[int]:
    """读取用户当前 epoch；无记录返回 None（等价 epoch=0）。"""
    user_id = str(cid or "").strip()
    if not user_id:
        return None
    client = _redis()
    if client is not None:
        try:
            raw = client.get(_REDIS_EPOCH_PREFIX + user_id)
            if raw is not None:
                value = int(raw)
                _MEM_EPOCH[user_id] = max(_MEM_EPOCH.get(user_id, 0), value)
                return value
        except Exception as exc:  # noqa: BLE001
            _warn_fail_open("读取 token_epoch", exc)
    return _MEM_EPOCH.get(user_id)


def is_epoch_stale(cid: str, tokep: Any) -> bool:
    """token 携带的 epoch 是否已落后于当前值（落后 → 应拒绝）。"""
    current = token_epoch(cid)
    if current is None:
        return False  # 从未 bump → 不吊销（兼容旧 token）
    try:
        claimed = int(tokep or 0)
    except (TypeError, ValueError):
        claimed = 0
    return claimed < int(current)


# ---------------------------------------------------------------- 测试辅助
def reset_state_for_tests() -> None:
    """清空进程内吊销状态（仅供单元测试使用）。"""
    _MEM_JTI.clear()
    _MEM_EPOCH.clear()


__all__ = [
    "add_blacklisted_jti",
    "is_jti_blacklisted",
    "bump_token_epoch",
    "token_epoch",
    "is_epoch_stale",
    "reset_state_for_tests",
    "JTI_KEY_PREFIX",
    "EPOCH_KEY_PREFIX",
    "EPOCH_TTL_SECONDS",
]
