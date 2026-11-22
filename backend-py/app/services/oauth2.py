"""OAuth2 授权服务器核心（零新增依赖：hmac / hashlib / secrets / base64）。

用途：让 Dubhe Nexus / Merak 等第三方通过标准 OAuth2 授权码流程绑定 CWFLY 账号。

实现范围：
- RFC 6749：Authorization Code + Refresh Token
- RFC 6750：Bearer Token（Authorization: Bearer <token>）
- RFC 7636：PKCE（S256 / plain）

安全要点：
1) 授权码 / 访问令牌 / 刷新令牌**只落库 SHA-256 摘要**，库被读也无法直接冒用；
2) 授权码一次性使用（事务内 `UPDATE ... WHERE used = 0` 的 rowcount 判定）；
3) 同意页参数用 JWT_SECRET 派生密钥做 HMAC 签名，前端隐藏域不可篡改；
4) redirect_uri 严格白名单精确匹配，杜绝开放重定向；
5) 客户端凭据比较用 hmac.compare_digest（常量时间）。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any, Optional
from urllib.parse import urlencode

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

log = logging.getLogger("cwfly.oauth2")

# 同意页签名载荷有效期（秒）
APPROVAL_TTL_SECONDS = 600

# 已登记客户端的展示信息（图标/主页）。新增第三方应用时在此追加即可。
CLIENT_ICON_URLS: dict[str, str] = {
    "merak": "https://www.dubhenexus.io/images/Dubhe-Nexus.svg",
}
MERAK_ICON_URL = CLIENT_ICON_URLS["merak"]

# scope -> 中文说明（同意页展示用）
SCOPE_LABELS: dict[str, str] = {
    "profile": "基本资料（用户名、头像、CID、飞行等级）",
    "email": "邮箱地址",
    "qq": "QQ 号码",
    "openid": "唯一身份标识（用于关联账号）",
}

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS `oauth2_codes` (
      `id` int NOT NULL AUTO_INCREMENT,
      `code_hash` char(64) NOT NULL,
      `client_id` varchar(64) NOT NULL,
      `cid` varchar(32) NOT NULL,
      `redirect_uri` varchar(512) NOT NULL,
      `scope` varchar(255) NOT NULL DEFAULT '',
      `code_challenge` varchar(128) DEFAULT NULL,
      `code_challenge_method` varchar(16) DEFAULT NULL,
      `used` tinyint(1) NOT NULL DEFAULT 0,
      `expiresAt` datetime(3) NOT NULL,
      `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_oauth2_code_hash` (`code_hash`),
      KEY `idx_oauth2_codes_exp` (`expiresAt`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `oauth2_tokens` (
      `id` int NOT NULL AUTO_INCREMENT,
      `access_hash` char(64) NOT NULL,
      `refresh_hash` char(64) DEFAULT NULL,
      `client_id` varchar(64) NOT NULL,
      `cid` varchar(32) NOT NULL,
      `scope` varchar(255) NOT NULL DEFAULT '',
      `accessExpiresAt` datetime(3) NOT NULL,
      `refreshExpiresAt` datetime(3) DEFAULT NULL,
      `revoked` tinyint(1) NOT NULL DEFAULT 0,
      `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_oauth2_access_hash` (`access_hash`),
      KEY `idx_oauth2_refresh_hash` (`refresh_hash`),
      KEY `idx_oauth2_tokens_cid` (`cid`),
      KEY `idx_oauth2_tokens_exp` (`accessExpiresAt`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
)


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(text_value: str) -> bytes:
    pad = "=" * (-len(text_value) % 4)
    return base64.urlsafe_b64decode(text_value + pad)


def _approval_key() -> bytes:
    """同意页签名密钥：由 JWT_SECRET 派生，与 access token 密钥域隔离。"""
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"), b"oauth2-approval", hashlib.sha256
    ).digest()


def is_configured() -> bool:
    return settings.oauth2_ready


def registered_apps() -> list[dict[str, Any]]:
    """已登记客户端（用于「已授权应用」列表的图标/名称/主页）。"""
    client_id = (settings.OAUTH2_CLIENT_ID or "").strip()
    if not client_id:
        return []
    return [
        {
            "id": client_id,
            "name": settings.OAUTH2_CLIENT_NAME or "第三方应用",
            "icon": MERAK_ICON_URL,
            "homepage": "https://merak.dubhenexus.io",
            "scopes": settings.oauth2_scopes,
        }
    ]


def _app_meta(client_id: str) -> dict[str, Any]:
    for app in registered_apps():
        if app["id"] == client_id:
            return app
    return {
        "id": client_id,
        "name": client_id or "未知应用",
        "icon": "",
        "homepage": "",
        "scopes": [],
    }



def redirect_uri_allowed(uri: str) -> bool:
    """回调地址白名单：精确匹配（不做前缀/通配，避免被拼接利用）。"""
    target = (uri or "").strip()
    if not target:
        return False
    return target in settings.oauth2_redirect_uris


def client_credentials_match(client_id: str, client_secret: str) -> bool:
    expected_id = (settings.OAUTH2_CLIENT_ID or "").strip()
    expected_secret = (settings.OAUTH2_CLIENT_SECRET or "").strip()
    if not expected_id or not expected_secret:
        return False
    id_ok = hmac.compare_digest((client_id or "").strip(), expected_id)
    secret_ok = hmac.compare_digest((client_secret or "").strip(), expected_secret)
    return id_ok and secret_ok


def parse_scope(raw: str) -> Optional[list[str]]:
    """把请求 scope 归一化；包含未授权 scope 时返回 None（invalid_scope）。"""
    allowed = settings.oauth2_scopes
    if not allowed:
        return []
    requested = (raw or "").replace(",", " ").split()
    if not requested:
        return list(allowed)
    scope_list: list[str] = []
    for item in requested:
        if item not in allowed:
            return None
        if item not in scope_list:
            scope_list.append(item)
    return scope_list


def scope_string(scopes: list[str]) -> str:
    return " ".join(scopes)


def build_redirect(redirect_uri: str, params: dict[str, str]) -> str:
    """在已有 query 的回调地址后追加参数（保留原 query）。"""
    sep = "&" if "?" in redirect_uri else "?"
    clean = {k: v for k, v in params.items() if v}
    if not clean:
        return redirect_uri
    return f"{redirect_uri}{sep}{urlencode(clean)}"


# --------------------------------------------------------------------------- #
# 同意页签名载荷
# --------------------------------------------------------------------------- #
def sign_approval(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + APPROVAL_TTL_SECONDS
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    token = b64url_encode(raw)
    sig = hmac.new(_approval_key(), token.encode("ascii"), hashlib.sha256).digest()
    return token + "." + b64url_encode(sig)


def verify_approval(value: str) -> Optional[dict[str, Any]]:
    if not value or "." not in value:
        return None
    token, _, sig = value.partition(".")
    expected = hmac.new(_approval_key(), token.encode("ascii"), hashlib.sha256).digest()
    try:
        provided = b64url_decode(sig)
    except Exception:  # noqa: BLE001
        return None
    if not hmac.compare_digest(provided, expected):
        return None
    try:
        data = json.loads(b64url_decode(token).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict):
        return None
    if int(data.get("exp") or 0) < int(time.time()):
        return None
    return data


# --------------------------------------------------------------------------- #
# 表结构
# --------------------------------------------------------------------------- #
async def ensure_schema(db: AsyncSession) -> None:
    for ddl in _DDL:
        await db.execute(text(ddl))
    await db.commit()


async def cleanup(db: AsyncSession) -> None:
    """清理过期授权码与令牌（每次签发时顺带执行，代价可忽略）。"""
    await db.execute(text("DELETE FROM `oauth2_codes` WHERE expiresAt < NOW(3)"))
    await db.execute(
        text(
            "DELETE FROM `oauth2_tokens` WHERE accessExpiresAt < DATE_SUB(NOW(3), INTERVAL 1 DAY)"
        )
    )


# --------------------------------------------------------------------------- #
# 授权码
# --------------------------------------------------------------------------- #
async def issue_code(
    db: AsyncSession,
    *,
    cid: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    code_challenge: str = "",
    code_challenge_method: str = "",
) -> str:
    await cleanup(db)
    code = secrets.token_urlsafe(32)
    await db.execute(
        text(
            "INSERT INTO `oauth2_codes` "
            "(code_hash, client_id, cid, redirect_uri, scope, code_challenge, "
            " code_challenge_method, expiresAt) "
            "VALUES (:code_hash, :client_id, :cid, :redirect_uri, :scope, :cc, :ccm, "
            "        DATE_ADD(NOW(3), INTERVAL :ttl SECOND))"
        ),
        {
            "code_hash": _hash(code),
            "client_id": client_id,
            "cid": cid,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "cc": (code_challenge or None),
            "ccm": (code_challenge_method or None),
            "ttl": int(settings.OAUTH2_CODE_TTL_SECONDS),
        },
    )
    await db.commit()
    return code


async def consume_code(
    db: AsyncSession,
    *,
    code: str,
    client_id: str,
    redirect_uri: str,
    code_verifier: str = "",
) -> Optional[dict[str, Any]]:
    """校验并一次性消费授权码；失败返回 None。"""
    if not code:
        return None
    row = (
        await db.execute(
            text(
                "SELECT id, cid, scope, redirect_uri, code_challenge, code_challenge_method "
                "FROM `oauth2_codes` "
                "WHERE code_hash = :code_hash AND client_id = :client_id "
                "  AND used = 0 AND expiresAt > NOW(3) LIMIT 1"
            ),
            {"code_hash": _hash(code), "client_id": client_id},
        )
    ).first()
    if row is None:
        return None
    data = dict(row._mapping)
    if (data.get("redirect_uri") or "") != (redirect_uri or ""):
        return None
    if not _verify_pkce(
        code_verifier,
        data.get("code_challenge") or "",
        (data.get("code_challenge_method") or "").upper(),
    ):
        return None

    consumed = await db.execute(
        text("UPDATE `oauth2_codes` SET used = 1 WHERE id = :id AND used = 0"),
        {"id": int(data["id"])},
    )
    if consumed.rowcount != 1:
        await db.rollback()
        return None
    await db.commit()
    return {"cid": str(data["cid"]), "scope": data.get("scope") or ""}


def _verify_pkce(verifier: str, challenge: str, method: str) -> bool:
    """无 challenge 时视为未启用 PKCE；有 challenge 时必须校验通过。"""
    if not challenge:
        return True
    if not verifier:
        return False
    if method in ("", "PLAIN"):
        expected = verifier
    elif method == "S256":
        expected = b64url_encode(hashlib.sha256(verifier.encode("ascii", "ignore")).digest())
    else:
        return False
    return hmac.compare_digest(expected, challenge)


# --------------------------------------------------------------------------- #
# 令牌
# --------------------------------------------------------------------------- #
async def issue_token(
    db: AsyncSession,
    *,
    cid: str,
    client_id: str,
    scope: str,
) -> dict[str, Any]:
    await cleanup(db)
    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(32)
    access_ttl = int(settings.OAUTH2_TOKEN_TTL_SECONDS)
    refresh_ttl = int(settings.OAUTH2_REFRESH_TTL_SECONDS)
    await db.execute(
        text(
            "INSERT INTO `oauth2_tokens` "
            "(access_hash, refresh_hash, client_id, cid, scope, accessExpiresAt, refreshExpiresAt) "
            "VALUES (:access_hash, :refresh_hash, :client_id, :cid, :scope, "
            "        DATE_ADD(NOW(3), INTERVAL :access_ttl SECOND), "
            "        DATE_ADD(NOW(3), INTERVAL :refresh_ttl SECOND))"
        ),
        {
            "access_hash": _hash(access_token),
            "refresh_hash": _hash(refresh_token),
            "client_id": client_id,
            "cid": cid,
            "scope": scope,
            "access_ttl": access_ttl,
            "refresh_ttl": refresh_ttl,
        },
    )
    await db.commit()
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": access_ttl,
        "refresh_token": refresh_token,
        "scope": scope,
    }


async def load_access_token(db: AsyncSession, access_token: str) -> Optional[dict[str, Any]]:
    if not access_token:
        return None
    row = (
        await db.execute(
            text(
                "SELECT cid, client_id, scope, accessExpiresAt FROM `oauth2_tokens` "
                "WHERE access_hash = :access_hash AND revoked = 0 "
                "  AND accessExpiresAt > NOW(3) LIMIT 1"
            ),
            {"access_hash": _hash(access_token)},
        )
    ).first()
    if row is None:
        return None
    data = dict(row._mapping)
    return {
        "cid": str(data["cid"]),
        "client_id": data.get("client_id") or "",
        "scope": data.get("scope") or "",
    }


async def refresh_token(
    db: AsyncSession, *, refresh_value: str, client_id: str
) -> Optional[dict[str, Any]]:
    """刷新令牌轮换：**原记录就地更新**（保留 createdAt 作为「授权时间」）。

    不新建行，避免同一授权在「已授权应用」里被重复计数，也让用户看到的
    授权时间稳定为首次授权时刻，而不是每次刷新刷新的时间。
    """
    if not refresh_value:
        return None
    row = (
        await db.execute(
            text(
                "SELECT id, cid, scope FROM `oauth2_tokens` "
                "WHERE refresh_hash = :refresh_hash AND client_id = :client_id "
                "  AND revoked = 0 AND refreshExpiresAt > NOW(3) LIMIT 1"
            ),
            {"refresh_hash": _hash(refresh_value), "client_id": client_id},
        )
    ).first()
    if row is None:
        return None
    data = dict(row._mapping)
    access_token = secrets.token_urlsafe(32)
    new_refresh = secrets.token_urlsafe(32)
    access_ttl = int(settings.OAUTH2_TOKEN_TTL_SECONDS)
    refresh_ttl = int(settings.OAUTH2_REFRESH_TTL_SECONDS)
    rotated = await db.execute(
        text(
            "UPDATE `oauth2_tokens` SET "
            "  access_hash = :access_hash, refresh_hash = :refresh_hash, "
            "  accessExpiresAt = DATE_ADD(NOW(3), INTERVAL :access_ttl SECOND), "
            "  refreshExpiresAt = DATE_ADD(NOW(3), INTERVAL :refresh_ttl SECOND) "
            "WHERE id = :id AND revoked = 0"
        ),
        {
            "access_hash": _hash(access_token),
            "refresh_hash": _hash(new_refresh),
            "access_ttl": access_ttl,
            "refresh_ttl": refresh_ttl,
            "id": int(data["id"]),
        },
    )
    if rotated.rowcount != 1:
        await db.rollback()
        return None
    await db.commit()
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": access_ttl,
        "refresh_token": new_refresh,
        "scope": data.get("scope") or "",
    }


# --------------------------------------------------------------------------- #
# 「已授权应用」（个人中心）
# --------------------------------------------------------------------------- #
async def list_authorized_apps(db: AsyncSession, cid: str) -> list[dict[str, Any]]:
    """当前用户仍在有效期内的授权应用（按 client 聚合成一条）。"""
    rows = (
        await db.execute(
            text(
                "SELECT client_id, scope, createdAt FROM `oauth2_tokens` "
                "WHERE cid = :cid AND revoked = 0 AND accessExpiresAt > NOW(3) "
                "ORDER BY createdAt DESC"
            ),
            {"cid": cid},
        )
    ).all()

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = dict(row._mapping)
        client_id = str(item.get("client_id") or "")
        if not client_id:
            continue
        bucket = grouped.get(client_id)
        scopes = {s for s in str(item.get("scope") or "").split() if s}
        if bucket is None:
            grouped[client_id] = {
                "client_id": client_id,
                "scopes": scopes,
                "authorized_at": item.get("createdAt"),
            }
        else:
            bucket["scopes"] |= scopes
            # 保留最早的授权时间（多条记录时）
            created = item.get("createdAt")
            if created and created < bucket["authorized_at"]:
                bucket["authorized_at"] = created

    result: list[dict[str, Any]] = []
    for client_id, bucket in grouped.items():
        meta = _app_meta(client_id)
        scopes = [s for s in settings.oauth2_scopes if s in bucket["scopes"]]
        result.append(
            {
                "id": client_id,
                "name": meta["name"],
                "icon": meta["icon"],
                "homepage": meta["homepage"],
                "scope": scope_string(scopes),
                "scopeLabels": [SCOPE_LABELS.get(s, s) for s in scopes],
                "authorizedAt": _iso(bucket["authorized_at"]),
            }
        )
    result.sort(key=lambda item: item.get("authorizedAt") or "", reverse=True)
    return result


async def revoke_app(db: AsyncSession, cid: str, client_id: str) -> int:
    """解除某个应用对该用户的授权（同时清理未使用的授权码）。

    只操作 `cid` 名下的记录，天然保证「只能取消自己的授权」。
    """
    if not cid or not client_id:
        return 0
    tokens = await db.execute(
        text(
            "UPDATE `oauth2_tokens` SET revoked = 1 "
            "WHERE cid = :cid AND client_id = :client_id AND revoked = 0"
        ),
        {"cid": cid, "client_id": client_id},
    )
    await db.execute(
        text(
            "DELETE FROM `oauth2_codes` "
            "WHERE cid = :cid AND client_id = :client_id AND used = 0"
        ),
        {"cid": cid, "client_id": client_id},
    )
    await db.commit()
    return int(tokens.rowcount or 0)



async def revoke(db: AsyncSession, token_value: str) -> bool:
    """按 access 或 refresh 令牌撤销整条授权记录。"""
    if not token_value:
        return False
    token_hash = _hash(token_value)
    result = await db.execute(
        text(
            "UPDATE `oauth2_tokens` SET revoked = 1 "
            "WHERE revoked = 0 AND (access_hash = :h OR refresh_hash = :h)"
        ),
        {"h": token_hash},
    )
    await db.commit()
    return result.rowcount >= 1


# --------------------------------------------------------------------------- #
# 用户资料（按 scope 裁剪）
# --------------------------------------------------------------------------- #
_USER_SQL = (
    "SELECT cid, username, rating, permissions, fsdLevel, email, qq, avatar, createdAt "
    "FROM `User` WHERE cid = :cid LIMIT 1"
)


def _absolute_avatar(value: Any) -> str:
    path = str(value or "").strip()
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{settings.oauth2_issuer}/{path.lstrip('/')}"


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


async def user_profile(db: AsyncSession, cid: str, scope: str) -> Optional[dict[str, Any]]:
    row = (await db.execute(text(_USER_SQL), {"cid": cid})).first()
    if row is None:
        return None
    data = dict(row._mapping)
    granted = set((scope or "").split())

    profile: dict[str, Any] = {"sub": str(data["cid"]), "cid": str(data["cid"])}
    if "openid" in granted:
        profile["openid"] = f"cwfly:{data['cid']}"
    if "profile" in granted or not granted:
        profile.update(
            {
                "username": data.get("username") or "",
                "nickname": data.get("username") or "",
                "avatar": _absolute_avatar(data.get("avatar")),
                "rating": int(data.get("rating") or 0),
                "fsdLevel": int(data.get("fsdLevel") or 0),
                "permissions": data.get("permissions") or "",
                "created_at": _iso(data.get("createdAt")),
            }
        )
    if "email" in granted:
        profile["email"] = data.get("email") or ""
    if "qq" in granted:
        profile["qq"] = data.get("qq") or ""
    profile["scope"] = scope
    return profile


__all__ = [
    "APPROVAL_TTL_SECONDS",
    "SCOPE_LABELS",
    "b64url_decode",
    "b64url_encode",
    "build_redirect",
    "cleanup",
    "client_credentials_match",
    "consume_code",
    "ensure_schema",
    "is_configured",
    "issue_code",
    "issue_token",
    "list_authorized_apps",
    "load_access_token",
    "parse_scope",
    "redirect_uri_allowed",
    "refresh_token",
    "registered_apps",
    "revoke",
    "revoke_app",
    "scope_string",
    "sign_approval",
    "user_profile",
    "verify_approval",
]
