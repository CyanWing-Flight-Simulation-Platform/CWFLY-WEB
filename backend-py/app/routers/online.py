"""/api/online 在线客户端（数据源：FSD 管理口 3012，只读主数据 + 管理动作）。

不修改/重启 FSD，复用其既有管理控制台：
- GET  /clients    在线机组/管制列表（含主站昵称、等级、静默时长）
- GET  /stats      连接数/证书数/包量/事件循环延迟等运行指标
- POST /message    向某个呼号发送游戏内服务端消息
- POST /broadcast  全服广播（管理员）
- POST /kick       踢出在线客户端（管理员）
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.config import settings
from app.deps import AuthFailure, CurrentUser, get_current_user, require_admin_access
from app.services import fsd_console
from app.utils.json_compat import JSJSONResponse

log = logging.getLogger("cwfly.online")

router = APIRouter(prefix="/online", tags=["online"])


async def require_bot_key(request: Request) -> None:
    """机器人/内部服务调用：X-API-Key（或 Bearer）需与 OPENAPI_KEY 一致。"""
    expected = (settings.OPENAPI_KEY or "").strip()
    if not expected:
        raise AuthFailure(503, "未配置 OPENAPI_KEY，机器人接口不可用")
    provided = (request.headers.get("x-api-key") or "").strip()
    if not provided:
        auth = (request.headers.get("authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
    if not provided or provided != expected:
        raise AuthFailure(401, "API Key 无效")


def _ok(data: Any = None, **extra: Any) -> JSJSONResponse:
    body: dict[str, Any] = {"success": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return JSJSONResponse(body)


def _fail(status_code: int, message: str) -> JSJSONResponse:
    return JSJSONResponse({"success": False, "message": message}, status_code=status_code)


async def _user_index(db: AsyncSession, cids: list[str]) -> dict[str, dict[str, Any]]:
    clean = sorted({c for c in cids if c and c.isdigit()})
    if not clean:
        return {}
    try:
        placeholders = ",".join(f":c{i}" for i in range(len(clean)))
        rows = (
            await db.execute(
                text(
                    f"SELECT cid, username, rating, fsdLevel FROM `User` WHERE cid IN ({placeholders})"
                ),
                {f"c{i}": cid for i, cid in enumerate(clean)},
            )
        ).all()
        return {str(r._mapping["cid"]): dict(r._mapping) for r in rows}
    except Exception as exc:  # noqa: BLE001
        log.warning("[online] 查询用户资料失败: %s", exc)
        return {}


@router.get("/clients")
async def clients(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        raw = await fsd_console.list_clients()
    except fsd_console.FsdConsoleError as exc:
        return _fail(503, f"FSD 管理口不可用：{exc}")
    except Exception as exc:  # noqa: BLE001
        log.warning("[online] 获取在线列表失败: %s", exc)
        return _fail(503, "获取在线列表失败")

    info = await _user_index(db, [str(c.get("cid") or "") for c in raw])
    items = []
    for c in raw:
        cid = str(c.get("cid") or "")
        u = info.get(cid) or {}
        items.append(
            {
                "callsign": c.get("callsign"),
                "cid": cid,
                "type": c.get("type"),
                "rating": c.get("rating"),
                "idle": c.get("idle"),
                "username": u.get("username") or "",
                "fsdLevel": u.get("fsdLevel"),
            }
        )
    pilots = sum(1 for i in items if i["type"] == "PILOT")
    return _ok({"items": items, "pilotCount": pilots, "atcCount": len(items) - pilots})


@router.get("/stats")
async def stats(current: CurrentUser = Depends(get_current_user)) -> Any:
    try:
        data = await fsd_console.stats()
    except fsd_console.FsdConsoleError as exc:
        return _fail(503, f"FSD 管理口不可用：{exc}")
    except Exception as exc:  # noqa: BLE001
        log.warning("[online] 获取统计失败: %s", exc)
        return _fail(503, "获取统计失败")
    return _ok(data)


@router.get("/snapshot")
async def snapshot(
    _bot: None = Depends(require_bot_key),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """在线快照（机器人与内部服务用）：直接读 FSD 落库的 FlightController/FlightPilot。

    不含 ATIS（FSD 仅内存保存，需协议连接才能取），其余字段与 FSD9 客户端一致。
    """
    try:
        controller_rows = (
            await db.execute(
                text(
                    "SELECT c.callsign, c.cid, c.realname, c.frequency, c.facilityType, "
                    "       c.visualRange, c.latitude, c.longitude, "
                    "       COALESCE(u.fsdLevel, 0) AS rating, l.createdAt AS startAt "
                    "FROM `FlightController` c "
                    "LEFT JOIN `User` u ON u.cid = c.cid "
                    "LEFT JOIN (SELECT callsign, MAX(id) AS maxId FROM `FlightLog` "
                    "           WHERE offlineAt IS NULL GROUP BY callsign) lm ON lm.callsign = c.callsign "
                    "LEFT JOIN `FlightLog` l ON l.id = lm.maxId"
                )
            )
        ).all()
        pilot_rows = (
            await db.execute(
                text(
                    "SELECT p.callsign, p.cid, p.realname, p.altitude, p.groundspd, p.transponder, "
                    "       p.latitude, p.longitude, p.heading, p.home, "
                    "       COALESCE(u.fsdLevel, 0) AS rating, l.createdAt AS startAt, "
                    "       fp.flightType AS planType, fp.aircraft AS planAircraft, "
                    "       fp.depIcao AS planDep, fp.arrIcao AS planArr, fp.cruiseAlt AS planAlt, "
                    "       fp.cruiseSpeed AS planSpeed, fp.route AS planRoute, "
                    "       fp.alternate AS planAltAirport, fp.remarks AS planRemarks "
                    "FROM `FlightPilot` p "
                    "LEFT JOIN `User` u ON u.cid = p.cid "
                    "LEFT JOIN (SELECT callsign, MAX(id) AS maxId FROM `FlightLog` "
                    "           WHERE offlineAt IS NULL GROUP BY callsign) lm ON lm.callsign = p.callsign "
                    "LEFT JOIN `FlightLog` l ON l.id = lm.maxId "
                    "LEFT JOIN (SELECT callsign, MAX(id) AS maxPlanId FROM `FlightPlan` GROUP BY callsign) pm "
                    "       ON pm.callsign = p.callsign "
                    "LEFT JOIN `FlightPlan` fp ON fp.id = pm.maxPlanId"
                )
            )
        ).all()
    except Exception as exc:  # noqa: BLE001
        log.warning("[online] 快照查询失败: %s", exc)
        return _fail(503, "获取在线快照失败")

    def _epoch(value: Any) -> int:
        if value is None:
            return 0
        try:
            return int(value.timestamp()) if hasattr(value, "timestamp") else 0
        except Exception:  # noqa: BLE001
            return 0

    def _num(value: Any, default: float = 0) -> float:
        try:
            return float(value)
        except Exception:  # noqa: BLE001
            return default

    controllers = []
    for r in controller_rows:
        d = dict(r._mapping)
        callsign = str(d.get("callsign") or "")
        controllers.append(
            {
                "callsign": callsign,
                "cid": str(d.get("cid") or ""),
                "realname": d.get("realname") or "",
                "rating": int(d.get("rating") or 0),
                "frequency": int(_num(d.get("frequency"))),
                "facilitytype": int(_num(d.get("facilityType"))),
                "visualrange": int(_num(d.get("visualRange"), 40)),
                "lat": _num(d.get("latitude")),
                "lon": _num(d.get("longitude")),
                "atis": "",
                "starttime": _epoch(d.get("startAt")),
                "isBot": callsign.upper().startswith("CW-"),
            }
        )

    pilots = []
    for r in pilot_rows:
        d = dict(r._mapping)
        callsign = str(d.get("callsign") or "")
        plan = {
            "type": d.get("planType") or "",
            "aircraft": d.get("planAircraft") or "",
            "depairport": d.get("planDep") or "",
            "destairport": d.get("planArr") or "",
            "altitude": d.get("planAlt") or "",
            "tascruise": d.get("planSpeed") or "",
            "route": d.get("planRoute") or "",
            "altairport": d.get("planAltAirport") or "",
            "remarks": d.get("planRemarks") or "",
        }
        pilots.append(
            {
                "callsign": callsign,
                "cid": str(d.get("cid") or ""),
                "realname": d.get("realname") or "",
                "rating": int(d.get("rating") or 0),
                "aircraft": plan["aircraft"],
                "altitude": int(_num(d.get("altitude"))),
                "groundspeed": int(_num(d.get("groundspd"))),
                "transponder": int(_num(d.get("transponder"))),
                "lat": _num(d.get("latitude")),
                "lon": _num(d.get("longitude")),
                "heading": int(_num(d.get("heading"))),
                "home": d.get("home") or "",
                "plan": plan,
                "starttime": _epoch(d.get("startAt")),
                "isBot": callsign.upper().startswith("CW-"),
            }
        )

    return _ok(
        {
            "pilots": [p for p in pilots if not p["isBot"]],
            "controllers": [c for c in controllers if not c["isBot"]],
            "bots": [p["callsign"] for p in pilots if p["isBot"]] + [c["callsign"] for c in controllers if c["isBot"]],
            "total": len(pilots) + len(controllers),
        }
    )


@router.post("/message")
async def message(
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _fail(400, "请求体格式错误")
    callsign = str((body or {}).get("callsign") or "").strip()
    text_value = str((body or {}).get("text") or "").strip()
    if not callsign or not text_value:
        return _fail(400, "呼号与内容不能为空")
    if len(text_value) > 300:
        return _fail(400, "消息长度不能超过 300 字")
    # 只有机组本人、管制或管理员能给在线客户端发游戏内消息
    me = await _own_callsigns(db, str(current.cid))
    is_admin = bool(current.permissions or "").strip()
    if callsign not in me and not is_admin and str(current.rating or 0) < 5:
        log.info("[online] 越权消息尝试 cid=%s cs=%s", current.cid, callsign)
        return _fail(403, "只有本人、管制或管理员可以发送游戏内消息")
    try:
        await fsd_console.say(callsign, text_value)
    except fsd_console.FsdConsoleError as exc:
        return _fail(400, str(exc))
    return _ok({"callsign": callsign})


async def _own_callsigns(db: AsyncSession, cid: str) -> set[str]:
    """本人当前在线使用的呼号（用于限制越权私聊）。"""
    try:
        rows = (
            await db.execute(
                text("SELECT callsign FROM `FlightController` WHERE cid = :cid"),
                {"cid": cid},
            )
        ).all()
        return {str(r._mapping["callsign"]) for r in rows}
    except Exception:  # noqa: BLE001
        return set()


@router.post("/broadcast")
async def broadcast(
    request: Request,
    current: CurrentUser = Depends(require_admin_access),
) -> Any:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _fail(400, "请求体格式错误")
    text_value = str((body or {}).get("text") or "").strip()
    if not text_value:
        return _fail(400, "广播内容不能为空")
    if len(text_value) > 300:
        return _fail(400, "广播内容不能超过 300 字")
    try:
        count = await fsd_console.wall(text_value)
    except fsd_console.FsdConsoleError as exc:
        return _fail(400, str(exc))
    log.warning("[online] 管理员 %s 全服广播: %s", current.cid, text_value[:80])
    return _ok({"delivered": count})


@router.post("/kick")
async def kick(
    request: Request,
    current: CurrentUser = Depends(require_admin_access),
) -> Any:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _fail(400, "请求体格式错误")
    callsign = str((body or {}).get("callsign") or "").strip()
    if not callsign:
        return _fail(400, "呼号不能为空")
    try:
        await fsd_console.kick(callsign)
    except fsd_console.FsdConsoleError as exc:
        return _fail(400, str(exc))
    log.warning("[online] 管理员 %s 踢出在线客户端 %s", current.cid, callsign)
    return _ok({"callsign": callsign})
