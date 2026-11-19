"""统一审计日志：分类、操作人快照、目标对象、请求溯源。

设计对齐 CTYFLY 的 audit_logs，但保留 CWFLY 现有 `AuditLog` 表：
- 新增列通过启动时幂等 ALTER 补齐；
- 写入失败不影响业务；
- risk 类只记录，不自动封禁（现有登录锁定/封禁策略已独立存在）。
"""
from __future__ import annotations

import os
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.audit_context import current_request, mark_semantic_audit
from app.utils.client import get_client_ip, get_user_agent

CATEGORIES = ("auth", "permission", "content", "risk", "admin", "system")

CATEGORY_LABELS = {
    "auth": "认证类",
    "permission": "权限类",
    "content": "内容类",
    "risk": "越权与风控",
    "admin": "管理操作",
    "system": "系统类",
}

_ADDED_COLUMNS = {
    "category": "VARCHAR(32) NOT NULL DEFAULT 'admin'",
    "actorName": "VARCHAR(191) NOT NULL DEFAULT ''",
    "actorRole": "VARCHAR(64) NOT NULL DEFAULT ''",
    "targetType": "VARCHAR(64) NOT NULL DEFAULT ''",
    "targetId": "VARCHAR(191) NOT NULL DEFAULT ''",
    "ip": "VARCHAR(64) NOT NULL DEFAULT ''",
    "ua": "VARCHAR(512) NOT NULL DEFAULT ''",
    "uaLabel": "VARCHAR(64) NOT NULL DEFAULT ''",
    "uaBot": "TINYINT(1) NOT NULL DEFAULT 0",
    "pid": "INT NOT NULL DEFAULT 0",
}

_ready = False

# 旧 action 编码 → 类别；未命中时归入 admin。
_CATEGORY_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^(login|logout|password|verify|oauth)"), "auth"),
    (re.compile(r"^(ban|unban|risk|ban_device|unban_device|ip_ban)"), "risk"),
    (re.compile(r"^(role|permission|staff|delete_user|edit_user|user_approval)"), "permission"),
    (re.compile(r"^(announcement|meeting|event|forum|article|content)"), "content"),
    (re.compile(r"^(system|config|scheduler|migration)"), "system"),
)

_UA_BOT_RE = re.compile(
    r"(bot|crawler|spider|python-requests|python-urllib|curl/|wget/|httpclient|axios/|go-http-client|scrapy)",
    re.IGNORECASE,
)

# 业务路由 → 可读动作名。未显式写审计的业务模块由中间件按此表补语义。
# 每项: (method, path regex, action, category, target_type)
_SEMANTIC_ROUTES: tuple[tuple[str, re.Pattern[str], str, str, str], ...] = (
    ("POST", re.compile(r"^/api/profile/avatar/?$"), "更新头像", "permission", "profile"),
    ("PUT", re.compile(r"^/api/profile/info/?$"), "更新绑定信息", "permission", "profile"),
    ("PUT", re.compile(r"^/api/profile/?$"), "修改密码", "auth", "profile"),
    ("POST", re.compile(r"^/api/profile/bg-image/?$"), "更新背景图", "content", "profile"),
    ("DELETE", re.compile(r"^/api/profile/bg-image/?$"), "恢复默认背景", "content", "profile"),
    ("POST", re.compile(r"^/api/profile/send-verify/?$"), "发送邮箱验证码", "auth", "profile"),
    ("POST", re.compile(r"^/api/profile/verify-email/?$"), "验证并绑定邮箱", "auth", "profile"),
    ("POST", re.compile(r"^/api/tickets/?$"), "提交工单", "content", "ticket"),
    ("DELETE", re.compile(r"^/api/tickets/(?P<id>[^/]+)/?$"), "删除工单", "content", "ticket"),
    ("POST", re.compile(r"^/api/apply/controller/?$"), "提交管制员申请", "permission", "application"),
    ("POST", re.compile(r"^/api/apply/staff/?$"), "提交职员申请", "permission", "application"),
    ("POST", re.compile(r"^/api/events/?$"), "创建活动", "content", "event"),
    ("PUT", re.compile(r"^/api/events/(?P<id>[^/]+)/?$"), "编辑活动", "content", "event"),
    ("DELETE", re.compile(r"^/api/events/(?P<id>[^/]+)/?$"), "删除活动", "content", "event"),
    ("POST", re.compile(r"^/api/events/(?P<id>[^/]+)/join/?$"), "报名活动", "content", "event"),
    ("DELETE", re.compile(r"^/api/events/(?P<id>[^/]+)/join/?$"), "取消活动报名", "content", "event"),
    ("DELETE", re.compile(r"^/api/events/registrations/(?P<id>[^/]+)/?$"), "移除活动报名", "permission", "event"),
    ("POST", re.compile(r"^/api/meetings/upload/?$"), "上传会议记录", "content", "meeting"),
    ("POST", re.compile(r"^/api/forum/posts/?$"), "发布论坛帖子", "content", "forum_post"),
    ("POST", re.compile(r"^/api/forum/posts/(?P<id>[^/]+)/reply/?$"), "回复论坛帖子", "content", "forum_post"),
    ("POST", re.compile(r"^/api/training/courses/(?P<id>[^/]+)/enroll/?$"), "报名培训课程", "content", "training_course"),
    ("POST", re.compile(r"^/api/training/exams/(?P<id>[^/]+)/submit/?$"), "提交培训考试", "content", "training_exam"),
    ("POST", re.compile(r"^/api/training/schedules/?$"), "创建培训排班", "content", "training_schedule"),
    ("POST", re.compile(r"^/api/flightplans/simbrief-import/?$"), "导入 SimBrief 飞行计划", "content", "flight_plan"),
    ("POST", re.compile(r"^/api/flightplans/?$"), "提交飞行计划", "content", "flight_plan"),
    ("POST", re.compile(r"^/api/flightplans/(?P<id>[^/]+)/fsd-sync/?$"), "同步飞行计划到 FSD", "content", "flight_plan"),
    ("DELETE", re.compile(r"^/api/flightplans/(?P<id>[^/]+)/?$"), "删除飞行计划", "content", "flight_plan"),
    ("POST", re.compile(r"^/api/checkin/?$"), "每日签到", "content", "checkin"),
    ("POST", re.compile(r"^/api/feedback/?$"), "提交反馈", "content", "feedback"),
    ("PUT", re.compile(r"^/api/notifications/read-all/?$"), "全部标记已读", "system", "notification"),
    ("PUT", re.compile(r"^/api/notifications/read/(?P<id>[^/]+)/?$"), "标记通知已读", "system", "notification"),
    ("POST", re.compile(r"^/api/auth/logout/?$"), "退出登录", "auth", "session"),
    ("PUT", re.compile(r"^/api/auth/password/?$"), "修改密码", "auth", "account"),
    ("POST", re.compile(r"^/api/auth/refresh/?$"), "刷新登录状态", "auth", "session"),
    ("POST", re.compile(r"^/api/auth/login-verify/?$"), "完成登录二次验证", "auth", "session"),
    ("POST", re.compile(r"^/api/auth/register/?$"), "注册账号", "auth", "account"),
    ("POST", re.compile(r"^/api/auth/forgot-password/?$"), "申请找回密码", "auth", "account"),
    ("POST", re.compile(r"^/api/auth/reset-password/?$"), "重置密码", "auth", "account"),
)


