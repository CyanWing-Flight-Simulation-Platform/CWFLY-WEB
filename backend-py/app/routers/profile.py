"""/api/profile 路由（逐接口对齐 Node src/routes/profile.js）。

端点：
- GET    /             个人信息
- PUT    /             修改密码（必须校验原密码）
- POST   /avatar       上传头像（5MB，png/jpg/jpeg/webp/gif）
- PUT    /info         更新 qq / avatar（邮箱改动走验证流程）
- POST   /bg-image     上传背景图（10MB，每日 5 次）
- DELETE /bg-image     恢复默认背景
- POST   /send-verify  发送邮箱验证码
- POST   /verify-email 校验邮箱验证码并绑定
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.services import mailer
from app.services import profile_store as ps
from app.services import profile_uploads as pu
from app.services import token_state
from app.services.token import sign_token
from app.services.zh_time_service import zh_locale
from app.utils.json_compat import JSJSONResponse
from app.utils.security import hash_password, sha256_hex, validate_password, verify_password

log = logging.getLogger("cwfly.profile")
router = APIRouter(prefix="/profile", tags=["profile"])

MESSAGE_OPERATION_FAILED = "操作失败"

# 安全（P2-9）：头像只允许站内上传目录前缀（或服务端生成的 QQ 头像），
# 防止把任意 URL 写进数据库后被前端当链接/HTML 渲染。
ALLOWED_AVATAR_PREFIXES = ("/uploads/avatars/",)
ALLOWED_AVATAR_HOSTS = ("q1.qlogo.cn", "q.qlogo.cn")


def is_allowed_avatar(value: Any) -> bool:
    """头像字段白名单：空串（恢复默认）/ `/uploads/avatars/...` / QQ 头像 CDN。"""
    if not isinstance(value, str):
        return False
    text = value.strip()
    if text == "":
        return True
    if text.startswith(ALLOWED_AVATAR_PREFIXES):
        # 目录内文件名不含该前缀时拒绝（防 `/uploads/avatars/../../x`）
        rest = text[len("/uploads/avatars/") :]
        return rest != "" and "/" not in rest and "\\" not in rest and ".." not in rest
    if text.startswith("https://"):
        from urllib.parse import urlparse

        host = (urlparse(text).hostname or "").lower()
        return host in ALLOWED_AVATAR_HOSTS
    return False


def _ok(data: Any = None, message: str | None = None) -> JSJSONResponse:
    body: dict[str, Any] = {"success": True}
    if data is not None:
        body["data"] = data
    if message is not None:
        body["message"] = message
    return JSJSONResponse(body)


def _fail(status_code: int, message: str) -> JSJSONResponse:
    return JSJSONResponse({"success": False, "message": message}, status_code=status_code)


def _upload_failure() -> JSJSONResponse:
    """multer 抛错（白名单外扩展名 / 超过大小上限）→ Node 全局错误处理 500。"""
    return _fail(500, "服务器内部错误")


def _js_string(value: Any) -> str:
    """等价 JS `String(value)`（用于模板字符串插值）。"""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _qq_avatar(qq: Any) -> str:
    """头像只能来自绑定的 QQ 号；未绑定 QQ 时返回空字符串（前端显示默认头像）。"""
    text = str(qq or "").strip()
    if not text:
        return ""
    return f"https://q1.qlogo.cn/g?b=qq&nk={text}&s=100"


# FlightLog 没有独立 role 字段；管制呼号使用 ICAO_设施后缀（如 ZBAA_TWR / ZSHA_CT）。
_CONTROLLER_CALLSIGN_RE = re.compile(
    r"_(DEL|GND|TWR|APP|CTR|FSS|OBS|AP|TW|CT|AT|OB)$",
    re.IGNORECASE,
)


async def _online_hours(db: AsyncSession, cid: str) -> dict[str, float]:
    """从 FlightLog 的上下线时间计算真实在线时长，不依赖 FlightPlan.flightTime。

    过滤规则：
    - offlineAt 为空（仍在线/异常断线未补）不计；
    - offlineAt <= createdAt（负数/零时长）不计；
    - 管制呼号按设施后缀归入管制时长，其余归入连飞时长。
    """
    flight_seconds = 0
    controller_seconds = 0
    try:
        rows = (
            await db.execute(
                text(
                    "SELECT callsign, createdAt, offlineAt FROM `FlightLog` "
                    "WHERE userId = :cid AND offlineAt IS NOT NULL "
                    "AND offlineAt > createdAt"
                ),
                {"cid": str(cid)},
            )
        ).all()
        for row in rows:
            item = row._mapping
            callsign = str(item.get("callsign") or "").strip().upper()
            created = item.get("createdAt")
            offline = item.get("offlineAt")
            if not created or not offline:
                continue
            seconds = (offline - created).total_seconds()
            if seconds <= 0:
                continue
            if _CONTROLLER_CALLSIGN_RE.search(callsign):
                controller_seconds += seconds
            else:
                flight_seconds += seconds
    except Exception as exc:  # noqa: BLE001 - 旧库可能尚未同步 offlineAt 列
        log.warning("[profile.py] FlightLog 在线时长查询失败: %s", exc)
    # TODO(兼容旧库): 若线上 FlightLog 尚未迁移 offlineAt，需要先执行 FSD 的
    # FlightLog 迁移；此处不伪造数据，查询失败时返回 0.00，避免接口 500。
    return {
        "totalFlightHours": round(flight_seconds / 3600, 2),
        "totalControllerHours": round(controller_seconds / 3600, 2),
    }


def _zh_now() -> str:
    """`new Date().toLocaleString('zh-CN')`（月/日不补零，与 Node ICU 输出一致）。"""
    return zh_locale(dt.datetime.now())


async def _read_json(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


# ==================== GET / 个人信息 ====================
@router.get("")
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        user = await ps.get_profile(db, current.cid)
        if not user:
            return _fail(404, "用户不存在")
        hours = await _online_hours(db, current.cid)
        return _ok(
            {
                "cid": user.get("cid"),
                "username": user.get("username"),
                "rating": int(user.get("rating") or 0),
                "permissions": user.get("permissions") or "",
                "fsdLevel": int(user.get("fsdLevel") or 0),
                "email": user.get("email"),
                "qq": user.get("qq"),
                "avatar": _qq_avatar(user.get("qq")),
                "bgImage": user.get("bgImage") or "",
                "createdAt": user.get("createdAt"),
                "totalFlightHours": hours["totalFlightHours"],
                "totalControllerHours": hours["totalControllerHours"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        log.error("[profile.py] %s", exc)
        return _fail(500, MESSAGE_OPERATION_FAILED)


# ==================== PUT / 修改密码 ====================
@router.put("")
async def update_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        body = await _read_json(request)
        old_password = body.get("oldPassword")
        new_password = body.get("newPassword")

        user = await ps.get_profile(db, current.cid)
        if not user:
            return _fail(404, "用户不存在")

        # 安全（2026-10-25 审计 P1-1）：改密码必须校验原密码
        if new_password:
            if not old_password:
                return _fail(400, "修改密码需要提供当前密码")
            if not isinstance(old_password, str) or not isinstance(new_password, str):
                # Node: bcrypt.compare(number, hash) 抛错 → catch → 500
                return _fail(500, MESSAGE_OPERATION_FAILED)
            stored_hash = await ps.get_password_hash(db, current.cid)
            if stored_hash is None:
                # Node: findUserWithCredentials(cid).password → null 上取属性 → 抛错 → 500
                return _fail(500, MESSAGE_OPERATION_FAILED)
            if not verify_password(old_password, stored_hash):
                return _fail(400, "当前密码错误")

            # 安全（P2-1）：改密同样要过密码策略（历史上只有注册/重置走了校验）
            pw_err = validate_password(new_password)
            if pw_err:
                return _fail(400, pw_err)

            await ps.update_password(
                db,
                current.cid,
                hash_password(new_password),
                sha256_hex(new_password),
            )
            # 安全（P1-2）：改密后前移 token_epoch → 该用户全部旧 token 立即失效
            # （被盗 token 无法继续使用，也无法通过 /auth/refresh 续期）。
            token_state.bump_token_epoch(current.cid)
            # 同时签发一枚新 token 返回，让「本次改密」的会话可以平滑继续：
            # 前端可选采用 data.token；不采用则下次请求 401 → 重新登录。
            fresh_token = sign_token(
                {
                    "cid": user.get("cid") or current.cid,
                    "username": user.get("username") or "",
                    "rating": user.get("rating") or 0,
                    "permissions": user.get("permissions") or "",
                    "fsdLevel": user.get("fsdLevel") or 0,
                }
            )
            # 发送密码修改安全通知（失败静默）
            email = user.get("email")
            if email:
                ip = request.headers.get("x-forwarded-for") or (
                    request.client.host if request.client else ""
                ) or ""
                mailer.fire_and_forget(
                    mailer.send_security_alert(
                        str(email),
                        {
                            "action": "密码修改",
                            "detail": "您在个人中心修改了登录密码。",
                            "time": _zh_now(),
                            "ip": ip,
                        },
                    )
                )
            return JSJSONResponse(
                {
                    "success": True,
                    "message": "更新成功",
                    "data": {"token": fresh_token},
                },
                headers={"X-Renewed-Token": fresh_token},
            )

        return _ok(message="更新成功")
    except Exception as exc:  # noqa: BLE001
        log.error("[profile.py] %s", exc)
        return _fail(500, MESSAGE_OPERATION_FAILED)


# ==================== POST /avatar 已停用（仅允许 QQ 头像） ====================
@router.post("/avatar")
async def upload_avatar(
    avatar: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    return _fail(403, "自定义头像已停用，请绑定 QQ 使用 QQ 头像")


# ==================== PUT /info 更新资料 ====================
@router.put("/info")
async def update_info(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        body = await _read_json(request)
        data: dict[str, Any] = {}

        # 安全（2026-08-07）：禁止通过 /info 直接改邮箱
        if "email" in body:
            return _fail(400, "邮箱修改请使用「邮箱验证」流程")

        if "avatar" in body:
            return _fail(400, "头像跟随绑定 QQ 自动生成，不支持自定义头像")

        if "qq" in body:
            qq = body.get("qq")
            if qq is None:
                return _fail(500, MESSAGE_OPERATION_FAILED)
            qq = str(qq).strip()
            if qq and not re.fullmatch(r"\d{5,12}", qq):
                return _fail(400, "QQ 号格式不正确")
            data["qq"] = qq
            # 头像只由 QQ 号生成；解绑 QQ 后清空，前端显示默认头像
            data["avatar"] = _qq_avatar(qq)

        await ps.update_info(db, current.cid, data)

        user = await ps.get_info_result(db, current.cid)
        if user is None:
            return _fail(500, MESSAGE_OPERATION_FAILED)
        return _ok(
            {
                "cid": user.get("cid"),
                "username": user.get("username"),
                "rating": int(user.get("rating") or 0),
                "fsdLevel": int(user.get("fsdLevel") or 0),
                # User 表无 fsdType 列，Node `user.fsdType ?? 'PILOT'` 恒为 'PILOT'
                "fsdType": user.get("fsdType") or "PILOT",
                "email": user.get("email"),
                "qq": user.get("qq"),
                "avatar": _qq_avatar(user.get("qq")),
            },
            message="已更新",
        )
    except Exception as exc:  # noqa: BLE001
        log.error("[profile.py] %s", exc)
        return _fail(500, MESSAGE_OPERATION_FAILED)


# ==================== POST /bg-image 上传背景图 ====================
@router.post("/bg-image")
async def upload_bg_image(
    bgImage: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        if bgImage is None or not (bgImage.filename or ""):
            return _fail(400, "请选择图片")
        try:
            filename = await pu.save_background(current.cid, bgImage)
        except pu.UploadRejected:
            return _upload_failure()
        except pu.NotAnImage:
            return _fail(400, "文件内容不是有效图片")

        # 每日限制 5 次（统计当天已上传的文件数；与 Node 一致：刚上传的文件也计入）
        if pu.count_bg_today(current.cid) >= pu.BG_DAILY_LIMIT:
            pu.remove_file(pu.BG_DIR / filename)
            return JSJSONResponse(
                {"success": False, "message": "更换背景图过于频繁，请明天再试"},
                status_code=429,
            )

        bg_path = "/uploads/backgrounds/" + filename
        # 删除旧背景图文件（仅保留一个最新）
        old_url = await ps.get_bg_image(db, current.cid)
        if old_url is None:
            # Node: prisma.user.update(...) 在用户不存在时抛错 → 500「操作失败」
            return _fail(500, MESSAGE_OPERATION_FAILED)
        if old_url:
            old_file = pu.uploads_path_for_url(old_url)
            new_file = (pu.BG_DIR / filename).resolve()
            if old_file is not None and old_file != new_file:
                pu.remove_file(old_file)

        await ps.set_bg_image(db, current.cid, bg_path)
        return _ok({"bgImage": bg_path}, message="背景图已更新")
    except Exception as exc:  # noqa: BLE001
        log.error("[profile.py] %s", exc)
        return _fail(500, MESSAGE_OPERATION_FAILED)


# ==================== DELETE /bg-image 恢复默认背景 ====================
@router.delete("/bg-image")
async def delete_bg_image(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        if await ps.get_bg_image(db, current.cid) is None:
            # Node: prisma.user.update(...) 在用户不存在时抛错 → 500「操作失败」
            return _fail(500, MESSAGE_OPERATION_FAILED)
        await ps.set_bg_image(db, current.cid, "")
        return _ok(message="已恢复默认背景")
    except Exception as exc:  # noqa: BLE001
        log.error("[profile.py] %s", exc)
        return _fail(500, MESSAGE_OPERATION_FAILED)


# ==================== POST /send-verify 发送邮箱验证码 ====================
@router.post("/send-verify")
async def send_verify(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        body = await _read_json(request)
        email = body.get("email")
        if not email:
            return _fail(400, "缺少邮箱")

        user = await ps.get_profile(db, current.cid)
        if not user:
            return _fail(404, "用户不存在")

        if not isinstance(email, str):
            # Node: email.toLowerCase() 抛错 → catch → 500「操作失败」
            return _fail(500, MESSAGE_OPERATION_FAILED)

        # 6 位随机验证码（crypto，不用 Math.random）
        code = mailer.generate_code()
        expires = dt.datetime.utcnow() + dt.timedelta(milliseconds=10 * 60 * 1000)

        # 安全（2026-10-25 审计 P2-3）：验证码与目标邮箱绑定存储
        # Node: resetCode = `${email.toLowerCase()}|${code}`
        await ps.store_reset_code(db, current.cid, f"{email.lower()}|{code}", expires)

        # 发送邮件放到后台任务：接口先返回，SMTP 延迟不再计入用户等待
        async def _mail_job() -> None:
            try:
                await mailer.send_verify_code(str(email), code, "邮箱验证")
            except Exception as mail_exc:  # noqa: BLE001
                log.warning("[profile.py] 验证码邮件发送失败: %s", mail_exc)

        mailer.fire_and_forget_thread(_mail_job)

        return _ok(message="验证码已发送")
    except Exception as exc:  # noqa: BLE001
        log.error("[profile.py] %s", exc)
        return _fail(500, MESSAGE_OPERATION_FAILED)


# ==================== POST /verify-email 校验并绑定邮箱 ====================
@router.post("/verify-email")
async def verify_email(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        body = await _read_json(request)
        email = body.get("email")
        code = body.get("code")
        if not email or not code:
            return _fail(400, "缺少参数")

        user = await ps.get_reset_row(db, current.cid)
        if user is None:
            return _fail(404, "用户不存在")

        if not isinstance(email, str):
            # Node: email.toLowerCase() 抛错 → catch → 500「操作失败」
            return _fail(500, MESSAGE_OPERATION_FAILED)

        # 安全（2026-10-25 审计 P2-3）：验证码与目标邮箱绑定 + 邮箱唯一性校验
        expected = user.get("resetCode") or ""
        parts = str(expected).split("|")
        bound_email = parts[0]
        bound_code = parts[1] if len(parts) > 1 else None

        # Node 用严格相等（!==）：类型不同即视为错误
        if bound_code != code or bound_email != email.lower():
            return _fail(400, "验证码错误")

        expires = user.get("resetCodeExpires")
        if expires is not None and hasattr(expires, "replace"):
            expires_naive = expires.replace(tzinfo=None) if expires.tzinfo else expires
            if dt.datetime.utcnow() > expires_naive:
                return _fail(400, "验证码已过期")

        taken = await ps.find_cid_by_email(db, email)
        if taken is not None and str(taken) != str(current.cid):
            return _fail(400, "该邮箱已被其他账号使用")

        await ps.set_email_verified(db, current.cid, email)
        return _ok(message="邮箱验证成功")
    except Exception as exc:  # noqa: BLE001
        log.error("[profile.py] %s", exc)
        return _fail(500, MESSAGE_OPERATION_FAILED)


__all__ = ["router"]
