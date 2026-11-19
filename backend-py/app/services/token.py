"""JWT 签发 / 验证 / 续签（逐行移植 Node src/utils/token.js）。

兼容红线：
- 声明字段：cid, username, rating, permissions, fsdLevel, iat, exp
  （安全审计 P0-3/P1-2 追加：typ="access"、jti、tokep；旧 token 无这些声明仍可解析）
- 算法：HS256，密钥来自时段轮换
- 续签：exp 过期但 ≤ JWT_REFRESH_GRACE_SECONDS 仍接受；>宽限则过期错误
- 滑动续签：剩余 < JWT_REFRESH_BEFORE_SECONDS 时重签并写 X-Renewed-Token（需查库取最新 claims）

安全（2026-11-07 审计）：
- **密钥域隔离（P0-3）**：PoW 令牌用 `HMAC(JWT_SECRET, "pow")` 独立派生密钥签发/校验，
  与 access token 的时段轮换密钥（`HMAC(JWT_SECRET, "jwt-period-<n>")`）完全不同域，
  因此 PoW 令牌**无法**当作 access token 使用（即使实现出现漏洞，签名也不匹配）。
- **类型强制（P0-3）**：access token 携带 `typ="access"`；`verify_token` 强制
  `typ=="access"`（可用 `JWT_ALLOW_LEGACY_TYP=1` 临时放行无 typ 的存量 token）且 `cid` 非空。
- **可吊销（P1-1/P1-2）**：`jti` 黑名单 + 用户级 `tokep`（见 `app/services/token_state.py`），
  登出/改密/封禁/降权后旧 token 立即失效；`/auth/refresh` 同样受吊销约束。
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any

import jwt as pyjwt

from app.config import settings
from app.services import token_state
from app.services.key_rotation import get_signing_key, get_verifying_keys

ACCESS_TYP = "access"
POW_TYP = "pow"
POW_KEY_DERIVATION_LABEL = b"pow"


class TokenError(Exception):
    expired = False


class TokenExpiredError(TokenError):
    expired = True


# ---------------------------------------------------------------- PoW 独立密钥域
def derive_pow_key() -> str:
    """PoW 令牌专用密钥：HMAC(JWT_SECRET, "pow")。

    与 `key_rotation.derive_period_key()` 的输出域完全不相交，因此两种令牌
    不可能互相冒充（P0-3 根因：此前 PoW 与 access token 共用同一签名密钥）。
    """
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        POW_KEY_DERIVATION_LABEL,
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------- access token
def sign_token(user: dict[str, Any], session_start: int | None = None) -> str:
    """签发 access token（含 typ/jti/tokep/sst，供类型校验、吊销与绝对会话上限使用）。"""
    iat = int(time.time())
    # sst = 首次登录时间；续签时原样继承，超过 JWT_MAX_SESSION_SECONDS 后拒绝续签。
    sst = int(session_start or iat)
    cid = str(user.get("cid") or "")
    payload: dict[str, Any] = {
        "cid": cid,
        "username": user.get("username"),
        "rating": user.get("rating") or 0,
        "permissions": user.get("permissions") or "",
        "fsdLevel": user.get("fsdLevel") or 0,
        "typ": ACCESS_TYP,
        "jti": secrets.token_hex(16),
        "iat": iat,
        "sst": sst,
        "exp": iat + settings.jwt_expires_seconds,
    }
    # epoch 快照：登录时把当前用户 epoch 写进 token；epoch 前进后本 token 立即失配。
    epoch = token_state.token_epoch(cid) if cid else None
    if epoch is not None:
        payload["tokep"] = int(epoch)
    return pyjwt.encode(payload, get_signing_key(), algorithm="HS256")


def _assert_access_claims(decoded: dict[str, Any]) -> None:
    """强制 typ/cid 并检查吊销状态。"""
    typ = decoded.get("typ")
    if typ is None:
        # 存量 token（2026-11-07 之前签发）没有 typ：默认拒绝；
        # 滚动发布期可临时置 JWT_ALLOW_LEGACY_TYP=1 放行（≤ 一个 JWT_EXPIRES 周期）。
        if not getattr(settings, "JWT_ALLOW_LEGACY_TYP", False):
            raise TokenError("Token 无效")
    elif str(typ) != ACCESS_TYP:
        # PoW 令牌（typ="pow"）在此被明确拒绝（P0-3）
        raise TokenError("Token 无效")

    cid = str(decoded.get("cid") or "").strip()
    if not cid:
        raise TokenError("Token 无效")

    jti = str(decoded.get("jti") or "").strip()
    if jti and token_state.is_jti_blacklisted(jti):
        raise TokenExpiredError("登录已过期，请重新登录")

    if token_state.is_epoch_stale(cid, decoded.get("tokep")):
        raise TokenExpiredError("登录已过期，请重新登录")


def verify_token(token: str) -> dict[str, Any]:
    """密钥环验证（兼容轮换）+ 类型/吊销校验，失败抛 TokenError / TokenExpiredError。"""
    last: Exception | None = None
    decoded: dict[str, Any] | None = None
    for key in get_verifying_keys():
        try:
            decoded = pyjwt.decode(token, key, algorithms=["HS256"])
            break
        except pyjwt.ExpiredSignatureError as exc:
            last = exc
        except pyjwt.InvalidTokenError as exc:
            last = exc
    if decoded is None:
        if isinstance(last, pyjwt.ExpiredSignatureError):
            raise TokenExpiredError("登录已过期") from last
        raise TokenError("Token 无效") from last

    _assert_access_claims(decoded)
    return decoded


def verify_token_for_refresh(token: str) -> dict[str, Any]:
    """续签专用：先验签名（忽略过期），再检查过期宽限。

    安全（P1-2）：同样强制 typ=="access"/cid 非空，并校验 jti 黑名单与 token_epoch，
    确保「登出/改密后旧 token 无法通过 refresh 无限续期」。
    """
    last: Exception | None = None
    decoded: dict[str, Any] | None = None
    for key in get_verifying_keys():
        try:
            decoded = pyjwt.decode(
                token, key, algorithms=["HS256"], options={"verify_exp": False}
            )
            break
        except pyjwt.InvalidTokenError as exc:
            last = exc
    if decoded is None:
        raise TokenError("Token 无效") from last

    _assert_access_claims(decoded)

    exp = decoded.get("exp")
    now = int(time.time())
    if exp and exp < now and (now - exp) > settings.JWT_REFRESH_GRACE_SECONDS:
        raise TokenExpiredError("Token 已过期")

    # 绝对会话上限：即使仍在宽限期/滑动续签窗口，也不能超过首次登录后的最长会话。
    session_start = int(decoded.get("sst") or decoded.get("iat") or 0)
    max_session = max(3600, int(settings.JWT_MAX_SESSION_SECONDS))
    if session_start and (now - session_start) > max_session:
        raise TokenExpiredError("会话已超过最长有效期，请重新登录")
    return decoded


def should_renew(decoded: dict[str, Any]) -> bool:
    exp = decoded.get("exp")
    if not exp:
        return False
    return (exp - int(time.time())) < settings.JWT_REFRESH_BEFORE_SECONDS


# ---------------------------------------------------------------- PoW token
def sign_pow_token(sid: str, ttl_seconds: int) -> str:
    """签发 PoW 通过令牌（独立密钥域，永不接受为 access token）。"""
    iat = int(time.time())
    payload = {
        "typ": POW_TYP,
        "sid": str(sid or ""),
        "iat": iat,
        "exp": iat + int(ttl_seconds),
    }
    return pyjwt.encode(payload, derive_pow_key(), algorithm="HS256")


def verify_pow_token(token: str) -> dict[str, Any]:
    """校验 PoW 令牌（仅 PoW 密钥域 + typ=="pow"）。失败抛 TokenError。"""
    try:
        decoded = pyjwt.decode(token, derive_pow_key(), algorithms=["HS256"])
    except pyjwt.InvalidTokenError as exc:
        raise TokenError("人机验证令牌无效") from exc
    if str(decoded.get("typ") or "") != POW_TYP:
        raise TokenError("人机验证令牌无效")
    return decoded


# ---------------------------------------------------------------- 可信设备令牌
TRUSTED_DEVICE_TYP = "trusted_device"
TRUSTED_DEVICE_KEY_LABEL = b"trusted-device"


def derive_trusted_device_key() -> str:
    """可信设备 Cookie 专用密钥域，避免与 access / PoW / challenge 互相冒充。"""
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        TRUSTED_DEVICE_KEY_LABEL,
        hashlib.sha256,
    ).hexdigest()


def sign_trusted_device(
    cid: str,
    fingerprint_hash: str,
    token_epoch: int | None,
    ttl_seconds: int,
) -> str:
    iat = int(time.time())
    payload: dict[str, Any] = {
        "typ": TRUSTED_DEVICE_TYP,
        "cid": str(cid),
        "fp": str(fingerprint_hash or ""),
        "iat": iat,
        "exp": iat + max(1, int(ttl_seconds)),
    }
    if token_epoch is not None:
        payload["tokep"] = int(token_epoch)
    return pyjwt.encode(payload, derive_trusted_device_key(), algorithm="HS256")


def verify_trusted_device(token: str) -> dict[str, Any]:
    try:
        decoded = pyjwt.decode(
            token, derive_trusted_device_key(), algorithms=["HS256"]
        )
    except pyjwt.InvalidTokenError as exc:
        raise TokenError("可信设备凭证无效或已过期") from exc
    if str(decoded.get("typ") or "") != TRUSTED_DEVICE_TYP:
        raise TokenError("可信设备凭证无效或已过期")
    if not str(decoded.get("cid") or "") or not str(decoded.get("fp") or ""):
        raise TokenError("可信设备凭证无效或已过期")
    return decoded


# ---------------------------------------------------------------- 登录挑战令牌
LOGIN_CHALLENGE_TYP = "login_challenge"
LOGIN_CHALLENGE_KEY_LABEL = b"login-challenge"


def derive_login_challenge_key() -> str:
    """登录挑战专用密钥域，避免与 access / PoW 令牌互相冒充。"""
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        LOGIN_CHALLENGE_KEY_LABEL,
        hashlib.sha256,
    ).hexdigest()


def sign_login_challenge(cid: str, ip: str, jti: str, ttl_seconds: int) -> str:
    iat = int(time.time())
    payload = {
        "typ": LOGIN_CHALLENGE_TYP,
        "cid": str(cid),
        "ip": str(ip or ""),
        "jti": str(jti),
        "iat": iat,
        "exp": iat + max(1, int(ttl_seconds)),
    }
    return pyjwt.encode(payload, derive_login_challenge_key(), algorithm="HS256")


def verify_login_challenge(token: str) -> dict[str, Any]:
    try:
        decoded = pyjwt.decode(token, derive_login_challenge_key(), algorithms=["HS256"])
    except pyjwt.InvalidTokenError as exc:
        raise TokenError("登录验证挑战无效或已过期") from exc
    if str(decoded.get("typ") or "") != LOGIN_CHALLENGE_TYP:
        raise TokenError("登录验证挑战无效或已过期")
    if not str(decoded.get("cid") or "") or not str(decoded.get("jti") or ""):
        raise TokenError("登录验证挑战无效或已过期")
    return decoded


__all__ = [
    "TokenError",
    "TokenExpiredError",
    "ACCESS_TYP",
    "POW_TYP",
    "LOGIN_CHALLENGE_TYP",
    "TRUSTED_DEVICE_TYP",
    "derive_pow_key",
    "derive_login_challenge_key",
    "derive_trusted_device_key",
    "sign_token",
    "verify_token",
    "verify_token_for_refresh",
    "should_renew",
    "sign_pow_token",
    "verify_pow_token",
    "sign_login_challenge",
    "verify_login_challenge",
    "sign_trusted_device",
    "verify_trusted_device",
]
