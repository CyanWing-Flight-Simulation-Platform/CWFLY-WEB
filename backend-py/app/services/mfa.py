"""管理员双因素认证（TOTP，RFC 6238）+ 恢复码。

不依赖第三方库，使用标准库实现：
- 登录密码通过后，管理员必须再输入 TOTP 6 位动态码；
- 首次登录自动进入绑定流程，绑定成功才签发 access token；
- 恢复码只保存 SHA-256 哈希，使用后立即失效。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from typing import Any
from urllib.parse import quote

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MFA_ISSUER = "CWFLY"
TOTP_DIGITS = 6
TOTP_STEP = 30
TOTP_WINDOW = 1
RECOVERY_CODE_COUNT = 8


def generate_secret() -> str:
    """生成 160-bit Base32 密钥（标准 TOTP 格式，无填充）。"""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    raw = str(secret or "").strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(raw) % 8) % 8)
    return base64.b32decode(raw + padding, casefold=True)


def _totp_at(secret: str, step: int) -> str:
    key = _decode_secret(secret)
    counter = int(step)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def verify_totp(secret: str, code: str, window: int = TOTP_WINDOW) -> bool:
    if not secret:
        return False
    clean = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(clean) != TOTP_DIGITS:
        return False
    current = int(time.time()) // TOTP_STEP
    for offset in range(-abs(window), abs(window) + 1):
        if hmac.compare_digest(_totp_at(secret, current + offset), clean):
            return True
    return False


def otpauth_url(cid: str, secret: str) -> str:
    label = quote(f"{MFA_ISSUER}:{cid}", safe=":")
    return (
        f"otpauth://totp/{label}?secret={secret}"
        f"&issuer={quote(MFA_ISSUER)}&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_STEP}"
    )


def _hash_recovery(code: str) -> str:
    return hashlib.sha256(str(code).replace("-", "").strip().lower().encode("utf-8")).hexdigest()


def generate_recovery_codes() -> tuple[list[str], str]:
    """返回（明文恢复码，JSON 哈希数组）。明文只在绑定成功时展示一次。"""
    codes: list[str] = []
    hashes: list[str] = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = secrets.token_hex(4).upper()
        code = f"{raw[:4]}-{raw[4:]}"
        codes.append(code)
        hashes.append(_hash_recovery(code))
    return codes, json.dumps(hashes, ensure_ascii=False)


def consume_recovery_code(stored_json: str | None, code: str) -> tuple[bool, str | None]:
    """校验并消耗一个恢复码；返回（是否成功，剩余哈希 JSON）。"""
    try:
        hashes = json.loads(stored_json or "[]")
    except (TypeError, ValueError):
        return False, stored_json
    if not isinstance(hashes, list):
        return False, stored_json
    target = _hash_recovery(code)
    for index, item in enumerate(hashes):
        if hmac.compare_digest(str(item), target):
            remaining = hashes[:index] + hashes[index + 1 :]
            return True, json.dumps(remaining, ensure_ascii=False)
    return False, stored_json


async def ensure_schema(db: AsyncSession | None = None) -> None:
    """幂等补齐 User 表 MFA 列。"""
    if db is None:
        from app.db.session import SessionLocal

        async with SessionLocal() as session:
            await ensure_schema(session)
        return
    rows = (
        await db.execute(
            text(
                "SELECT COLUMN_NAME FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'User'"
            )
        )
    ).all()
    existing = {str(row[0]) for row in rows}
    additions = {
        "mfaEnabled": "TINYINT NOT NULL DEFAULT 0",
        "mfaSecret": "VARCHAR(64) NULL",
        "mfaRecoveryCodes": "TEXT NULL",
    }
    changed = False
    for column, definition in additions.items():
        if column not in existing:
            await db.execute(text(f"ALTER TABLE `User` ADD COLUMN `{column}` {definition}"))
            changed = True
    if changed:
        await db.commit()


async def get_mfa_state(db: AsyncSession, cid: str) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                "SELECT `mfaEnabled`, `mfaSecret`, `mfaRecoveryCodes` "
                "FROM `User` WHERE `cid` = :cid LIMIT 1"
            ),
            {"cid": str(cid)},
        )
    ).first()
    return dict(row._mapping) if row else {}


async def set_mfa_secret(
    db: AsyncSession, cid: str, secret: str, *, enabled: bool = False
) -> None:
    await db.execute(
        text(
            "UPDATE `User` SET `mfaSecret` = :secret, `mfaEnabled` = :enabled "
            "WHERE `cid` = :cid"
        ),
        {"secret": secret, "enabled": 1 if enabled else 0, "cid": str(cid)},
    )
    await db.commit()


async def enable_mfa(
    db: AsyncSession, cid: str, secret: str, recovery_json: str
) -> None:
    await db.execute(
        text(
            "UPDATE `User` SET `mfaEnabled` = 1, `mfaSecret` = :secret, "
            "`mfaRecoveryCodes` = :codes WHERE `cid` = :cid"
        ),
        {"secret": secret, "codes": recovery_json, "cid": str(cid)},
    )
    await db.commit()


async def disable_mfa(db: AsyncSession, cid: str) -> None:
    await db.execute(
        text(
            "UPDATE `User` SET `mfaEnabled` = 0, `mfaSecret` = NULL, "
            "`mfaRecoveryCodes` = NULL WHERE `cid` = :cid"
        ),
        {"cid": str(cid)},
    )
    await db.commit()


async def update_recovery_codes(db: AsyncSession, cid: str, recovery_json: str) -> None:
    await db.execute(
        text("UPDATE `User` SET `mfaRecoveryCodes` = :codes WHERE `cid` = :cid"),
        {"codes": recovery_json, "cid": str(cid)},
    )
    await db.commit()


__all__ = [
    "MFA_ISSUER",
    "TOTP_DIGITS",
    "TOTP_STEP",
    "RECOVERY_CODE_COUNT",
    "generate_secret",
    "verify_totp",
    "otpauth_url",
    "generate_recovery_codes",
    "consume_recovery_code",
    "ensure_schema",
    "get_mfa_state",
    "set_mfa_secret",
    "enable_mfa",
    "disable_mfa",
    "update_recovery_codes",
]
