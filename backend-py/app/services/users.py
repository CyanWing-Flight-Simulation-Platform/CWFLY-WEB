"""用户相关数据访问：原生 SQL（列名与 Prisma 生成的 MySQL 表完全一致）。

P0 阶段刻意使用原生 SQL 而非 ORM 映射：
- Prisma 的列名是 camelCase（如 fsdPasswordHash / registerIp），ORM 全量映射留到 P2；
- 认证路径要求与 Node 版本行为逐字节一致，原生 SQL 最可控；
- 后续可为 51 张表补充 SQLAlchemy 模型，这些函数可逐步替换为 ORM 查询。
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# 与 Node findUserWithCredentials 完全相同的字段集合与顺序
_CRED_SQL = (
    "SELECT id, cid, username, `password`, rating, permissions, fsdLevel, email, qq, avatar, "
    "createdAt, fsdPasswordHash FROM `User` WHERE cid = :cid LIMIT 1"
)

_PUBLIC_COLS = "cid, username, rating, permissions, fsdLevel, createdAt"


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping) if row is not None else {}


async def find_user_with_credentials(db: AsyncSession, cid: str | None) -> dict[str, Any] | None:
    if not cid:
        return None
    row = (await db.execute(text(_CRED_SQL), {"cid": cid})).first()
    return _row_to_dict(row) if row else None


async def find_user_public(db: AsyncSession, cid: str | None) -> dict[str, Any] | None:
    if not cid:
        return None
    row = (
        await db.execute(
            text(f"SELECT {_PUBLIC_COLS} FROM `User` WHERE cid = :cid LIMIT 1"),
            {"cid": cid},
        )
    ).first()
    return _row_to_dict(row) if row else None


async def find_user_by_email(db: AsyncSession, email: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text(f"SELECT {_PUBLIC_COLS}, email FROM `User` WHERE email = :email LIMIT 1"),
            {"email": email},
        )
    ).first()
    return _row_to_dict(row) if row else None


async def find_first_by_column(db: AsyncSession, column: str, value: Any) -> dict[str, Any] | None:
    """按白名单列查首条（registerFp / registerIp / email 去重）。"""
    allowed = {"registerFp", "registerIp", "email", "cid"}
    if column not in allowed:
        raise ValueError(f"unsupported column: {column}")
    row = (
        await db.execute(
            text(f"SELECT id FROM `User` WHERE `{column}` = :value LIMIT 1"), {"value": value}
        )
    ).first()
    return _row_to_dict(row) if row else None


async def count_admins(db: AsyncSession) -> int:
    row = (
        await db.execute(text("SELECT COUNT(*) AS c FROM `User` WHERE rating >= 11"))
    ).first()
    return int(row._mapping["c"]) if row else 0


async def create_user(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    """插入用户；createdAt 由应用侧写入 UTC（对齐 Prisma @default(now()) 的行为）。"""
    payload = {
        "cid": data["cid"],
        "username": data["username"],
        "password": data["password"],
        "rating": data.get("rating", 0),
        "permissions": data.get("permissions", ""),
        "fsdLevel": data.get("fsdLevel", 0),
        "email": data.get("email", ""),
        "fsdPasswordHash": data.get("fsdPasswordHash", ""),
        "registerIp": data.get("registerIp", ""),
        "registerFp": data.get("registerFp", ""),
        "registerUserAgent": data.get("registerUserAgent", ""),
        "createdAt": data.get("createdAt") or dt.datetime.utcnow(),
    }
    await db.execute(
        text(
            "INSERT INTO `User` (cid, username, `password`, rating, permissions, fsdLevel, email, "
            "fsdPasswordHash, registerIp, registerFp, registerUserAgent, createdAt) VALUES "
            "(:cid, :username, :password, :rating, :permissions, :fsdLevel, :email, "
            ":fsdPasswordHash, :registerIp, :registerFp, :registerUserAgent, :createdAt)"
        ),
        payload,
    )
    await db.commit()
    return payload


async def update_user(db: AsyncSession, cid: str, values: dict[str, Any]) -> None:
    """按白名单列更新用户。"""
    allowed = {"password", "fsdPasswordHash", "rating", "permissions", "fsdLevel", "email"}
    sets, params = [], {"cid": cid}
    for key, value in values.items():
        if key not in allowed:
            raise ValueError(f"unsupported column: {key}")
        col = "`password`" if key == "password" else key
        sets.append(f"{col} = :{key}")
        params[key] = value
    if not sets:
        return
    await db.execute(text(f"UPDATE `User` SET {', '.join(sets)} WHERE cid = :cid"), params)
    await db.commit()


# ---------------- LoginAttempt（登录失败锁定） ----------------
async def delete_login_attempts(db: AsyncSession, cid: str) -> None:
    await db.execute(text("DELETE FROM `LoginAttempt` WHERE userId = :cid"), {"cid": cid})
    await db.commit()


async def delete_login_attempts_before(
    db: AsyncSession, cid: str, cutoff: dt.datetime, ip: str | None = None
) -> None:
    """清理过期失败记录；传入 ip 时只清理该 (cid, ip) 组合（P2-3 组合键）。"""
    if ip:
        await db.execute(
            text(
                "DELETE FROM `LoginAttempt` WHERE userId = :cid AND createdAt < :cutoff "
                "AND ip = :ip"
            ),
            {"cid": cid, "cutoff": cutoff, "ip": ip},
        )
    else:
        await db.execute(
            text("DELETE FROM `LoginAttempt` WHERE userId = :cid AND createdAt < :cutoff"),
            {"cid": cid, "cutoff": cutoff},
        )
    await db.commit()


async def count_login_attempts_since(
    db: AsyncSession, cid: str, cutoff: dt.datetime, ip: str | None = None
) -> int:
    """统计窗口内失败次数；传入 ip 时按 (cid, ip) 组合计数（P2-3：防定向锁号 DoS）。"""
    if ip:
        row = (
            await db.execute(
                text(
                    "SELECT COUNT(*) AS c FROM `LoginAttempt` "
                    "WHERE userId = :cid AND createdAt >= :cutoff AND ip = :ip"
                ),
                {"cid": cid, "cutoff": cutoff, "ip": ip},
            )
        ).first()
    else:
        row = (
            await db.execute(
                text(
                    "SELECT COUNT(*) AS c FROM `LoginAttempt` "
                    "WHERE userId = :cid AND createdAt >= :cutoff"
                ),
                {"cid": cid, "cutoff": cutoff},
            )
        ).first()
    return int(row._mapping["c"]) if row else 0


async def insert_login_attempt(db: AsyncSession, cid: str, ip: str) -> None:
    await db.execute(
        text("INSERT INTO `LoginAttempt` (userId, ip, createdAt) VALUES (:cid, :ip, :now)"),
        {"cid": cid, "ip": ip, "now": dt.datetime.utcnow()},
    )
    await db.commit()


# ---------------- LoginLog / Trusted IP ----------------
async def insert_login_log(db: AsyncSession, data: dict[str, Any]) -> None:
    await db.execute(
        text(
            "INSERT INTO `LoginLog` (userId, ip, userAgent, deviceFp, success, type, failReason, createdAt) "
            "VALUES (:userId, :ip, :userAgent, :deviceFp, :success, :type, :failReason, :now)"
        ),
        {
            "userId": data.get("userId") or "unknown",
            "ip": data.get("ip") or "",
            "userAgent": data.get("userAgent") or "",
            "deviceFp": data.get("deviceFp") or "",
            "success": 1 if data.get("success") else 0,
            "type": data.get("type") or "login",
            "failReason": data.get("failReason") or "",
            "now": dt.datetime.utcnow(),
        },
    )
    await db.commit()


async def trusted_ips(db: AsyncSession, register_ip: str | None, cid: str) -> set[str]:
    """可信 IP = 注册 IP + 最近 N 条成功登录 IP。"""
    from app.config import settings

    ips: set[str] = set()
    if register_ip:
        ips.add(register_ip)
    rows = (
        await db.execute(
            text(
                "SELECT ip FROM `LoginLog` WHERE userId = :cid AND success = 1 "
                "ORDER BY createdAt DESC LIMIT :limit"
            ),
            {"cid": cid, "limit": max(1, int(settings.TRUSTED_IP_LOGIN_HISTORY))},
        )
    ).all()
    for row in rows:
        ip = row._mapping.get("ip")
        if ip:
            ips.add(ip)
    return ips


# ---------------- VerificationCode（邮箱验证码，DB 共享） ----------------
_verification_schema_ready = False


async def ensure_verification_schema() -> None:
    """幂等补充 VerificationCode.purpose / attempts 列（启动时调用）。"""
    global _verification_schema_ready
    if _verification_schema_ready:
        return
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT `COLUMN_NAME` AS name FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'VerificationCode'"
                )
            )
        ).all()
        columns = {str(r._mapping.get("name") or "").lower() for r in rows}
        if not columns:
            return
        pending = []
        if "purpose" not in columns:
            pending.append(
                (
                    "purpose",
                    "ALTER TABLE `VerificationCode` ADD COLUMN `purpose` VARCHAR(20) "
                    "NOT NULL DEFAULT 'register'",
                )
            )
        if "attempts" not in columns:
            pending.append(
                (
                    "attempts",
                    "ALTER TABLE `VerificationCode` ADD COLUMN `attempts` INT NOT NULL DEFAULT 0",
                )
            )
        for _name, ddl in pending:
            try:
                await db.execute(text(ddl))
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                # 多 worker 同时启动时另一个 worker 可能已加列
                if "Duplicate column name" not in str(exc):
                    raise
    _verification_schema_ready = True


async def store_verification_code(
    db: AsyncSession,
    email: str,
    code: str,
    ttl_ms: int | None = None,
    purpose: str = "register",
) -> None:
    if ttl_ms is None:
        from app.config import settings

        ttl_ms = max(1, int(settings.VERIFY_CODE_TTL_SECONDS)) * 1000
    await db.execute(
        text("DELETE FROM `VerificationCode` WHERE email = :email AND purpose = :purpose"),
        {"email": email, "purpose": purpose},
    )
    await db.execute(
        text(
            "INSERT INTO `VerificationCode` (email, code, purpose, attempts, expiresAt, createdAt) "
            "VALUES (:email, :code, :purpose, 0, :expiresAt, :now)"
        ),
        {
            "email": email,
            "code": code,
            "purpose": purpose,
            "expiresAt": dt.datetime.utcnow() + dt.timedelta(milliseconds=ttl_ms),
            "now": dt.datetime.utcnow(),
        },
    )
    await db.commit()


async def consume_verification_code(
    db: AsyncSession,
    email: str,
    code: str,
    purpose: str,
    max_attempts: int | None = None,
) -> bool:
    """按 purpose 校验并一次性消费验证码；错误计数落库，达到上限即删除。"""
    if max_attempts is None:
        from app.config import settings

        max_attempts = max(1, int(settings.VERIFY_CODE_MAX_ATTEMPTS))
    rows = (
        await db.execute(
            text(
                "SELECT id, code, attempts FROM `VerificationCode` "
                "WHERE email = :email AND purpose = :purpose AND expiresAt > :now "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"email": email, "purpose": purpose, "now": dt.datetime.utcnow()},
        )
    ).all()
    if not rows:
        return False

    import secrets as _secrets

    latest = rows[0]
    record = _row_to_dict(latest)
    code_id = int(record["id"])
    if _secrets.compare_digest(str(record.get("code") or ""), str(code)):
        await db.execute(text("DELETE FROM `VerificationCode` WHERE id = :id"), {"id": code_id})
        await db.commit()
        return True

    attempts = int(record.get("attempts") or 0) + 1
    if attempts >= max(1, int(max_attempts)):
        await db.execute(text("DELETE FROM `VerificationCode` WHERE id = :id"), {"id": code_id})
    else:
        await db.execute(
            text("UPDATE `VerificationCode` SET attempts = :attempts WHERE id = :id"),
            {"attempts": attempts, "id": code_id},
        )
    await db.commit()
    return False


async def delete_verification_code(db: AsyncSession, code_id: int) -> None:
    await db.execute(text("DELETE FROM `VerificationCode` WHERE id = :id"), {"id": code_id})
    await db.commit()


async def delete_verification_codes(
    db: AsyncSession, email: str, purpose: str | None = None
) -> None:
    if purpose:
        await db.execute(
            text("DELETE FROM `VerificationCode` WHERE email = :email AND purpose = :purpose"),
            {"email": email, "purpose": purpose},
        )
    else:
        await db.execute(text("DELETE FROM `VerificationCode` WHERE email = :email"), {"email": email})
    await db.commit()


__all__ = [
    "find_user_with_credentials",
    "find_user_public",
    "find_user_by_email",
    "find_first_by_column",
    "count_admins",
    "create_user",
    "update_user",
    "delete_login_attempts",
    "delete_login_attempts_before",
    "count_login_attempts_since",
    "insert_login_attempt",
    "insert_login_log",
    "trusted_ips",
    "ensure_verification_schema",
    "store_verification_code",
    "consume_verification_code",
    "delete_verification_code",
    "delete_verification_codes",
]
