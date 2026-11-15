"""申请（管制员 / 职员）数据访问（对齐 Node src/routes/apply.js）。

``Application.time`` 是 Prisma String 列，Node 写入 ``new Date().toLocaleString('zh-CN')``。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.content_service import normalize_row
from app.services.zh_time_service import zh_now

APPLICATION_COLUMNS = (
    "id, userId, name, `type`, department, reason, status, `time`, "
    "interviewTime1, interviewTime2, reviewComment, reviewedBy"
)

PENDING_STATUS = "待审核"
INTERVIEW_STATUS = "待面试"
ACTIVE_STATUSES = (PENDING_STATUS, INTERVIEW_STATUS)
APPROVED_STATUSES = ("已通过", "Approved")

APPLICATION_TYPES = ("controller", "staff")


async def find_pending(
    db: AsyncSession, user_id: str, type_: str
) -> dict[str, Any] | None:
    """查询同类型、仍处于审核流程中的申请（防重复提交）。"""
    row = (
        await db.execute(
            text(
                f"SELECT {APPLICATION_COLUMNS} FROM `Application` "
                "WHERE userId = :uid AND `type` = :type "
                "AND status IN ('" + "','".join(ACTIVE_STATUSES) + "') "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"uid": user_id, "type": type_},
        )
    ).first()
    return normalize_row(row) if row else None


async def find_approved(
    db: AsyncSession, user_id: str, type_: str
) -> dict[str, Any] | None:
    """查询同类型已通过的申请，避免通过后再次提交产生重复待审记录。"""
    row = (
        await db.execute(
            text(
                f"SELECT {APPLICATION_COLUMNS} FROM `Application` "
                "WHERE userId = :uid AND `type` = :type "
                "AND status IN ('" + "','".join(APPROVED_STATUSES) + "') "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"uid": user_id, "type": type_},
        )
    ).first()
    return normalize_row(row) if row else None


async def get_staff(db: AsyncSession, user_id: str) -> dict[str, Any] | None:
    """查询用户是否已在 Staff 表（职员/管制员身份）。"""
    row = (
        await db.execute(
            text(
                "SELECT `cid`, `name`, `department`, `position`, `rating`, `active` "
                "FROM `Staff` WHERE `cid` = :cid LIMIT 1"
            ),
            {"cid": user_id},
        )
    ).first()
    return normalize_row(row) if row else None



async def create_application(
    db: AsyncSession,
    user_id: str,
    name: str,
    type_: str,
    department: Any,
    reason: Any,
) -> dict[str, Any]:
    payload = {
        "userId": user_id,
        "name": name,
        "type": type_,
        "department": department or "",
        "reason": reason or "",
        "status": PENDING_STATUS,
        "time": zh_now(),
    }
    result = await db.execute(
        text(
            "INSERT INTO `Application` (userId, name, `type`, department, reason, status, `time`) "
            "VALUES (:userId, :name, :type, :department, :reason, :status, :time)"
        ),
        payload,
    )
    await db.commit()
    app_id = int(result.lastrowid)
    return await get_application(db, app_id) or {}


async def get_application(db: AsyncSession, app_id: int) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text(f"SELECT {APPLICATION_COLUMNS} FROM `Application` WHERE id = :id LIMIT 1"),
            {"id": app_id},
        )
    ).first()
    return normalize_row(row) if row else None


async def list_my_applications(db: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            text(
                f"SELECT {APPLICATION_COLUMNS} FROM `Application` "
                "WHERE userId = :uid ORDER BY id DESC"
            ),
            {"uid": user_id},
        )
    ).all()
    return [normalize_row(r) for r in rows]


__all__ = [
    "APPLICATION_COLUMNS",
    "PENDING_STATUS",
    "INTERVIEW_STATUS",
    "ACTIVE_STATUSES",
    "APPROVED_STATUSES",
    "APPLICATION_TYPES",
    "find_pending",
    "find_approved",
    "get_staff",
    "create_application",
    "get_application",
    "list_my_applications",
]
