"""登录失败锁定（对齐 Node src/routes/auth.js：LoginAttempt 表共享计数）。

安全（2026-11-07 审计 P1-14 / P2-3）：
- 锁定键从「账号」改为 **(cid, ip) 组合**：攻击者无法通过故意输错密码把别人的账号锁死
  （定向 DoS），因为锁定只影响他自己的 IP→该账号 组合。
- **高等级账号（rating >= 11，管理员/超管）只告警不锁定**：即使攻击者换 IP，
  也不能把管理员账号锁在门外；异常次数写入日志供人工研判。
- 成功登录仍清空该账号全部失败记录（含其它 IP），避免历史计数影响正常用户。
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import users

log = logging.getLogger("cwfly.login_lock")

LOGIN_LOCK_WINDOW = dt.timedelta(minutes=15)
LOGIN_LOCK_MAX_FAILS = 5
LOCK_MESSAGE = "登录失败次数过多，账号已临时锁定 15 分钟"
# rating >= 该值视为「高等级账号」→ 只告警不锁定
LOCK_EXEMPT_RATING = 11


async def check_login_lock(
    db: AsyncSession,
    cid: str | None,
    ip: str | None = None,
    rating: int = 0,
) -> str | None:
    """返回锁定时应给前端的文案；未锁定返回 None。

    - 计数键：`(cid, ip)`（ip 为空时退回按 cid 计数，兼容内部调用）
    - `rating >= LOCK_EXEMPT_RATING` 的账号永不锁定，仅在超阈值时告警
    """
    if not cid:
        return None
    cutoff = dt.datetime.utcnow() - LOGIN_LOCK_WINDOW
    try:
        await users.delete_login_attempts_before(db, cid, cutoff, ip)
        count = await users.count_login_attempts_since(db, cid, cutoff, ip)
    except Exception:  # noqa: BLE001 - 计数不可用时 fail-open（不因 DB 故障锁死登录）
        return None

    if count < LOGIN_LOCK_MAX_FAILS:
        return None

    if int(rating or 0) >= LOCK_EXEMPT_RATING:
        log.warning(
            "[login_lock] 高等级账号失败次数超阈值（不锁定，仅告警）: cid=%s ip=%s fails=%s",
            cid,
            ip or "-",
            count,
        )
        return None

    return LOCK_MESSAGE


async def record_login_failure(
    db: AsyncSession, cid: str | None, ip: str
) -> None:
    if not cid:
        return
    try:
        await users.insert_login_attempt(db, cid, ip)
    except Exception:
        pass


async def clear_login_failures(db: AsyncSession, cid: str | None) -> None:
    if not cid:
        return
    try:
        await users.delete_login_attempts(db, cid)
    except Exception:
        pass


__all__ = [
    "LOGIN_LOCK_MAX_FAILS",
    "LOCK_EXEMPT_RATING",
    "LOCK_MESSAGE",
    "check_login_lock",
    "record_login_failure",
    "clear_login_failures",
]
