"""社区积分与虚拟商城。

设计要点：
- 只使用站内“积分”，不存在任何法定货币字段或兑换逻辑。
- 余额在既有 ``UserPoint.points`` 上扣减，兑换使用条件原子 UPDATE。
- 所有发放入账写入 ``point_transactions``，通过 (userId, kind, reference)
  唯一键保证活动/视频/时长结算幂等。
"""
from __future__ import annotations

import datetime as dt
import logging
import math
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("cwfly.community_points")

CONFIG_DEFAULTS: dict[str, str] = {
    "points_per_hour": "5",
    "activity_points": "50",
    "activity_min_hours": "10",
    "video_points": "100",
    "redeem_daily_limit": "3",
    "redeem_cooldown_seconds": "30",
}
ALLOWED_CONFIG = set(CONFIG_DEFAULTS)
NUMERIC_CONFIG = {
    "points_per_hour": "float",
    "activity_points": "int",
    "activity_min_hours": "float",
    "video_points": "int",
    "redeem_daily_limit": "int",
    "redeem_cooldown_seconds": "int",
}

DDL = [
    """
    CREATE TABLE IF NOT EXISTS `point_config` (
      `config_key` varchar(64) NOT NULL,
      `config_value` varchar(191) NOT NULL,
      `updatedAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
      PRIMARY KEY (`config_key`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `point_products` (
      `id` int NOT NULL AUTO_INCREMENT,
      `name` varchar(191) NOT NULL,
      `description` varchar(500) NOT NULL DEFAULT '',
      `icon` varchar(191) NOT NULL DEFAULT '✦',
      `price` int NOT NULL DEFAULT 0,
      `stock` int NOT NULL DEFAULT -1,
      `status` tinyint NOT NULL DEFAULT 1,
      `asset_type` varchar(32) NOT NULL DEFAULT 'virtual',
      `min_flight_hours` double NOT NULL DEFAULT 0,
      `sort_order` int NOT NULL DEFAULT 0,
      `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
      `updatedAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
      PRIMARY KEY (`id`),
      KEY `point_products_status_idx` (`status`, `sort_order`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `user_assets` (
      `id` bigint NOT NULL AUTO_INCREMENT,
      `userId` varchar(191) NOT NULL,
      `productId` int DEFAULT NULL,
      `asset_type` varchar(32) NOT NULL DEFAULT 'virtual',
      `name` varchar(191) NOT NULL,
      `icon` varchar(191) NOT NULL DEFAULT '✦',
      `quantity` int NOT NULL DEFAULT 1,
      `status` varchar(16) NOT NULL DEFAULT 'active',
      `source` varchar(32) NOT NULL DEFAULT 'redeem',
      `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
      PRIMARY KEY (`id`),
      KEY `user_assets_user_idx` (`userId`, `createdAt`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `point_transactions` (
      `id` bigint NOT NULL AUTO_INCREMENT,
      `userId` varchar(191) NOT NULL,
      `amount` int NOT NULL,
      `balanceAfter` int NOT NULL DEFAULT 0,
      `kind` varchar(32) NOT NULL,
      `reference` varchar(191) NOT NULL,
      `description` varchar(500) NOT NULL DEFAULT '',
      `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
      PRIMARY KEY (`id`),
      UNIQUE KEY `point_transactions_ref_key` (`userId`, `kind`, `reference`),
      KEY `point_transactions_user_idx` (`userId`, `createdAt`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `point_video_submissions` (
      `id` int NOT NULL AUTO_INCREMENT,
      `userId` varchar(191) NOT NULL,
      `title` varchar(191) NOT NULL,
      `url` varchar(500) NOT NULL,
      `status` varchar(16) NOT NULL DEFAULT 'pending',
      `reward` int NOT NULL DEFAULT 0,
      `reviewNote` varchar(500) NOT NULL DEFAULT '',
      `reviewer` varchar(191) NOT NULL DEFAULT '',
      `createdAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
      `reviewedAt` datetime(3) DEFAULT NULL,
      PRIMARY KEY (`id`),
      KEY `point_videos_status_idx` (`status`, `createdAt`),
      KEY `point_videos_user_idx` (`userId`, `createdAt`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `point_hour_settlements` (
      `userId` varchar(191) NOT NULL,
      `settledHours` double NOT NULL DEFAULT 0,
      `updatedAt` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
      PRIMARY KEY (`userId`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]

class ShopError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def ensure_schema(db: AsyncSession) -> None:
    """启动时建表并写入默认规则；商品库保持为空，由管理员自行创建。"""
    for ddl in DDL:
        await db.execute(text(ddl))
    for key, value in CONFIG_DEFAULTS.items():
        await db.execute(
            text(
                "INSERT IGNORE INTO `point_config` (config_key, config_value) "
                "VALUES (:k, :v)"
            ),
            {"k": key, "v": value},
        )
    col = (
        await db.execute(
            text(
                "SELECT COUNT(*) AS c FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'point_products' "
                "AND column_name = 'min_flight_hours'"
            )
        )
    ).first()
    if col is not None and int(col._mapping["c"] or 0) == 0:
        await db.execute(
            text(
                "ALTER TABLE `point_products` "
                "ADD COLUMN `min_flight_hours` double NOT NULL DEFAULT 0"
            )
        )
    await db.commit()


async def get_config(db: AsyncSession) -> dict[str, str]:
    rows = (await db.execute(text("SELECT config_key, config_value FROM `point_config`"))).all()
    out = dict(CONFIG_DEFAULTS)
    for row in rows:
        key = str(row._mapping["config_key"])
        if key in out:
            out[key] = str(row._mapping["config_value"])
    return out


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


async def get_balance(db: AsyncSession, cid: str) -> int:
    row = (
        await db.execute(
            text("SELECT points FROM `UserPoint` WHERE userId = :uid LIMIT 1"),
            {"uid": cid},
        )
    ).first()
    return _int(row._mapping["points"]) if row else 0


async def get_total_hours(db: AsyncSession, cid: str) -> float:
    """常旅客累计飞行时长（小时），来自现有 UserPoint.hours。"""
    row = (
        await db.execute(
            text("SELECT hours FROM `UserPoint` WHERE userId = :uid LIMIT 1"),
            {"uid": cid},
        )
    ).first()
    return _float(row._mapping["hours"]) if row else 0.0


async def list_products(db: AsyncSession, only_active: bool = True) -> list[dict[str, Any]]:
    where = "WHERE status = 1" if only_active else ""
    rows = (
        await db.execute(
            text(
                "SELECT id, name, description, icon, price, stock, status, "
                "asset_type, min_flight_hours, sort_order FROM `point_products` "
                f"{where} ORDER BY sort_order ASC, id ASC"
            )
        )
    ).all()
    out: list[dict[str, Any]] = []
    for row in rows:
        m = row._mapping
        stock = _int(m["stock"], -1)
        out.append(
            {
                "id": _int(m["id"]),
                "name": m["name"],
                "description": m["description"] or "",
                "icon": m["icon"] or "✦",
                "price": _int(m["price"]),
                "stock": stock,
                "unlimited": stock < 0,
                "status": _int(m["status"]),
                "assetType": m["asset_type"] or "virtual",
                "minFlightHours": _float(m["min_flight_hours"]),
                "sortOrder": _int(m["sort_order"]),
            }
        )
    return out


async def shop_overview(db: AsyncSession, cid: str) -> dict[str, Any]:
    balance = await get_balance(db, cid)
    total_hours = await get_total_hours(db, cid)
    products = await list_products(db, only_active=True)
    config = await get_config(db)
    return {
        "balance": balance,
        "totalHours": total_hours,
        "products": products,
        "rates": {
            "pointsPerHour": _float(config["points_per_hour"]),
            "activityPoints": _int(config["activity_points"]),
            "activityMinHours": _float(config["activity_min_hours"]),
            "videoPoints": _int(config["video_points"]),
        },
    }


async def list_transactions(db: AsyncSession, cid: str, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    rows = (
        await db.execute(
            text(
                "SELECT id, amount, balanceAfter, kind, reference, description, createdAt "
                "FROM `point_transactions` WHERE userId = :uid "
                "ORDER BY id DESC LIMIT :limit"
            ),
            {"uid": cid, "limit": limit},
        )
    ).all()
    return [
        {
            "id": _int(r._mapping["id"]),
            "amount": _int(r._mapping["amount"]),
            "balanceAfter": _int(r._mapping["balanceAfter"]),
            "kind": r._mapping["kind"],
            "reference": r._mapping["reference"],
            "description": r._mapping["description"] or "",
            "createdAt": r._mapping["createdAt"],
        }
        for r in rows
    ]


async def list_assets(db: AsyncSession, cid: str) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            text(
                "SELECT id, productId, asset_type, name, icon, quantity, status, "
                "source, createdAt FROM `user_assets` WHERE userId = :uid "
                "ORDER BY id DESC"
            ),
            {"uid": cid},
        )
    ).all()
    return [
        {
            "id": _int(r._mapping["id"]),
            "productId": _int(r._mapping["productId"]) if r._mapping["productId"] is not None else None,
            "assetType": r._mapping["asset_type"],
            "name": r._mapping["name"],
            "icon": r._mapping["icon"] or "✦",
            "quantity": _int(r._mapping["quantity"], 1),
            "status": r._mapping["status"],
            "source": r._mapping["source"],
            "createdAt": r._mapping["createdAt"],
        }
        for r in rows
    ]


async def _award_in_tx(
    db: AsyncSession,
    cid: str,
    amount: int,
    kind: str,
    reference: str,
    description: str,
) -> bool:
    """在调用方事务内幂等加分；重复 reference 返回 False。"""
    if amount <= 0:
        return False
    inserted = await db.execute(
        text(
            "INSERT IGNORE INTO `point_transactions` "
            "(userId, amount, balanceAfter, kind, reference, description) "
            "VALUES (:uid, :amount, 0, :kind, :ref, :desc)"
        ),
        {"uid": cid, "amount": amount, "kind": kind, "ref": reference, "desc": description},
    )
    if int(inserted.rowcount or 0) != 1:
        return False
    await db.execute(
        text(
            "INSERT INTO `UserPoint` (userId, points, exp, level, flights, hours) "
            "VALUES (:uid, :amount, 0, 1, 0, 0) "
            "ON DUPLICATE KEY UPDATE points = points + :amount, updatedAt = NOW(3)"
        ),
        {"uid": cid, "amount": amount},
    )
    row = (
        await db.execute(
            text("SELECT points FROM `UserPoint` WHERE userId = :uid LIMIT 1"),
            {"uid": cid},
        )
    ).first()
    balance = _int(row._mapping["points"]) if row else amount
    await db.execute(
        text(
            "UPDATE `point_transactions` SET balanceAfter = :balance "
            "WHERE userId = :uid AND kind = :kind AND reference = :ref"
        ),
        {"balance": balance, "uid": cid, "kind": kind, "ref": reference},
    )
    return True


async def redeem(db: AsyncSession, cid: str, product_id: int) -> dict[str, Any]:
    """事务 + 行锁 + 条件原子扣减；失败抛 ShopError。"""
    try:
        pid = int(product_id)
    except (TypeError, ValueError):
        raise ShopError("商品参数错误")

    await db.rollback()
    async with db.begin():
        config = await get_config(db)
        daily_limit = max(0, _int(config["redeem_daily_limit"]))
        cooldown = max(0, _int(config["redeem_cooldown_seconds"]))

        product = (
            await db.execute(
                text(
                    "SELECT id, name, description, icon, price, stock, status, asset_type, "
                    "min_flight_hours FROM `point_products` WHERE id = :id FOR UPDATE"
                ),
                {"id": pid},
            )
        ).first()
        if product is None:
            raise ShopError("商品不存在", 404)
        m = product._mapping
        if _int(m["status"]) != 1:
            raise ShopError("商品已下架", 409)
        price = _int(m["price"])
        if price <= 0:
            raise ShopError("商品积分配置错误", 400)
        required_hours = _float(m["min_flight_hours"])
        user_hours_row = (
            await db.execute(
                text(
                    "SELECT hours FROM `UserPoint` WHERE userId = :uid LIMIT 1 FOR UPDATE"
                ),
                {"uid": cid},
            )
        ).first()
        user_hours = _float(user_hours_row._mapping["hours"]) if user_hours_row else 0.0
        if user_hours < required_hours:
            raise ShopError(f"需飞行 {required_hours:g} 小时解锁", 403)

        if daily_limit:
            quota = (
                await db.execute(
                    text(
                        "SELECT COUNT(*) AS cnt FROM `point_transactions` "
                        "WHERE userId = :uid AND kind = 'redeem' AND DATE(createdAt) = CURDATE()"
                    ),
                    {"uid": cid},
                )
            ).first()
            if quota is not None and _int(quota._mapping["cnt"]) >= daily_limit:
                raise ShopError("今日兑换次数已达上限，请明天再试", 429)

        if cooldown:
            recent = (
                await db.execute(
                    text(
                        "SELECT TIMESTAMPDIFF(SECOND, MAX(createdAt), NOW(3)) AS ago "
                        "FROM `point_transactions` "
                        "WHERE userId = :uid AND kind = 'redeem'"
                    ),
                    {"uid": cid},
                )
            ).first()
            if recent is not None and recent._mapping["ago"] is not None:
                if _int(recent._mapping["ago"]) < cooldown:
                    raise ShopError(
                        f"兑换操作过于频繁，请 {cooldown - _int(recent._mapping['ago'])} 秒后再试",
                        429,
                    )

        stock = _int(m["stock"], -1)
        if stock >= 0:
            stock_update = await db.execute(
                text(
                    "UPDATE `point_products` SET stock = stock - 1, updatedAt = NOW(3) "
                    "WHERE id = :id AND status = 1 AND stock > 0"
                ),
                {"id": pid},
            )
            if int(stock_update.rowcount or 0) != 1:
                raise ShopError("商品库存不足", 409)

        debit = await db.execute(
            text(
                "UPDATE `UserPoint` SET points = points - :price, updatedAt = NOW(3) "
                "WHERE userId = :uid AND points >= :price"
            ),
            {"price": price, "uid": cid},
        )
        if int(debit.rowcount or 0) != 1:
            raise ShopError("积分不足", 409)

        balance_row = (
            await db.execute(
                text("SELECT points FROM `UserPoint` WHERE userId = :uid LIMIT 1"),
                {"uid": cid},
            )
        ).first()
        balance = _int(balance_row._mapping["points"]) if balance_row else 0
        reference = f"redeem:{uuid.uuid4().hex}"
        await db.execute(
            text(
                "INSERT INTO `point_transactions` "
                "(userId, amount, balanceAfter, kind, reference, description) "
                "VALUES (:uid, :amount, :balance, 'redeem', :ref, :desc)"
            ),
            {
                "uid": cid,
                "amount": -price,
                "balance": balance,
                "ref": reference,
                "desc": f"兑换商品：{m['name']}",
            },
        )
        await db.execute(
            text(
                "INSERT INTO `user_assets` "
                "(userId, productId, asset_type, name, icon, quantity, status, source) "
                "VALUES (:uid, :pid, :type, :name, :icon, 1, 'active', 'redeem')"
            ),
            {
                "uid": cid,
                "pid": pid,
                "type": m["asset_type"] or "virtual",
                "name": m["name"],
                "icon": m["icon"] or "✦",
            },
        )
        return {
            "balance": balance,
            "product": {
                "id": pid,
                "name": m["name"],
                "icon": m["icon"] or "✦",
            },
        }


async def submit_video(db: AsyncSession, cid: str, title: str, url: str) -> dict[str, Any]:
    title = str(title or "").strip()
    url = str(url or "").strip()
    if not title or len(title) > 120:
        raise ShopError("请填写 1-120 字的作品标题")
    if not (url.startswith("https://") or url.startswith("http://")) or len(url) > 500:
        raise ShopError("请填写有效的作品链接")
    result = await db.execute(
        text(
            "INSERT INTO `point_video_submissions` (userId, title, url) "
            "VALUES (:uid, :title, :url)"
        ),
        {"uid": cid, "title": title, "url": url},
    )
    await db.commit()
    return {"id": int(result.lastrowid or 0), "status": "pending"}


async def list_user_videos(db: AsyncSession, cid: str) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            text(
                "SELECT id, title, url, status, reward, reviewNote, createdAt, reviewedAt "
                "FROM `point_video_submissions` WHERE userId = :uid ORDER BY id DESC"
            ),
            {"uid": cid},
        )
    ).all()
    return [
        {
            "id": _int(r._mapping["id"]),
            "title": r._mapping["title"],
            "url": r._mapping["url"],
            "status": r._mapping["status"],
            "reward": _int(r._mapping["reward"]),
            "reviewNote": r._mapping["reviewNote"] or "",
            "createdAt": r._mapping["createdAt"],
            "reviewedAt": r._mapping["reviewedAt"],
        }
        for r in rows
    ]


async def _settle_event_user(db: AsyncSession, cid: str, event_id: int, amount: int, min_hours: float) -> str:
    await db.rollback()
    async with db.begin():
        point = (
            await db.execute(
                text(
                    "SELECT hours FROM `UserPoint` WHERE userId = :uid LIMIT 1 FOR UPDATE"
                ),
                {"uid": cid},
            )
        ).first()
        hours = _float(point._mapping["hours"]) if point else 0.0
        if hours < min_hours:
            return "below_hours"
        awarded = await _award_in_tx(
            db,
            cid,
            amount,
            "activity",
            f"event:{event_id}",
            f"参加活动 #{event_id} 的积分结算",
        )
        return "awarded" if awarded else "already_settled"


async def settle_event(db: AsyncSession, event_id: int) -> dict[str, Any]:
    event_exists = (
        await db.execute(text("SELECT id FROM `Event` WHERE id = :id LIMIT 1"), {"id": event_id})
    ).first()
    if event_exists is None:
        raise ShopError("活动不存在", 404)
    config = await get_config(db)
    amount = _int(config["activity_points"])
    min_hours = _float(config["activity_min_hours"])
    rows = (
        await db.execute(
            text(
                "SELECT DISTINCT userId FROM `EventRegistration` "
                "WHERE eventId = :id AND status <> 'cancelled'"
            ),
            {"id": event_id},
        )
    ).all()
    users = [str(r._mapping["userId"]) for r in rows]
    awarded = below = duplicate = 0
    for cid in users:
        result = await _settle_event_user(db, cid, event_id, amount, min_hours)
        if result == "awarded":
            awarded += 1
        elif result == "below_hours":
            below += 1
        else:
            duplicate += 1
    return {
        "eventId": event_id,
        "total": len(users),
        "awarded": awarded,
        "belowHours": below,
        "duplicate": duplicate,
        "minHours": min_hours,
        "points": amount,
    }


async def settle_hours(db: AsyncSession, cid: str | None = None) -> dict[str, Any]:
    config = await get_config(db)
    rate = _float(config["points_per_hour"])
    params: dict[str, Any] = {}
    where = ""
    if cid:
        where = "WHERE userId = :uid"
        params["uid"] = cid
    rows = (
        await db.execute(
            text(f"SELECT userId, hours FROM `UserPoint` {where} ORDER BY userId"), params
        )
    ).all()
    awarded_users = 0
    awarded_points = 0
    for row in rows:
        user_id = str(row._mapping["userId"])
        hours = _float(row._mapping["hours"])
        await db.rollback()
        async with db.begin():
            point = (
                await db.execute(
                    text("SELECT hours FROM `UserPoint` WHERE userId = :uid FOR UPDATE"),
                    {"uid": user_id},
                )
            ).first()
            if point is None:
                continue
            current_hours = _float(point._mapping["hours"])
            settled_row = (
                await db.execute(
                    text(
                        "SELECT settledHours FROM `point_hour_settlements` "
                        "WHERE userId = :uid FOR UPDATE"
                    ),
                    {"uid": user_id},
                )
            ).first()
            settled = _float(settled_row._mapping["settledHours"]) if settled_row else 0.0
            delta = max(0.0, current_hours - settled)
            amount = int(math.floor(delta * rate + 1e-9))
            if amount <= 0:
                continue
            ok = await _award_in_tx(
                db,
                user_id,
                amount,
                "flight_hours",
                f"hours:{current_hours:.4f}",
                f"飞行时长结算 {delta:.2f} 小时",
            )
            if not ok:
                continue
            await db.execute(
                text(
                    "INSERT INTO `point_hour_settlements` (userId, settledHours) "
                    "VALUES (:uid, :hours) ON DUPLICATE KEY UPDATE "
                    "settledHours = VALUES(settledHours), updatedAt = NOW(3)"
                ),
                {"uid": user_id, "hours": current_hours},
            )
            awarded_users += 1
            awarded_points += amount
    return {"users": awarded_users, "points": awarded_points, "rate": rate}


async def admin_list_products(db: AsyncSession) -> list[dict[str, Any]]:
    return await list_products(db, only_active=False)


async def admin_save_product(db: AsyncSession, data: dict[str, Any], product_id: int | None = None) -> dict[str, Any]:
    name = str(data.get("name") or "").strip()
    description = str(data.get("description") or "").strip()
    icon = str(data.get("icon") or "✦").strip()[:32] or "✦"
    asset_type = str(data.get("assetType") or data.get("asset_type") or "virtual").strip()[:32]
    if not name or len(name) > 120:
        raise ShopError("商品名称需为 1-120 字")
    price = _int(data.get("price"))
    if price <= 0:
        raise ShopError("所需积分必须大于 0")
    stock = _int(data.get("stock"), -1)
    if stock < -1:
        stock = -1
    status = 1 if _int(data.get("status"), 1) != 0 else 0
    min_flight_hours = _float(
        data.get("minFlightHours", data.get("min_flight_hours", 0)), 0.0
    )
    if min_flight_hours < 0:
        raise ShopError("解锁所需飞行时长不能为负数")
    sort_order = _int(data.get("sortOrder") or data.get("sort_order"), 0)
    if product_id is None:
        result = await db.execute(
            text(
                "INSERT INTO `point_products` "
                "(name, description, icon, price, stock, status, asset_type, "
                "min_flight_hours, sort_order) "
                "VALUES (:name, :desc, :icon, :price, :stock, :status, :type, "
                ":min_hours, :sort)"
            ),
            {
                "name": name,
                "desc": description,
                "icon": icon,
                "price": price,
                "stock": stock,
                "status": status,
                "type": asset_type,
                "min_hours": min_flight_hours,
                "sort": sort_order,
            },
        )
        await db.commit()
        return {"id": int(result.lastrowid or 0)}
    exists = (
        await db.execute(
            text("SELECT id FROM `point_products` WHERE id = :id LIMIT 1"),
            {"id": product_id},
        )
    ).first()
    if exists is None:
        raise ShopError("商品不存在", 404)
    await db.execute(
        text(
            "UPDATE `point_products` SET name = :name, description = :desc, icon = :icon, "
            "price = :price, stock = :stock, status = :status, asset_type = :type, "
            "min_flight_hours = :min_hours, sort_order = :sort, updatedAt = NOW(3) WHERE id = :id"
        ),
        {
            "name": name,
            "desc": description,
            "icon": icon,
            "price": price,
            "stock": stock,
            "status": status,
            "type": asset_type,
            "min_hours": min_flight_hours,
            "sort": sort_order,
            "id": product_id,
        },
    )
    await db.commit()
    return {"id": product_id}


async def admin_delete_product(db: AsyncSession, product_id: int) -> None:
    exists = (
        await db.execute(
            text("SELECT id FROM `point_products` WHERE id = :id LIMIT 1"),
            {"id": product_id},
        )
    ).first()
    if exists is None:
        raise ShopError("商品不存在", 404)
    await db.execute(text("DELETE FROM `point_products` WHERE id = :id"), {"id": product_id})
    await db.commit()


async def admin_list_transactions(
    db: AsyncSession,
    user_id: str | None = None,
    kind: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """积分流水审计：可按用户 CID / 类型过滤，返回变动原因与变动后余额。"""
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": max(1, min(int(limit), 200)), "offset": max(0, int(offset))}
    if user_id:
        clauses.append("t.userId = :uid")
        params["uid"] = user_id
    if kind:
        clauses.append("t.kind = :kind")
        params["kind"] = kind
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = (
        await db.execute(
            text(
                "SELECT t.id, t.userId, u.username, t.amount, t.balanceAfter, t.kind, "
                "t.reference, t.description, t.createdAt "
                "FROM `point_transactions` t LEFT JOIN `User` u ON u.cid = t.userId "
                f"{where} ORDER BY t.id DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
    ).all()
    return [
        {
            "id": _int(r._mapping["id"]),
            "userId": r._mapping["userId"],
            "username": r._mapping["username"] or "",
            "amount": _int(r._mapping["amount"]),
            "balanceAfter": _int(r._mapping["balanceAfter"]),
            "kind": r._mapping["kind"],
            "reference": r._mapping["reference"],
            "description": r._mapping["description"] or "",
            "createdAt": r._mapping["createdAt"],
        }
        for r in rows
    ]


async def list_videos(db: AsyncSession, status: str | None = None) -> list[dict[str, Any]]:
    where = "WHERE status = :status" if status else ""
    params = {"status": status} if status else {}
    rows = (
        await db.execute(
            text(
                "SELECT id, userId, title, url, status, reward, reviewNote, reviewer, "
                "createdAt, reviewedAt FROM `point_video_submissions` "
                f"{where} ORDER BY id DESC LIMIT 200"
            ),
            params,
        )
    ).all()
    return [
        {
            "id": _int(r._mapping["id"]),
            "userId": r._mapping["userId"],
            "title": r._mapping["title"],
            "url": r._mapping["url"],
            "status": r._mapping["status"],
            "reward": _int(r._mapping["reward"]),
            "reviewNote": r._mapping["reviewNote"] or "",
            "reviewer": r._mapping["reviewer"] or "",
            "createdAt": r._mapping["createdAt"],
            "reviewedAt": r._mapping["reviewedAt"],
        }
        for r in rows
    ]


async def review_video(db: AsyncSession, video_id: int, status: str, reward: int, reviewer: str, note: str = "") -> dict[str, Any]:
    if status not in ("approved", "rejected"):
        raise ShopError("审核状态错误")
    config = await get_config(db)
    reward = reward if reward > 0 else _int(config["video_points"])
    await db.rollback()
    async with db.begin():
        row = (
            await db.execute(
                text(
                    "SELECT id, userId, title, status FROM `point_video_submissions` "
                    "WHERE id = :id FOR UPDATE"
                ),
                {"id": video_id},
            )
        ).first()
        if row is None:
            raise ShopError("作品不存在", 404)
        if row._mapping["status"] != "pending":
            raise ShopError("该作品已审核", 409)
        user_id = str(row._mapping["userId"])
        await db.execute(
            text(
                "UPDATE `point_video_submissions` SET status = :status, reward = :reward, "
                "reviewNote = :note, reviewer = :reviewer, reviewedAt = NOW(3) "
                "WHERE id = :id"
            ),
            {
                "status": status,
                "reward": reward if status == "approved" else 0,
                "note": str(note or "")[:500],
                "reviewer": reviewer,
                "id": video_id,
            },
        )
        awarded = False
        if status == "approved" and reward > 0:
            awarded = await _award_in_tx(
                db,
                user_id,
                reward,
                "video",
                f"video:{video_id}",
                f"宣传作品审核通过：{row._mapping['title']}",
            )
        return {"id": video_id, "approved": status == "approved", "awarded": awarded, "reward": reward}


async def update_config(db: AsyncSession, updates: dict[str, Any]) -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, value in updates.items():
        if key not in ALLOWED_CONFIG:
            continue
        kind = NUMERIC_CONFIG[key]
        try:
            num = float(value)
        except (TypeError, ValueError):
            raise ShopError(f"{key} 必须是数字")
        if num < 0:
            raise ShopError(f"{key} 不能为负数")
        clean[key] = str(int(num)) if kind == "int" else str(num)
    if not clean:
        raise ShopError("没有可更新的配置")
    for key, value in clean.items():
        await db.execute(
            text(
                "INSERT INTO `point_config` (config_key, config_value) VALUES (:k, :v) "
                "ON DUPLICATE KEY UPDATE config_value = VALUES(config_value), updatedAt = NOW(3)"
            ),
            {"k": key, "v": value},
        )
    await db.commit()
    return await get_config(db)


__all__ = [
    "ShopError",
    "CONFIG_DEFAULTS",
    "ensure_schema",
    "get_config",
    "get_balance",
    "get_total_hours",
    "shop_overview",
    "list_products",
    "list_transactions",
    "list_assets",
    "redeem",
    "submit_video",
    "list_user_videos",
    "settle_event",
    "settle_hours",
    "admin_list_products",
    "admin_save_product",
    "admin_delete_product",
    "admin_list_transactions",
    "list_videos",
    "review_video",
    "update_config",
]
