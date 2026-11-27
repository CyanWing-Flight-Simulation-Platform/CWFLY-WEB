"""站内消息 + 在线客户端（对齐 flyisfp 的 /clients、/chat、未读红点能力）。

数据面来源：
- 在线列表 / 统计：FSD 管理口 3012（services.fsd_console），不重启 FSD
- 站内消息：MySQL `DirectMessage` 表；若收件人在线，同时用 FSD `say` 送进游戏内
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.services import fsd_console
from app.services import users as users_svc
from app.utils.json_compat import JSJSONResponse

log = logging.getLogger("cwfly.messages")

router = APIRouter(prefix="/messages", tags=["messages"])

MAX_BODY = 500
MAX_PAGE = 100


def _ok(data: Any = None, **extra: Any) -> JSJSONResponse:
    body: dict[str, Any] = {"success": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return JSJSONResponse(body)


def _fail(status_code: int, message: str) -> JSJSONResponse:
    return JSJSONResponse({"success": False, "message": message}, status_code=status_code)


async def ensure_table(db: AsyncSession) -> None:
    """幂等建表：DirectMessage（首次调用会创建，避免依赖手工迁移）。"""
    await db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS `DirectMessage` ("
            "`id` INT NOT NULL AUTO_INCREMENT,"
            "`fromCid` VARCHAR(16) NOT NULL,"
            "`toCid` VARCHAR(16) NOT NULL,"
            "`body` VARCHAR(1000) NOT NULL,"
            "`createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),"
            "`readAt` DATETIME(3) NULL,"
            "PRIMARY KEY (`id`),"
            "INDEX `idx_dm_to` (`toCid`, `readAt`),"
            "INDEX `idx_dm_from` (`fromCid`, `createdAt`),"
            "INDEX `idx_dm_pair` (`fromCid`, `toCid`, `createdAt`)"
            ") DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    )
    await db.commit()


async def _names_for(db: AsyncSession, cids: list[str]) -> dict[str, dict[str, Any]]:
    """批量取用户昵称/呼号信息，失败时降级为空（不影响消息读取）。"""
    clean = sorted({str(c) for c in cids if c and str(c).strip()})
    if not clean:
        return {}
    try:
        placeholders = ",".join(f":c{i}" for i in range(len(clean)))
        params = {f"c{i}": cid for i, cid in enumerate(clean)}
        rows = (
            await db.execute(
                text(f"SELECT cid, username, rating FROM `User` WHERE cid IN ({placeholders})"),
                params,
            )
        ).all()
        return {str(r._mapping["cid"]): dict(r._mapping) for r in rows}
    except Exception as exc:  # noqa: BLE001
        log.warning("[messages] 查询用户资料失败: %s", exc)
        return {}


@router.get("/unread-count")
async def unread_count(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    row = (
        await db.execute(
            text("SELECT COUNT(*) AS c FROM `DirectMessage` WHERE toCid = :cid AND readAt IS NULL"),
            {"cid": str(current.cid)},
        )
    ).first()
    return _ok({"unread": int(row._mapping["c"] or 0) if row else 0})


@router.get("/conversations")
async def conversations(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    me = str(current.cid)
    rows = (
        await db.execute(
            text(
                "SELECT peer, MAX(id) AS lastId, SUM(unread) AS unread FROM ("
                "  SELECT IF(fromCid = :me, toCid, fromCid) AS peer, id,"
                "         IF(toCid = :me AND readAt IS NULL, 1, 0) AS unread"
                "  FROM `DirectMessage` WHERE fromCid = :me OR toCid = :me"
                ") t GROUP BY peer ORDER BY lastId DESC LIMIT 50"
            ),
            {"me": me},
        )
    ).all()
    if not rows:
        return _ok({"items": []})
    last_ids = [int(r._mapping["lastId"]) for r in rows]
    placeholders = ",".join(f":i{k}" for k in range(len(last_ids)))
    last_rows = (
        await db.execute(
            text(
                f"SELECT id, fromCid, toCid, body, createdAt FROM `DirectMessage` WHERE id IN ({placeholders})"
            ),
            {f"i{k}": v for k, v in enumerate(last_ids)},
        )
    ).all()
    last_map = {int(r._mapping["id"]): dict(r._mapping) for r in last_rows}
    names = await _names_for(db, [str(r._mapping["peer"]) for r in rows])
    items = []
    for r in rows:
        peer = str(r._mapping["peer"])
        last = last_map.get(int(r._mapping["lastId"])) or {}
        items.append(
            {
                "peerCid": peer,
                "peerName": (names.get(peer) or {}).get("username") or peer,
                "unread": int(r._mapping["unread"] or 0),
                "lastBody": last.get("body") or "",
                "lastAt": str(last.get("createdAt") or ""),
                "lastFromMe": str(last.get("fromCid") or "") == me,
            }
        )
    return _ok({"items": items})


@router.get("/{peer_cid}")
async def thread(
    peer_cid: str,
    before: Optional[int] = None,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    me = str(current.cid)
    peer = str(peer_cid).strip()
    if not peer:
        return _fail(400, "对方 CID 不能为空")
    where = ["(fromCid = :me AND toCid = :peer) OR (fromCid = :peer AND toCid = :me)"]
    params: dict[str, Any] = {"me": me, "peer": peer, "limit": MAX_PAGE}
    if before:
        where.append("id < :before")
        params["before"] = int(before)
    rows = (
        await db.execute(
            text(
                "SELECT id, fromCid, toCid, body, createdAt, readAt FROM `DirectMessage` "
                f"WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT :limit"
            ),
            params,
        )
    ).all()
    items = [dict(r._mapping) for r in rows][::-1]
    # 打开会话即标记已读
    await db.execute(
        text("UPDATE `DirectMessage` SET readAt = NOW(3) WHERE toCid = :me AND fromCid = :peer AND readAt IS NULL"),
        {"me": me, "peer": peer},
    )
    await db.commit()
    names = await _names_for(db, [peer])
    return _ok(
        {
            "peerCid": peer,
            "peerName": (names.get(peer) or {}).get("username") or peer,
            "items": items,
        }
    )


@router.post("")
@router.post("/")
async def send_message(
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _fail(400, "请求体格式错误")
    to_cid = str((body or {}).get("toCid") or "").strip()
    content = str((body or {}).get("body") or "").strip()
    if not to_cid or not content:
        return _fail(400, "收件人与内容不能为空")
    if len(content) > MAX_BODY:
        return _fail(400, f"消息长度不能超过 {MAX_BODY} 字")
    me = str(current.cid)
    if to_cid == me:
        return _fail(400, "不能给自己发消息")
    target = await users_svc.find_user_public(db, to_cid)
    if not target:
        return _fail(404, "对方账号不存在")

    await db.execute(
        text(
            "INSERT INTO `DirectMessage` (`fromCid`, `toCid`, `body`) "
            "VALUES (:f, :t, :b)"
        ),
        {"f": me, "t": to_cid, "b": content},
    )
    await db.commit()

    # 收件人若正在连飞，顺带把消息送进游戏内（失败不影响站内消息落库）
    delivered_in_game = False
    try:
        clients = await fsd_console.list_clients()
        targets = [c for c in clients if str(c.get("cid")) == to_cid]
        from_name = (await users_svc.find_user_public(db, me) or {}).get("username") or me
        for c in targets[:1]:
            await fsd_console.say(str(c["callsign"]), f"[站内] {from_name}: {content}")
            delivered_in_game = True
    except Exception as exc:  # noqa: BLE001
        log.info("[messages] 游戏内投递跳过: %s", exc)

    return _ok({"deliveredInGame": delivered_in_game})


__all__ = ["router", "ensure_table", "MAX_BODY"]
