"""统一审计日志：分类、操作人快照、目标对象、请求溯源。

设计对齐 CTYFLY 的 audit_logs，但保留 CWFLY 现有 `AuditLog` 表：
- 新增列通过启动时幂等 ALTER 补齐；
- 写入失败不影响业务；
- risk 类只记录，不自动封禁（现有登录锁定/封禁策略已独立存在）。
"""
from __future__ import annotations

import os
import re
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.audit_context import current_request
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
    """写一条审计日志；失败静默，不阻塞业务。"""
    try:
        actor_name = actor_name or ""
        actor_role = actor_role or ""
        if operator and (not actor_name or not actor_role):
            snapshot_name, snapshot_role = await _actor_snapshot(db, str(operator))
            actor_name = actor_name or snapshot_name or str(operator)
            actor_role = actor_role or snapshot_role

        req = current_request()
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
    except Exception:  # noqa: BLE001
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass


def _days_filter(days: int) -> int:
    return max(1, min(int(days or 7), 90))


def now_ms() -> int:
    return int(time.time() * 1000)


__all__ = [
    "CATEGORIES",
    "CATEGORY_LABELS",
    "classify_action",
    "classify_ua",
    "ensure_schema",
    "write",
]
