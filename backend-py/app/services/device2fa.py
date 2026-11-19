"""站内设备密钥（自研 Passkey）2FA。

浏览器用 Web Crypto 生成不可导出的 ECDSA P-256 私钥，存 IndexedDB；
服务端只保存公钥 JWK。登录第二步用本机私钥对一次性登录挑战签名，无需手机/第三方 App。
恢复码只保存 SHA-256 哈希。
"""
from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import mfa

COLUMNS = {
    "device2faEnabled": "TINYINT NOT NULL DEFAULT 0",
    "device2faPublicKey": "TEXT NULL",
    "device2faRecoveryCodes": "TEXT NULL",
}


async def ensure_schema(db: AsyncSession | None = None) -> None:
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
    changed = False
    for column, definition in COLUMNS.items():
        if column not in existing:
            await db.execute(text(f"ALTER TABLE `User` ADD COLUMN `{column}` {definition}"))
            changed = True
    if changed:
        await db.commit()


def _b64url_decode(value: str) -> bytes:
    raw = str(value or "").strip()
    return base64.urlsafe_b64decode(raw + "=" * ((4 - len(raw) % 4) % 4))


def _validate_public_key(jwk_json: str) -> dict[str, Any]:
    try:
        jwk = json.loads(jwk_json)
    except (TypeError, ValueError):
        raise ValueError("公钥格式错误") from None
    if not isinstance(jwk, dict) or jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
        raise ValueError("仅支持 P-256 设备密钥")
    x = str(jwk.get("x") or "")
    y = str(jwk.get("y") or "")
    if not x or not y:
        raise ValueError("公钥缺少坐标")
    try:
        xb, yb = _b64url_decode(x), _b64url_decode(y)
        if len(xb) != 32 or len(yb) != 32:
            raise ValueError
        ec.EllipticCurvePublicNumbers(
            int.from_bytes(xb, "big"), int.from_bytes(yb, "big"), ec.SECP256R1()
        ).public_key()
    except ValueError:
        raise ValueError("设备公钥无效") from None
    except Exception:
        raise ValueError("设备公钥无效") from None
    return {"kty": "EC", "crv": "P-256", "x": x, "y": y}


async def get_state(db: AsyncSession, cid: str) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                "SELECT `device2faEnabled`, `device2faPublicKey`, `device2faRecoveryCodes` "
                "FROM `User` WHERE `cid` = :cid LIMIT 1"
            ),
            {"cid": str(cid)},
        )
    ).first()
    return dict(row._mapping) if row else {}


async def enable(db: AsyncSession, cid: str, public_key_json: str) -> tuple[list[str], str]:
    jwk = _validate_public_key(public_key_json)
    codes, recovery_json = mfa.generate_recovery_codes()
    await db.execute(
        text(
            "UPDATE `User` SET `device2faEnabled` = 1, `device2faPublicKey` = :pub, "
            "`device2faRecoveryCodes` = :codes WHERE `cid` = :cid"
        ),
        {
            "pub": json.dumps(jwk, separators=(",", ":"), ensure_ascii=False),
            "codes": recovery_json,
            "cid": str(cid),
        },
    )
    await db.commit()
    return codes, recovery_json


async def disable(db: AsyncSession, cid: str) -> None:
    await db.execute(
        text(
            "UPDATE `User` SET `device2faEnabled` = 0, `device2faPublicKey` = NULL, "
            "`device2faRecoveryCodes` = NULL WHERE `cid` = :cid"
        ),
        {"cid": str(cid)},
    )
    await db.commit()


async def update_recovery_codes(db: AsyncSession, cid: str, recovery_json: str) -> None:
    await db.execute(
        text("UPDATE `User` SET `device2faRecoveryCodes` = :codes WHERE `cid` = :cid"),
        {"codes": recovery_json, "cid": str(cid)},
    )
    await db.commit()


def verify_signature(public_key_json: str | None, message: str, signature_b64: str) -> bool:
    try:
        jwk = json.loads(public_key_json or "")
        x = _b64url_decode(str(jwk["x"]))
        y = _b64url_decode(str(jwk["y"]))
        pub = ec.EllipticCurvePublicNumbers(
            int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()
        ).public_key()
        sig = base64.b64decode(str(signature_b64 or ""), validate=True)
        if len(sig) == 64:
            # WebCrypto ECDSA 返回 r||s 原始拼接；转成 DER 供 cryptography 校验
            sig = encode_dss_signature(
                int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big")
            )
        pub.verify(sig, str(message).encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, TypeError, KeyError, binascii.Error):
        return False


__all__ = [
    "COLUMNS",
    "ensure_schema",
    "get_state",
    "enable",
    "disable",
    "update_recovery_codes",
    "verify_signature",
]
