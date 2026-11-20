"""/api/dashboard 路由（逐接口对齐 Node src/routes/dashboard.js）。

GET /api/dashboard/stats（公开）
- totalUsers       User 总数
- controllerCount  fsdLevel >= 1（OBS 及以上）或 rating >= 11（SUP/ADM 平台管理员）
- eventCount       Event 总数
- onlineUsers      FSD 在线机组数（FlightPilot + FlightController 去重）
- onlinePilotCount / onlineControllerCount  FSD 在线飞行员/管制员数
- webOnlineUsers   OnlineUser 表 2 分钟内活跃（仅网页在线，不含 FSD 身份）
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.utils.json_compat import JSJSONResponse

log = logging.getLogger("cwfly.dashboard")
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _count(db: AsyncSession, sql: str) -> int:
    row = (await db.execute(text(sql))).first()
    if row is None:
        return 0
    return int(row._mapping["c"] or 0)


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)) -> JSJSONResponse:
    try:
        total_users = await _count(db, "SELECT COUNT(*) AS c FROM `User`")
        controller_count = await _count(
            db,
            "SELECT COUNT(*) AS c FROM `User` WHERE fsdLevel >= 1 OR rating >= 11",
        )
        event_count = await _count(db, "SELECT COUNT(*) AS c FROM `Event`")
        # 统计口径统一：首页“在线用户”只认真正连接到 FSD 的机组，
        # 不能把仅打开网页的登录账号/游客（OnlineUser 表）算进去，
        # 否则会出现“在线飞行员 0、在线管制员 0、在线用户 1”的穿帮。
        # TODO: 若未来增加非 FSD 的在线身份，必须同时提供可区分的字段，
        # 不要复用 onlineUsers 这个展示口径。
        # 某些开发库还没有 FSD 快照表，先探测表是否存在，缺失时按 0 处理，避免首页接口 500。
        fsd_tables = await _count(
            db,
            "SELECT COUNT(*) AS c FROM information_schema.tables "
            "WHERE table_schema = DATABASE() "
            "AND LOWER(table_name) IN ('flightpilot', 'flightcontroller')",
        )
        if fsd_tables >= 2:
            online_pilot_count = await _count(db, "SELECT COUNT(*) AS c FROM `FlightPilot`")
            online_controller_count = await _count(db, "SELECT COUNT(*) AS c FROM `FlightController`")
            online_users = await _count(
                db,
                "SELECT COUNT(*) AS c FROM ("
                "  SELECT COALESCE(NULLIF(`cid`, ''), `callsign`) AS online_key FROM `FlightPilot`"
                "  UNION"
                "  SELECT COALESCE(NULLIF(`cid`, ''), `callsign`) AS online_key FROM `FlightController`"
                ") AS online_fsd",
            )
        else:
            log.warning("[Dashboard] 缺少 FlightPilot/FlightController，在线 FSD 统计按 0 处理")
            online_pilot_count = 0
            online_controller_count = 0
            online_users = 0

        online_tables = await _count(
            db,
            "SELECT COUNT(*) AS c FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND LOWER(table_name) = 'onlineuser'",
        )
        if online_tables:
            web_online_row = (
                await db.execute(
                    text(
                        "SELECT COUNT(*) AS n FROM `OnlineUser` "
                        "WHERE lastSeen >= DATE_SUB(NOW(3), INTERVAL 2 MINUTE)"
                    )
                )
            ).first()
            web_online_users = int(web_online_row._mapping["n"] or 0) if web_online_row is not None else 0
        else:
            web_online_users = 0

        data: dict[str, Any] = {
            "totalUsers": total_users,
            "controllerCount": controller_count,
            "eventCount": event_count,
            "onlineUsers": online_users,
            "onlinePilotCount": online_pilot_count,
            "onlineControllerCount": online_controller_count,
            "webOnlineUsers": web_online_users,
        }
        return JSJSONResponse({"success": True, "data": data})
    except Exception as exc:  # noqa: BLE001
        log.error("[Dashboard] 查询失败: %s", exc)
        return JSJSONResponse({"success": False, "message": "查询失败"}, status_code=500)


__all__ = ["router"]
