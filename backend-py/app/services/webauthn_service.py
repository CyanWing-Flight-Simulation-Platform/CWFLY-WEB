"""标准 WebAuthn / Passkey 服务。

- 凭据公钥、credential id、签名计数器存 MySQL；
- Challenge 一次性落库，支持多实例；
- 不保存任何生物特征数据，生物识别只在用户本地设备完成。
"""
from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import settings

CHALLENGE_TTL_SECONDS = 300

DDL = [
    """
    CREATE TABLE IF NOT EXISTS `webauthn_credentials` (
      `id` bigint NOT NULL AUTO_INCREMENT,
      `cid` varchar(191) NOT NULL,
      `credential_id` varchar(512) NOT NULL,
      `public_key` text NOT NULL,
      `sign_count` bigint NOT NULL DEFAULT 0,
      `transports` varchar(255) NOT NULL DEFAULT '',
      `name` varchar(120) NOT NULL DEFAULT '',
      `aaguid` varchar(64) NOT NULL DEFAULT '',
      `backed_up` tinyint NOT NULL DEFAULT 0,
      `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
      `lastUsedAt` datetime(3) DEFAULT NULL,
      PRIMARY KEY (`id`),
      UNIQUE KEY `webauthn_credentials_credential_key` (`credential_id`),
      KEY `webauthn_credentials_cid_idx` (`cid`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `webauthn_challenges` (
      `id` bigint NOT NULL AUTO_INCREMENT,
      `cid` varchar(191) NOT NULL,
      `kind` varchar(16) NOT NULL,
      `challenge` varchar(255) NOT NULL,
      `expiresAt` datetime(3) NOT NULL,
      `used` tinyint NOT NULL DEFAULT 0,
      `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
      PRIMARY KEY (`id`),
      KEY `webauthn_challenges_lookup_idx` (`cid`, `kind`, `used`, `id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    text = str(value or "").strip()
    text += "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text.encode("ascii"))


async def ensure_schema(db: AsyncSession) -> None:
    for ddl in DDL:
        await db.execute(text(ddl))
    await db.commit()


async def store_challenge(db: AsyncSession, cid: str, kind: str, challenge: bytes) -> None:
    await db.execute(
        text("DELETE FROM `webauthn_challenges` WHERE expiresAt < NOW(3)"),
    )
    await db.execute(
        text(
            "INSERT INTO `webauthn_challenges` (cid, kind, challenge, expiresAt) "
            "VALUES (:cid, :kind, :challenge, DATE_ADD(NOW(3), INTERVAL :ttl SECOND))"
        ),
        {
            "cid": cid,
            "kind": kind,
            "challenge": b64url_encode(challenge),
            "ttl": CHALLENGE_TTL_SECONDS,
        },
    )
    await db.commit()


async def load_challenge(db: AsyncSession, cid: str, kind: str) -> bytes | None:
    row = (
        await db.execute(
            text(
                "SELECT challenge FROM `webauthn_challenges` "
                "WHERE cid = :cid AND kind = :kind AND used = 0 "
                "AND expiresAt > NOW(3) ORDER BY id DESC LIMIT 1"
            ),
            {"cid": cid, "kind": kind},
        )
    ).first()
    if row is None:
        return None
    return b64url_decode(row._mapping["challenge"])


async def consume_challenge(db: AsyncSession, cid: str, kind: str, challenge: bytes) -> bool:
    row = (
        await db.execute(
            text(
                "SELECT id FROM `webauthn_challenges` "
                "WHERE cid = :cid AND kind = :kind AND used = 0 "
                "AND challenge = :challenge AND expiresAt > NOW(3) "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"cid": cid, "kind": kind, "challenge": b64url_encode(challenge)},
        )
    ).first()
    if row is None:
        return False
    result = await db.execute(
        text(
            "UPDATE `webauthn_challenges` SET used = 1 "
            "WHERE id = :id AND used = 0"
        ),
        {"id": int(row._mapping["id"])},
    )
    await db.commit()
    return int(result.rowcount or 0) == 1


async def list_credentials(db: AsyncSession, cid: str) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            text(
                "SELECT id, credential_id, name, transports, sign_count, createdAt, lastUsedAt "
                "FROM `webauthn_credentials` WHERE cid = :cid ORDER BY id ASC"
            ),
            {"cid": cid},
        )
    ).all()
    return [
        {
            "id": int(r._mapping["id"]),
            "credentialId": r._mapping["credential_id"],
            "name": r._mapping["name"] or "Passkey",
            "transports": [x for x in str(r._mapping["transports"] or "").split(",") if x],
            "signCount": int(r._mapping["sign_count"] or 0),
            "createdAt": r._mapping["createdAt"],
            "lastUsedAt": r._mapping["lastUsedAt"],
        }
        for r in rows
    ]


def _split_transports(raw: Any) -> list[Any] | None:
    """库里以逗号分隔存储（internal,hybrid），转成 WebAuthn 的 transports 枚举列表。"""
    if not raw:
        return None
    from webauthn.helpers.structs import AuthenticatorTransport

    valid = {t.value: t for t in AuthenticatorTransport}
    items = [str(x).strip().lower() for x in str(raw).split(",") if str(x).strip()]
    out = [valid[item] for item in items if item in valid]
    return out or None


async def _raw_credentials(db: AsyncSession, cid: str) -> list[PublicKeyCredentialDescriptor]:
    rows = (
        await db.execute(
            text("SELECT credential_id, transports FROM `webauthn_credentials` WHERE cid = :cid"),
            {"cid": cid},
        )
    ).all()
    out: list[PublicKeyCredentialDescriptor] = []
    for r in rows:
        d = r._mapping
        kwargs: dict[str, Any] = {"id": b64url_decode(d["credential_id"])}
        transports = _split_transports(d.get("transports"))
        if transports:
            # 关键：告诉浏览器凭据可能在手机上（hybrid）或在本地（internal），
            # 否则 Chrome 只会尝试本地凭据管理器，手机上的 Passkey 永远唤不起来。
            kwargs["transports"] = transports
        out.append(PublicKeyCredentialDescriptor(**kwargs))
    return out


async def has_credentials(db: AsyncSession, cid: str) -> bool:
    """该账号是否绑定过 Passkey（登录前用它做前置判断，避免无凭据时唤起系统创建对话框）。"""
    row = (
        await db.execute(
            text("SELECT COUNT(*) AS c FROM `webauthn_credentials` WHERE cid = :cid"),
            {"cid": cid},
        )
    ).first()
    return bool(row and int(row._mapping["c"]) > 0)


async def registration_options(db: AsyncSession, cid: str, username: str) -> dict[str, Any]:
    exclude = await _raw_credentials(db, cid)
    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=str(cid).encode("utf-8"),
        user_name=str(cid),
        user_display_name=str(username or cid),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude,
    )
    await store_challenge(db, cid, "register", options.challenge)
    data = json.loads(options_to_json(options))
    # passkeys.dev 推荐：让认证器回报 credProps，便于判断是否可发现凭据
    data["extensions"] = {"credProps": True}
    return data


async def verification_response(
    db: AsyncSession,
    cid: str,
    credential: dict[str, Any],
    name: str,
    transports: list[str],
) -> dict[str, Any]:
    challenge = await load_challenge(db, cid, "register")
    if not challenge:
        raise ValueError("注册验证已过期，请重新发起")
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origins,
            require_user_presence=True,
            require_user_verification=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Passkey 验证失败：{exc}") from exc

    if not await consume_challenge(db, cid, "register", challenge):
        raise ValueError("注册验证已失效，请重新发起")

    credential_id = b64url_encode(verified.credential_id)
    public_key = b64url_encode(verified.credential_public_key)
    try:
        await db.execute(
            text(
                "INSERT INTO `webauthn_credentials` "
                "(cid, credential_id, public_key, sign_count, transports, name, aaguid, backed_up) "
                "VALUES (:cid, :cred_id, :pub, :sign, :transports, :name, :aaguid, :backed_up)"
            ),
            {
                "cid": cid,
                "cred_id": credential_id,
                "pub": public_key,
                "sign": int(verified.sign_count or 0),
                "transports": ",".join(str(x)[:32] for x in (transports or []))[:255],
                "name": str(name or "Passkey")[:120],
                "aaguid": str(getattr(verified, "aaguid", "") or "")[:64],
                "backed_up": 1 if getattr(verified, "credential_backed_up", False) else 0,
            },
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise ValueError("该 Passkey 已绑定或保存失败") from exc
    return {"credentialId": credential_id, "name": str(name or "Passkey")}


async def authentication_options(db: AsyncSession, cid: str | None = None) -> dict[str, Any]:
    allow = await _raw_credentials(db, cid) if cid else None
    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=allow,
        timeout=60000,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    await store_challenge(db, cid or "", "login", options.challenge)
    return json.loads(options_to_json(options))


async def verify_login(
    db: AsyncSession,
    cid: str | None,
    credential: dict[str, Any],
    challenge_token: str | None = None,
) -> str:
    if challenge_token:
        row = (
            await db.execute(
                text(
                    "SELECT challenge FROM `webauthn_challenges` "
                    "WHERE kind = 'login' AND used = 0 AND challenge = :challenge "
                    "AND expiresAt > NOW(3) ORDER BY id DESC LIMIT 1"
                ),
                {"challenge": challenge_token},
            )
        ).first()
    else:
        row = (
            await db.execute(
                text(
                    "SELECT challenge FROM `webauthn_challenges` "
                    "WHERE cid = :cid AND kind = 'login' AND used = 0 "
                    "AND expiresAt > NOW(3) ORDER BY id DESC LIMIT 1"
                ),
                {"cid": cid or ""},
            )
        ).first()
    if row is None:
        raise ValueError("Passkey 登录已过期，请重试")
    challenge = b64url_decode(row._mapping["challenge"])
    raw = dict(credential or {})
    credential_id = str(raw.get("id") or raw.get("rawId") or "").strip()
    if not credential_id:
        raise ValueError("Passkey 凭据缺少 ID")
    if cid:
        cred_row = (
            await db.execute(
                text(
                    "SELECT id, cid, public_key, sign_count FROM `webauthn_credentials` "
                    "WHERE cid = :cid AND credential_id = :cred LIMIT 1"
                ),
                {"cid": cid, "cred": credential_id},
            )
        ).first()
    else:
        cred_row = (
            await db.execute(
                text(
                    "SELECT id, cid, public_key, sign_count FROM `webauthn_credentials` "
                    "WHERE credential_id = :cred LIMIT 1"
                ),
                {"cred": credential_id},
            )
        ).first()
    if cred_row is None:
        raise ValueError("未找到该 Passkey")
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origins,
            credential_public_key=b64url_decode(cred_row._mapping["public_key"]),
            credential_current_sign_count=int(cred_row._mapping["sign_count"] or 0),
            require_user_verification=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Passkey 验证失败：{exc}") from exc
    consumed = await db.execute(
        text(
            "UPDATE `webauthn_challenges` SET used = 1 "
            "WHERE kind = 'login' AND used = 0 AND expiresAt > NOW(3) "
            "AND challenge = :challenge"
        ),
        {"challenge": b64url_encode(challenge)},
    )
    await db.commit()
    if int(consumed.rowcount or 0) == 0:
        raise ValueError("Passkey 登录已失效，请重试")
    new_count = max(int(verified.new_sign_count or 0), int(cred_row._mapping["sign_count"] or 0))
    await db.execute(
        text(
            "UPDATE `webauthn_credentials` SET sign_count = :sign, lastUsedAt = NOW(3) "
            "WHERE id = :id"
        ),
        {"sign": new_count, "id": int(cred_row._mapping["id"])},
    )
    await db.commit()
    return str(cred_row._mapping["cid"])


async def delete_credential(db: AsyncSession, cid: str, credential_row_id: int) -> bool:
    result = await db.execute(
        text("DELETE FROM `webauthn_credentials` WHERE id = :id AND cid = :cid"),
        {"id": int(credential_row_id), "cid": cid},
    )
    await db.commit()
    return int(result.rowcount or 0) == 1


__all__ = [
    "ensure_schema",
    "list_credentials",
    "registration_options",
    "verification_response",
    "authentication_options",
    "verify_login",
    "delete_credential",
]