def classify_ua(ua: str) -> tuple[str, bool]:
    text = (ua or "").strip()
    if not text:
        return "未知", False
    if _UA_BOT_RE.search(text):
        return "脚本 / 爬虫", True
    if "Edg/" in text:
        return "Edge", False
    if "Chrome/" in text:
        return "Chrome", False
    if "Firefox/" in text:
        return "Firefox", False
    if "Safari/" in text:
        return "Safari", False
    return text[:40], False


def classify_action(action: str) -> str:
    value = (action or "").strip().lower()
    for pattern, category in _CATEGORY_RULES:
        if pattern.search(value):
            return category
    return "admin"


def semantic_action(method: str, path: str) -> tuple[str, str, str, str] | None:
    """返回 (可读动作, 类别, 目标类型, 目标 ID)；未匹配到业务路由时返回 None。"""
    verb = (method or "").upper()
    clean_path = "/" + (path or "").strip("/")
    for route_method, pattern, action, category, target_type in _SEMANTIC_ROUTES:
        if route_method != verb:
            continue
        match = pattern.match(clean_path)
        if match:
            target_id = match.groupdict().get("id", "")
            return action, category, target_type, str(target_id or "")
    return None


async def ensure_schema() -> None:
    """幂等补齐 AuditLog 的新列；旧表可继续写入。"""
    global _ready
    if _ready:
        return
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT COLUMN_NAME AS name FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'AuditLog'"
                )
            )
        ).all()
        existing = {str(r._mapping.get("name") or "").lower() for r in rows}
        for name, definition in _ADDED_COLUMNS.items():
            if name.lower() in existing:
                continue
            await db.execute(text(f"ALTER TABLE `AuditLog` ADD COLUMN `{name}` {definition}"))
        await db.commit()
    _ready = True


def _actor_role(rating: int, fsd_level: int, permissions: str) -> str:
    if rating >= 12:
        return "超级管理员"
    if rating >= 11:
        return "管理员"
    if rating >= 8:
        return "协管员"
    if fsd_level >= 2:
        return "管制员"
    if permissions:
        return "职员"
    return "用户"


async def _actor_snapshot(db: AsyncSession, cid: str) -> tuple[str, str]:
    if not cid:
        return "", ""
    try:
        row = (
            await db.execute(
                text(
                    "SELECT username, rating, permissions, fsdLevel FROM `User` "
                    "WHERE cid = :cid LIMIT 1"
                ),
                {"cid": str(cid)},
            )
        ).first()
        if not row:
            return "", ""
        item = row._mapping
        return (
            str(item.get("username") or ""),
            _actor_role(
                int(item.get("rating") or 0),
                int(item.get("fsdLevel") or 0),
                str(item.get("permissions") or ""),
            ),
        )
    except Exception:  # noqa: BLE001
        return "", ""


