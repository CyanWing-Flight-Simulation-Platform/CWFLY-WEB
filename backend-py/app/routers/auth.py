"""/api/auth 路由（逐接口对齐 Node src/routes/auth.js）。

路径 / 方法 / 请求体 / 响应 JSON 结构 / 状态码 / 中文文案均与 Node 版一致。
灰度切流：nginx 先 `location /api/auth/ { proxy_pass http://python_backend; }`。
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.deps import AuthFailure, CurrentUser, get_current_user, get_verified_user
from app.routers.captcha import require_pow_token
from app.middleware.rate_limit import (
    Limit,
    login_limiter,
    rate_limiter,
    register_limiter,
    sensitive_limiter,
)
from app.services import users
from app.services.device_ban import is_device_banned
from app.services.login_challenge import (
    LoginChallengeUnavailable,
    consume_login_challenge,
    create_login_challenge,
)
from app.services.login_lock import check_login_lock, clear_login_failures, record_login_failure
from app.services.mailer import (
    VerificationUnavailable,
    fire_and_forget_thread,
    generate_code,
    send_notification,
    send_security_alert,
    send_verify_code,
    store_code,
    verify_code,
)
from app.services import audit_log, token_state
from app.services import webauthn_service as wa
from app.services.token import (
    TokenError,
    TokenExpiredError,
    sign_token,
    sign_trusted_device,
    verify_token_for_refresh,
    verify_trusted_device,
)
from app.utils.client import get_client_ip, get_device_fp, get_user_agent
from app.utils.json_compat import JSJSONResponse
from app.utils.session_cookie import (
    access_token_from_request,
    clear_auth_cookies,
    set_auth_cookies,
)
from app.utils.security import (
    hash_password,
    sha256_hex,
    validate_password,
    verify_password,
)

log = logging.getLogger("cwfly.auth")
router = APIRouter(prefix="/auth", tags=["auth"])

# 安全（P2-2）：CID 存在性探测专用限流（枚举缓解）。前端注册页依赖该接口
# 随机挑选可用 CID，故保留 `exists` 语义，但把枚举速率压到每 IP 每分钟 20 次。
CHECK_CID_LIMIT = Limit("auth-check-cid", 60, 20, "查询过于频繁，请稍后再试")
check_cid_limiter = rate_limiter(CHECK_CID_LIMIT)

# ---------- 响应工具（与 Node res.json / res.status().json 等价） ----------
def ok(data: Any = None, **extra: Any) -> JSJSONResponse:
    body: dict[str, Any] = {"success": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return JSJSONResponse(body)


def fail(status_code: int, message: str, **extra: Any) -> JSJSONResponse:
    body: dict[str, Any] = {"success": False, "message": message}
    body.update(extra)
    return JSJSONResponse(body, status_code=status_code)


TRUSTED_DEVICE_COOKIE = "cw_trusted_device"


async def _clear_login_limiter(ip: str | None) -> None:
    """登录成功后清掉该 IP 的登录限流计数，避免正常用户被自己的重试次数拖住。"""
    if not ip:
        return
    try:
        from app.services import rate_limit_store

        await rate_limit_store.reset_key(f"auth-login:{ip}")
    except Exception:  # noqa: BLE001 - 限流清理失败不影响登录
        pass


def auth_ok(request: Request, token: str, data: Any = None, **extra: Any) -> JSJSONResponse:
    """成功响应 + 写入 HttpOnly 会话 Cookie。"""
    response = ok(data, **extra)
    set_auth_cookies(response, request, token)
    return response


def _device_fp_hash(request: Request) -> str:
    fp = get_device_fp(request)
    if not fp:
        return ""
    return hashlib.sha256(fp.encode("utf-8")).hexdigest()


def _cookie_secure(request: Request) -> bool:
    forwarded = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    return request.url.scheme == "https" or forwarded == "https"


def _trusted_device_matches(request: Request, user: dict[str, Any]) -> bool:
    """校验 HttpOnly 可信设备 Cookie：绑定 CID + 设备指纹 + token epoch。"""
    token = request.cookies.get(TRUSTED_DEVICE_COOKIE) or ""
    fp_hash = _device_fp_hash(request)
    if not token or not fp_hash:
        return False
    try:
        claims = verify_trusted_device(token)
    except TokenError:
        return False
    cid = str(user.get("cid") or "")
    if str(claims.get("cid") or "") != cid:
        return False
    if str(claims.get("fp") or "") != fp_hash:
        return False
    return not token_state.is_epoch_stale(cid, claims.get("tokep"))


def _issue_trusted_device(response: JSJSONResponse, request: Request, user: dict[str, Any]) -> None:
    """登录成功后签发 30 天可信设备 Cookie；无设备指纹时不签发。"""
    fp_hash = _device_fp_hash(request)
    if not fp_hash:
        return
    cid = str(user.get("cid") or "")
    ttl = max(1, int(settings.TRUSTED_DEVICE_TTL_SECONDS))
    token = sign_trusted_device(cid, fp_hash, token_state.token_epoch(cid), ttl)
    response.set_cookie(
        key=TRUSTED_DEVICE_COOKIE,
        value=token,
        max_age=ttl,
        httponly=True,
        secure=_cookie_secure(request),
        samesite="lax",
        path="/",
    )


def user_payload(user: dict[str, Any]) -> dict[str, Any]:
    """登录/注册/me/refresh 返回的 user 对象（字段与顺序对齐 Node）。"""
    return {
        "cid": user.get("cid"),
        "username": user.get("username"),
        "rating": user.get("rating") or 0,
        "permissions": user.get("permissions") or "",
        "fsdLevel": user.get("fsdLevel") or 0,
        "createdAt": user.get("createdAt"),
    }


# ============================ 基础检查 ============================
@router.get("/check-admin")
async def check_admin(db: AsyncSession = Depends(get_db)) -> Any:
    try:
        count = await users.count_admins(db)
        return JSJSONResponse({"success": True, "exists": count > 0})
    except Exception:
        return JSJSONResponse({"success": True, "exists": False})


@router.get("/check-cid", dependencies=[Depends(check_cid_limiter)])
async def check_cid(cid: Optional[str] = None, db: AsyncSession = Depends(get_db)) -> Any:
    """CID 是否可用（注册页随机挑选 CID 用）。

    安全（P2-2 枚举缓解）：
    - 只接受 4 位数字（畸形入参不消耗真实查询，也不泄露存在性）；
    - 独立限流（20 次/分钟/IP）把批量枚举压到不可用水平；
    - 真正的高价值枚举通道已关闭：`/auth/register` 的 CID/邮箱冲突检查
      移到「邮箱验证码校验之后」，没有真实验证码无法探测存在性。
    """
    if not cid:
        return fail(400, "缺少 CID")
    cid_text = str(cid).strip()
    if len(cid_text) != 4 or not cid_text.isdigit():
        return fail(400, "CID 必须为4位数字")
    try:
        user = await users.find_user_public(db, cid_text)
        return JSJSONResponse({"success": True, "exists": user is not None})
    except Exception:
        return fail(500, "查询失败")


# ============================ 注册 ============================
@router.post(
    "/register",
    dependencies=[Depends(register_limiter), Depends(require_pow_token)],
)
async def register(request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    try:
        body = await request.json()
    except Exception:
        body = {}
    cid = body.get("cid")
    username = body.get("username")
    password = body.get("password")
    email = body.get("email")
    email_code = body.get("emailCode")

    register_fp = get_device_fp(request)
    register_ip = get_client_ip(request)

    # 设备指纹黑名单
    if register_fp and await is_device_banned(register_fp):
        return fail(403, "该设备已被封禁，无法注册新账号", code="DEVICE_BANNED")
    # 同一设备/网络只能注册一次（数据库持久化）
    if register_fp:
        if await users.find_first_by_column(db, "registerFp", register_fp):
            return fail(429, "该设备已注册过账号，请更换设备或联系管理员")
    if register_ip:
        if await users.find_first_by_column(db, "registerIp", register_ip):
            return fail(429, "该设备已注册过账号，请更换设备或联系管理员")

    if not cid or not username or not password or not email or not email_code:
        return fail(400, "请填写完整信息（邮箱及验证码必填）")

    pw_err = validate_password(password)
    if pw_err:
        return fail(400, pw_err)

    if len(str(cid)) != 4 or not str(cid).isdigit():
        return fail(400, "CID 必须为4位数字")
    cid = str(cid)

    # 安全（P2-2 枚举）：先校验邮箱验证码，再做 CID/邮箱冲突检查。
    # 顺序调整后，攻击者必须先拥有一个真实可收信的邮箱（且通过 PoW/限流/冷却），
    # 才能拿到「该 CID / 该邮箱已被注册」这类存在性信号，批量枚举成本大幅提高。
    try:
        code_ok = await verify_code(email, email_code, "register")
    except VerificationUnavailable:
        return fail(503, "验证码服务暂不可用，请稍后重试")
    if not code_ok:
        return fail(400, "邮箱验证码错误或已过期")

    if await users.find_user_public(db, cid):
        return fail(409, "该 CID 已被注册")
    if await users.find_user_by_email(db, email):
        return fail(409, "该邮箱已被注册")

    register_user_agent = get_user_agent(request)
    created = await users.create_user(
        db,
        {
            "cid": cid,
            "username": username,
            "password": hash_password(password),
            "rating": 0,
            "permissions": "",
            "fsdLevel": 0,
            "email": email or "",
            "fsdPasswordHash": sha256_hex(password),
            "registerIp": register_ip,
            "registerFp": register_fp,
            "registerUserAgent": register_user_agent,
        },
    )

    # 证据链：注册即写登录日志（失败不阻塞注册）
    try:
        await users.insert_login_log(
            db,
            {
                "userId": cid,
                "ip": register_ip,
                "userAgent": register_user_agent,
                "deviceFp": register_fp,
                "success": True,
                "type": "register",
            },
        )
    except Exception as exc:
        log.error("[auth.py] 注册日志写入失败: %s", exc)

    token = sign_token(created)

    # 欢迎邮件（不阻塞响应）
    if created.get("email"):
        fire_and_forget(
            send_notification(
                created["email"],
                {
                    "subject": "欢迎加入 CW 模拟飞行",
                    "intro": f"欢迎您，{created['username']}！",
                    "body": "您的账号已成功注册。您可以使用 CID 登录平台，开始您的模拟飞行之旅。",
                    "action": "开始体验",
                    "actionUrl": f"{_frontend_url()}/dashboard",
                },
            )
        )

    return auth_ok(request, token, {"token": token, "user": user_payload(created)})
    # Node 版异常兜底见下方包装器


# ============================ 登录 ============================
@router.post(
    "/login",
    dependencies=[Depends(login_limiter), Depends(require_pow_token)],
)
async def login(request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    try:
        body = await request.json()
    except Exception:
        body = {}
    cid = body.get("cid")
    password = body.get("password") or ""
    ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    device_fp = get_device_fp(request)

    if device_fp and await is_device_banned(device_fp):
        try:
            await users.insert_login_log(
                db,
                {
                    "userId": cid or "unknown",
                    "ip": ip,
                    "userAgent": user_agent,
                    "deviceFp": device_fp,
                    "success": False,
                    "type": "login",
                    "failReason": "device_banned",
                },
            )
        except Exception:
            pass
        await audit_log.write(
            db,
            "login_banned_device",
            "登录被拒绝：设备指纹已被封禁",
            str(cid or "unknown"),
            target_type="device",
        )
        return fail(403, "该设备已被封禁，请联系管理员", code="DEVICE_BANNED")

    # 安全（P1-14 / P2-3）：先取账号（只为拿 rating），锁定判定按 (cid, ip) 组合，
    # 且 rating >= 11 的高等级账号只告警不锁定 —— 避免攻击者用错密码把管理员锁死。
    user = await users.find_user_with_credentials(db, cid)
    lock_msg = await check_login_lock(
        db, cid, ip, int((user or {}).get("rating") or 0)
    )
    if lock_msg:
        return fail(429, lock_msg)

    if not user:
        await record_login_failure(db, cid, ip)
        await _safe_login_log(db, cid or "unknown", ip, user_agent, device_fp, False, "notfound")
        await audit_log.write(
            db, "login_unknown_cid", "登录失败：CID 不存在", str(cid or "")
        )
        return fail(401, "CID 或密码错误")

    if not verify_password(password, user.get("password")):
        await record_login_failure(db, cid, ip)
        await _safe_login_log(db, cid, ip, user_agent, device_fp, False, "password")
        await audit_log.write(
            db, "login_wrong_password", "登录失败：密码错误", str(cid or "")
        )
        return fail(401, "CID 或密码错误")

    await clear_login_failures(db, cid)

    # 同步 FSD 密码哈希（兼容老用户）
    if not user.get("fsdPasswordHash") or len(str(user.get("fsdPasswordHash"))) != 64:
        fsd_hash = sha256_hex(password)
        try:
            await users.update_user(db, cid, {"fsdPasswordHash": fsd_hash})
        except Exception:
            pass

    # 可信 IP / 可信设备校验：两者任一命中即跳过邮箱二次验证
    trusted = await users.trusted_ips(db, user.get("registerIp"), user["cid"])
    device_trusted = _trusted_device_matches(request, user)
    if ip not in trusted and not device_trusted:
        # 未绑定邮箱的账号无法走邮箱二次验证：允许登录，但写高风险审计日志。
        # 不能直接返回 needVerify，否则这类账号会因无法收码而永久锁死。
        if not user.get("email"):
            await _safe_login_log(
                db, cid, ip, user_agent, device_fp, True, "new_ip_no_email_high_risk"
            )
            await audit_log.write(
                db,
                "new_ip_no_email",
                "新 IP 登录且账号未绑定邮箱，已按高风险放行",
                str(cid or ""),
                target_type="user",
                target_id=cid,
            )
            log.warning(
                "[auth] 新 IP 且未绑定邮箱，按高风险放行: cid=%s ip=%s fp=%s",
                cid,
                ip,
                device_fp or "-",
            )
            token = sign_token(user)
            response = ok(
                {"token": token, "user": user_payload(user)},
                securityWarning="检测到新 IP 登录，但账号未绑定邮箱；请尽快绑定邮箱以启用二次验证。",
            )
            set_auth_cookies(response, request, token)
            _issue_trusted_device(response, request, user)
            return response

        try:
            challenge = await create_login_challenge(db, user["cid"], ip, device_fp)
        except LoginChallengeUnavailable:
            return fail(503, "登录安全验证服务暂不可用，请稍后重试")

        await _safe_login_log(
            db, cid, ip, user_agent, device_fp, False, "new_ip_verification_required"
        )
        return JSJSONResponse(
            {
                "success": True,
                "needVerify": True,
                "data": {
                    "email": user.get("email") or "",
                    "message": "检测到新设备/IP 登录，请通过邮箱验证码确认身份",
                    "loginChallenge": challenge,
                },
            }
        )

    await _clear_login_limiter(ip)
    await _safe_login_log(db, cid, ip, user_agent, device_fp, True, "")
    await audit_log.write(
        db,
        "login_success",
        "登录成功",
        str(cid or ""),
        target_type="user",
        target_id=cid,
    )
    token = sign_token(user)
    response = ok({"token": token, "user": user_payload(user)})
    set_auth_cookies(response, request, token)
    _issue_trusted_device(response, request, user)
    return response


# ============================ 登录二次验证（新 IP / 新设备） ============================
@router.post(
    "/login-verify",
    dependencies=[Depends(login_limiter), Depends(require_pow_token)],
)
async def login_verify(request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    try:
        body = await request.json()
    except Exception:
        body = {}
    cid = body.get("cid")
    email_code = body.get("emailCode")
    login_challenge_token = body.get("loginChallenge")
    ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    device_fp = get_device_fp(request)

    if not cid or not email_code or not login_challenge_token:
        return fail(400, "登录验证已失效，请重新登录")

    user = await users.find_user_with_credentials(db, str(cid))
    if not user:
        return fail(401, "账号不存在")
    if not user.get("email"):
        return fail(400, "该账号未绑定邮箱，请联系管理员")

    lock_msg = await check_login_lock(
        db, user["cid"], ip, int(user.get("rating") or 0)
    )
    if lock_msg:
        return fail(429, lock_msg)
    if device_fp and await is_device_banned(device_fp):
        return fail(403, "设备已被封禁", code="DEVICE_BANNED")

    try:
        challenge_ok = await consume_login_challenge(
            db, str(login_challenge_token), str(cid), ip
        )
    except LoginChallengeUnavailable:
        return fail(503, "登录安全验证服务暂不可用，请稍后重试")
    if not challenge_ok:
        return fail(400, "登录验证已失效，请重新登录")

    try:
        code_ok = await verify_code(user["email"], email_code, "login")
    except VerificationUnavailable:
        return fail(503, "验证码服务暂不可用，请稍后重试")
    if not code_ok:
        await record_login_failure(db, user["cid"], ip)
        return fail(400, "邮箱验证码错误或已过期")

    await _safe_login_log(db, user["cid"], ip, user_agent, device_fp, True, "")
    token = sign_token(user)
    response = ok({"token": token, "user": user_payload(user)})
    set_auth_cookies(response, request, token)
    _issue_trusted_device(response, request, user)
    return response


# ============================ 标准 WebAuthn / Passkey ============================
# 生物识别/PIN 只发生在用户本地设备；服务端只保存公钥、credential id 和签名计数器。


async def _passkey_password_ok(db: AsyncSession, cid: str, password: str) -> bool:
    creds = await users.find_user_with_credentials(db, cid)
    return bool(creds and verify_password(str(password or ""), creds.get("password")))


@router.get("/passkey/credentials")
async def passkey_credentials(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_verified_user),
) -> Any:
    return ok({"credentials": await wa.list_credentials(db, current.cid)})


@router.post("/passkey/register/options", dependencies=[Depends(sensitive_limiter)])
async def passkey_register_options(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_verified_user),
) -> Any:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    if not await _passkey_password_ok(db, current.cid, str((body or {}).get("password") or "")):
        return fail(401, "当前密码错误")
    user = await users.find_user_with_credentials(db, current.cid) or {}
    options = await wa.registration_options(db, current.cid, user.get("username") or current.cid)
    return ok({"options": options})


@router.post("/passkey/register/verify", dependencies=[Depends(sensitive_limiter)])
async def passkey_register_verify(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_verified_user),
) -> Any:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    body = body or {}
    credential = body.get("credential")
    if not isinstance(credential, dict):
        return fail(400, "缺少 Passkey 凭据")
    # transports 决定登录时浏览器怎么找这把钥匙：手机上的凭据需要 "hybrid"，
    # 本地 Windows Hello 需要 "internal"。前端可能没带，这里做一次兜底推断。
    transports = body.get("transports")
    if not transports:
        transports = (credential.get("response") or {}).get("transports") or []
    if not transports:
        transports = ["internal", "hybrid"]
    try:
        saved = await wa.verification_response(
            db,
            current.cid,
            credential,
            str(body.get("name") or "Passkey"),
            transports,
        )
    except ValueError as exc:
        return fail(400, str(exc))
    await audit_log.write(
        db, "passkey_registered", "已绑定 Passkey", str(current.cid),
        target_type="user", target_id=current.cid,
    )
    return ok({"credential": saved, "credentials": await wa.list_credentials(db, current.cid)})


@router.delete("/passkey/credentials/{credential_row_id}")
async def passkey_delete_credential(
    credential_row_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_verified_user),
) -> Any:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    if not await _passkey_password_ok(db, current.cid, str((body or {}).get("password") or "")):
        return fail(401, "当前密码错误")
    if not await wa.delete_credential(db, current.cid, credential_row_id):
        return fail(404, "Passkey 不存在")
    await audit_log.write(
        db, "passkey_removed", "已移除 Passkey", str(current.cid),
        target_type="user", target_id=current.cid,
    )
    return ok({"credentials": await wa.list_credentials(db, current.cid)})


@router.post("/passkey/login/options")
async def passkey_login_options(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    cid = str((body or {}).get("cid") or "").strip() or None
    # 没有 CID 就无法限定 allowCredentials，浏览器在找不到凭据时会弹「创建通行密钥」，
    # 因此这里前置拦截，避免把登录变成绑定。
    if not cid:
        return fail(400, "请先输入 CID，再使用 Passkey 登录")
    if not await wa.has_credentials(db, cid):
        return fail(400, "该账号还没有绑定 Passkey，请先用密码登录后在个人中心绑定")
    options = await wa.authentication_options(db, cid)
    return ok({"options": options, "challenge": options.get("challenge")})


@router.post("/passkey/login/verify", dependencies=[Depends(login_limiter)])
async def passkey_login_verify(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    body = body or {}
    cid = str(body.get("cid") or "").strip() or None
    challenge_token = str(body.get("challenge") or "").strip() or None
    credential = body.get("credential")
    if not isinstance(credential, dict) or not challenge_token:
        return fail(400, "Passkey 登录参数不完整")
    ip = get_client_ip(request)
    device_fp = get_device_fp(request)
    if device_fp and await is_device_banned(device_fp):
        return fail(403, "该设备已被封禁，请联系管理员", code="DEVICE_BANNED")
    try:
        actual_cid = await wa.verify_login(db, cid, credential, challenge_token)
    except ValueError as exc:
        await record_login_failure(db, cid or "unknown", ip)
        await audit_log.write(
            db, "passkey_login_failed", "Passkey 登录失败", cid or "unknown",
            target_type="user", target_id=cid or "",
        )
        return fail(401, str(exc))
    user = await users.find_user_with_credentials(db, actual_cid)
    if not user:
        return fail(401, "Passkey 登录失败")
    lock_msg = await check_login_lock(db, actual_cid, ip, int(user.get("rating") or 0))
    if lock_msg:
        return fail(429, lock_msg)
    await clear_login_failures(db, actual_cid)
    await _clear_login_limiter(ip)
    await _safe_login_log(db, actual_cid, ip, get_user_agent(request), device_fp, True, "passkey")
    await audit_log.write(
        db, "passkey_login", "Passkey 登录成功", actual_cid,
        target_type="user", target_id=actual_cid,
    )
    token = sign_token(user)
    return auth_ok(request, token, {"token": token, "user": user_payload(user)})


# ============================ 会话续签 ============================
@router.post("/refresh")
async def refresh(request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    header = request.headers.get("authorization") or ""
    cookie_token = access_token_from_request(request)
    token = cookie_token or (header[len("Bearer ") :] if header.startswith("Bearer ") else "")
    if not token:
        return fail(401, "请先登录")
    try:
        decoded = verify_token_for_refresh(token)
        fresh = await users.find_user_public(db, str(decoded.get("cid") or ""))
        if not fresh:
            return fail(401, "账号不存在或已注销")
        new_token = sign_token(
            fresh,
            session_start=decoded.get("sst") or decoded.get("iat"),
        )
        response = ok({
            "token": new_token,
            "user": user_payload(fresh),
        })
        set_auth_cookies(response, request, new_token)
        return response
    except TokenExpiredError:
        log.error("[auth.py] refresh 失败: token expired")
        return fail(401, "登录已过期，请重新登录")
    except TokenError as exc:
        log.error("[auth.py] refresh 失败: %s", exc)
        return fail(401, "登录无效，请重新登录")


# ============================ 退出登录（令牌吊销） ============================
@router.post("/logout")
async def logout(request: Request) -> Any:
    """把当前 token 的 `jti` 写入黑名单（TTL = 剩余有效期），实现服务端登出。

    安全（P1-2 / P1-16）：
    - 前端登出只清 localStorage 时，token 仍在有效期内可用；本接口让 token 真正失效；
    - 旧 token（无 `jti`）无法单独吊销 → 前移该用户 `token_epoch`，
      使其所有会话下线（宁可多下线，不留可用凭证）；
    - 幂等：无 token / 已失效 token 也返回 success，避免前端登出流程报错。
    """
    header = request.headers.get("authorization") or ""
    token = access_token_from_request(request)
    if not token and header.startswith("Bearer "):
        token = header[len("Bearer ") :].strip()
    revoked = False
    mode = "noop"
    if token:
        try:
            # 允许「已过期但签名有效」的 token 走登出，便于清理宽限期内的旧凭证
            decoded = verify_token_for_refresh(token)
        except TokenError:
            decoded = None
        if decoded:
            cid = str(decoded.get("cid") or "").strip()
            jti = str(decoded.get("jti") or "").strip()
            exp = int(decoded.get("exp") or 0)
            ttl = max(exp - int(time.time()), 0)
            if jti:
                mode = "jti"
                revoked = token_state.add_blacklisted_jti(jti, ttl)
            elif cid:
                mode = "epoch"
                token_state.bump_token_epoch(cid)
                revoked = True
            if cid:
                log.info("[auth.py] 用户登出: cid=%s mode=%s revoked=%s", cid, mode, revoked)
    # 仅结束当前登录会话；可信设备 Cookie 保留，避免同一设备每次登录都重新收码。
    # 修改密码/封禁会前移 token epoch，使旧的可信设备 Cookie 自动失效。
    response = JSJSONResponse(
        {"success": True, "message": "已退出登录", "data": {"mode": mode, "revoked": revoked}}
    )
    clear_auth_cookies(response)
    return response


# ============================ 修改密码 ============================
@router.put("/password", dependencies=[Depends(sensitive_limiter)])
async def change_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> Any:
    try:
        body = await request.json()
    except Exception:
        body = {}
    old_password = body.get("oldPassword") or ""
    new_password = body.get("newPassword") or ""

    user = await users.find_user_public(db, current.cid)
    if not user:
        return fail(404, "用户不存在")

    creds = await users.find_user_with_credentials(db, current.cid)
    if not creds or not verify_password(old_password, creds.get("password")):
        return fail(401, "原密码错误")

    # 安全（P2-1）：改密同样要过密码策略（历史上只有注册/重置走了校验）
    pw_err = validate_password(new_password)
    if pw_err:
        return fail(400, pw_err)

    await users.update_user(
        db,
        current.cid,
        {"password": hash_password(new_password), "fsdPasswordHash": sha256_hex(new_password)},
    )
    # 安全（P1-2）：改密后前移 token_epoch，使所有旧 token（含本次调用者）立即失效，
    # 并要求用户用新密码重新登录（被盗 token 无法继续使用/续期）。
    token_state.bump_token_epoch(current.cid)
    # 同时下发一枚新 token：前端采用 data.token 则可平滑继续本次会话。
    fresh_token = sign_token(
        {
            "cid": user.get("cid") or current.cid,
            "username": user.get("username") or "",
            "rating": user.get("rating") or 0,
            "permissions": user.get("permissions") or "",
            "fsdLevel": user.get("fsdLevel") or 0,
        }
    )

    if user.get("email"):
        fire_and_forget(
            send_security_alert(
                user["email"],
                {
                    "action": "密码修改",
                    "detail": "您的登录密码已被成功修改。",
                    "time": _now_cn_string(),
                    "ip": get_client_ip(request),
                },
            )
        )
    response = JSJSONResponse(
        {
            "success": True,
            "message": "密码已更新",
            "data": {"token": fresh_token},
        },
        headers={"X-Renewed-Token": fresh_token},
    )
    set_auth_cookies(response, request, fresh_token)
    return response


# ============================ 当前用户 ============================
@router.get("/me")
async def me(db: AsyncSession = Depends(get_db), current: CurrentUser = Depends(get_current_user)) -> Any:
    try:
        user = await users.find_user_public(db, current.cid)
        if not user:
            return fail(404, "用户不存在")
        return ok(user_payload(user))
    except Exception:
        return fail(401, "登录已过期")


# ============================ 忘记密码 / 重置密码 ============================
@router.post(
    "/forgot-password",
    dependencies=[Depends(sensitive_limiter), Depends(require_pow_token)],
)
async def forgot_password(request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    try:
        body = await request.json()
    except Exception:
        body = {}
    email = body.get("email")
    if not email:
        return fail(400, "请输入邮箱")

    user = await users.find_user_by_email(db, email)
    if user:
        code = generate_code()
        # 先落库保证验证码立即可用，SMTP 发信后台执行（不阻塞响应）
        try:
            await store_code(email, code, "reset")
        except VerificationUnavailable:
            return fail(503, "验证码服务暂不可用，请稍后重试")

        async def _mail_job() -> None:
            try:
                await send_verify_code(email, code, "找回密码")
            except Exception as exc:  # noqa: BLE001
                log.error("[forgot-password] 邮件发送失败: %s", exc)

        fire_and_forget_thread(_mail_job)

    return JSJSONResponse({"success": True, "message": "如果该邮箱已注册，验证码已发送到邮箱"})


@router.post(
    "/reset-password",
    dependencies=[Depends(sensitive_limiter), Depends(require_pow_token)],
)
async def reset_password(request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    try:
        body = await request.json()
    except Exception:
        body = {}
    email = body.get("email")
    code = body.get("code")
    password = body.get("password")
    if not email or not code or not password:
        return fail(400, "请填写完整")

    try:
        code_ok = await verify_code(email, code, "reset")
    except VerificationUnavailable:
        return fail(503, "验证码服务暂不可用，请稍后重试")
    if not code_ok:
        return fail(400, "验证码错误或已过期")

    user = await users.find_user_by_email(db, email)
    if not user:
        return fail(400, "验证码错误或已过期")

    pw_err = validate_password(password)
    if pw_err:
        return fail(400, pw_err)

    await users.update_user(
        db,
        user["cid"],
        {"password": hash_password(password), "fsdPasswordHash": sha256_hex(password)},
    )
    # 安全（P1-2）：忘记密码重置后同样吊销该用户全部旧会话
    token_state.bump_token_epoch(user["cid"])
    return JSJSONResponse({"success": True, "message": "密码已重置"})


# ============================ 内部工具 ============================
async def _safe_login_log(
    db: AsyncSession,
    user_id: str,
    ip: str,
    user_agent: str,
    device_fp: str,
    success: bool,
    fail_reason: str,
) -> None:
    try:
        await users.insert_login_log(
            db,
            {
                "userId": user_id,
                "ip": ip,
                "userAgent": user_agent,
                "deviceFp": device_fp,
                "success": success,
                "type": "login",
                "failReason": fail_reason,
            },
        )
    except Exception:
        pass


def _frontend_url() -> str:
    from app.config import settings

    return settings.FRONTEND_URL or "http://localhost:5173"


def _now_cn_string() -> str:
    """对齐 Node `new Date().toLocaleString('zh-CN')`（月/日不补零）。"""
    from app.services.zh_time_service import zh_now

    return zh_now()


__all__ = ["router", "AuthFailure", "Response"]
