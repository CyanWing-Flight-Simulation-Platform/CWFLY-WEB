"""登录二次验证 challenge：JWT 绑定 CID/IP，并在数据库中一次性消费。"""
from __future__ import annotations

import datetime as dt
import logging
import secrets
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.token import (
    TokenError,
    sign_login_challenge,
    verify_login_challenge,
)

log = logging.getLogger("cwfly.login_challenge")

_ready = False


class LoginChallengeUnavailable(Exception):
    """挑战存储不可用：调用方应返回 503，禁止无状态放行。"""


async def ensure_table() -> None:
    global _ready
    if _ready:
        return
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        exists = (
            await db.execute(
                text(
                    "SELECT COUNT(*) AS c FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = 'LoginChallenge'"
                )
            )
        ).first()._mapping["c"]
        if int(exists) > 0:
            _ready = True
            await db.close()
            return
        await db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS `LoginChallenge` ("
                "`jti` VARCHAR(64) NOT NULL,"
                "`cid` VARCHAR(191) NOT NULL,"
                "`ip` VARCHAR(64) NOT NULL,"
                "`deviceFp` VARCHAR(191) NOT NULL DEFAULT '',"
                "`expiresAt` DATETIME(3) NOT NULL,"
                "`usedAt` DATETIME(3) NULL,"
                "`createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),"
                "PRIMARY KEY (`jti`),"
                "INDEX `idx_login_challenge_exp` (`expiresAt`)"
                ") DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
        await db.commit()
    _ready = True


async def create_login_challenge(
    db: AsyncSession, cid: str, ip: str, device_fp: str = ""
) -> str:
    """生成 JWT challenge 并落库 jti；数据库不可用抛 LoginChallengeUnavailable。"""
    try:
        await ensure_table()
    except Exception as exc:  # noqa: BLE001
        log.error("[login_challenge] 建表失败: %s", exc)
        raise LoginChallengeUnavailable("登录验证服务暂不可用") from exc
    jti = secrets.token_hex(16)
    ttl = max(1, int(settings.LOGIN_CHALLENGE_TTL_SECONDS))
    expires = dt.datetime.utcnow() + dt.timedelta(seconds=ttl)
    try:
        await db.execute(
            text(
                "INSERT INTO `LoginChallenge` (`jti`, `cid`, `ip`, `deviceFp`, `expiresAt`) "
                "VALUES (:jti, :cid, :ip, :fp, :expiresAt)"
            ),
            {"jti": jti, "cid": str(cid), "ip": str(ip or ""), "fp": (device_fp or "")[:191], "expiresAt": expires},
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        log.error("[login_challenge] 创建失败: %s", exc)
        raise LoginChallengeUnavailable("登录验证服务暂不可用") from exc
    return sign_login_challenge(str(cid), str(ip or ""), jti, ttl)


async def consume_login_challenge(
    db: AsyncSession, token: str, cid: str, ip: str
) -> bool:
    """校验签名/CID/IP，并原子标记 usedAt；重复使用或数据库异常均失败。"""
    try:
        claims: dict[str, Any] = verify_login_challenge(token)
    except TokenError:
        return False

    if str(claims.get("cid") or "") != str(cid):
        return False
    if str(claims.get("ip") or "") != str(ip or ""):
        return False

    jti = str(claims.get("jti") or "")
    if not jti:
        return False
    try:
        result = await db.execute(
            text(
                "UPDATE `LoginChallenge` SET `usedAt` = UTC_TIMESTAMP(3) "
                "WHERE `jti` = :jti AND `cid` = :cid AND `ip` = :ip "
                "AND `usedAt` IS NULL AND `expiresAt` > UTC_TIMESTAMP(3)"
            ),
            {"jti": jti, "cid": str(cid), "ip": str(ip or "")},
        )
        await db.commit()
        return int(result.rowcount or 0) == 1
    except Exception as exc:  # noqa: BLE001
        log.error("[login_challenge] 消费失败: %s", exc)
        raise LoginChallengeUnavailable("登录验证服务暂不可用") from exc


__all__ = [
    "LoginChallengeUnavailable",
    "ensure_table",
    "create_login_challenge",
    "consume_login_challenge",
]