async def _insert(
    db: AsyncSession,
    action: str,
    detail: str,
    operator: str,
    *,
    category: str | None,
    target_type: str,
    target_id: Any,
    actor_name: str,
    actor_role: str,
    request: Any = None,
) -> None:
    actor_name = actor_name or ""
    actor_role = actor_role or ""
    if operator and (not actor_name or not actor_role):
        snapshot_name, snapshot_role = await _actor_snapshot(db, str(operator))
        actor_name = actor_name or snapshot_name or str(operator)
        actor_role = actor_role or snapshot_role

    req = request if request is not None else current_request()
    ip = get_client_ip(req) if req is not None else ""
    ua = get_user_agent(req) if req is not None else ""
    ua_label, ua_bot = classify_ua(ua)
    value = str(detail or "")
    await db.execute(
        text(
            "INSERT INTO `AuditLog` (`userId`, `action`, `target`, `detail`, "
            "`category`, `actorName`, `actorRole`, `targetType`, `targetId`, "
            "`ip`, `ua`, `uaLabel`, `uaBot`, `pid`) VALUES "
            "(:uid, :action, :target, :detail, :category, :actorName, :actorRole, "
            ":targetType, :targetId, :ip, :ua, :uaLabel, :uaBot, :pid)"
        ),
        {
            "uid": str(operator or "system"),
            "action": str(action or "")[:191],
            "target": value[:191],
            "detail": value[:191],
            "category": category or classify_action(action),
            "actorName": actor_name[:191],
            "actorRole": actor_role[:64],
            "targetType": str(target_type or "")[:64],
            "targetId": str(target_id or "")[:191],
            "ip": ip[:64],
            "ua": ua[:512],
            "uaLabel": ua_label[:64],
            "uaBot": 1 if ua_bot else 0,
            "pid": os.getpid(),
        },
    )
    await db.commit()


async def write(
    db: AsyncSession,
    action: str,
    detail: str = "",
    operator: str = "",
    *,
    category: str | None = None,
    target_type: str = "",
    target_id: Any = "",
    actor_name: str = "",
    actor_role: str = "",
) -> None:
    """写一条有业务语义的审计日志；失败静默，不阻塞业务。"""
    try:
        await _insert(
            db,
            action,
            detail,
            operator,
            category=category,
            target_type=target_type,
            target_id=target_id,
            actor_name=actor_name,
            actor_role=actor_role,
        )
        mark_semantic_audit()
    except Exception:  # noqa: BLE001
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass


def _category_for_path(path: str) -> str:
    value = (path or "").lower()
    if value.startswith("/api/auth"):
        return "auth"
    if value.startswith("/api/admin"):
        return "admin"
    if value.startswith("/api/security"):
        return "risk"
    if value.startswith("/api/profile"):
        return "permission"
    if value.startswith(("/api/tickets", "/api/apply", "/api/events", "/api/meetings",
                         "/api/forum", "/api/content", "/api/training", "/api/staff")):
        return "content"
    return "system"


def _claims_actor(request: Any) -> tuple[str, str, str]:
    """从 Bearer token 取操作人；无效/匿名请求记为 anonymous。"""
    if request is None:
        return "anonymous", "游客", ""
    header = request.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        return "anonymous", "游客", ""
    try:
        from app.services.token import verify_token

        claims = verify_token(header[len("Bearer ") :])
    except Exception:  # noqa: BLE001
        return "anonymous", "游客", ""
    cid = str(claims.get("cid") or "").strip()
    if not cid:
        return "anonymous", "游客", ""
    name = str(claims.get("username") or cid)
    role = _actor_role(
        int(claims.get("rating") or 0),
        int(claims.get("fsdLevel") or 0),
        str(claims.get("permissions") or ""),
    )
    return cid, name, role


async def write_generic_request(
    db: AsyncSession,
    *,
    method: str,
    path: str,
    status: int,
    duration_ms: int,
    request: Any = None,
) -> None:
    """中间件兜底：记录所有未显式审计的 /api 请求。"""
    cid, name, role = _claims_actor(request)
    clean_path = str(path or "")[:150]
    semantic = semantic_action(method, clean_path)
    if semantic:
        action, category, target_type, target_id = semantic
        detail = f"{method} {clean_path} · HTTP {status} · {max(0, int(duration_ms))}ms"
    else:
        action = f"{method} {clean_path}"
        category = _category_for_path(clean_path)
        target_type = "api"
        target_id = clean_path
        detail = f"HTTP {status} · {max(0, int(duration_ms))}ms"
    await _insert(
        db,
        action,
        detail,
        cid,
        category=category,
        target_type=target_type,
        target_id=target_id,
        actor_name=name,
        actor_role=role,
        request=request,
    )


__all__ = [
    "CATEGORIES",
    "CATEGORY_LABELS",
    "classify_action",
    "classify_ua",
    "ensure_schema",
    "semantic_action",
    "write",
    "write_generic_request",
]
