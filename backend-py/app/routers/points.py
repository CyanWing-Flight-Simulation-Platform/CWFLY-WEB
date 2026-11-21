"""/api/points 路由（逐接口对齐 Node src/routes/points.js）。

Node 侧 ``router.use(authenticate)`` → 每个端点都带 ``Depends(get_current_user)``。
- GET /              我的积分（无记录时返回默认对象）+ 成就列表
- GET /leaderboard   积分榜（points desc，前 50）
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.services import community_points as cp
from app.services import points_service as ps
from app.utils.json_compat import JSJSONResponse

log = logging.getLogger("cwfly.points")
router = APIRouter(prefix="/points", tags=["points"])


def _ok(data: Any = None, **extra: Any) -> JSJSONResponse:
    body: dict[str, Any] = {"success": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return JSJSONResponse(body)


def _fail(status_code: int, message: str, **extra: Any) -> JSJSONResponse:
    body: dict[str, Any] = {"success": False, "message": message}
    body.update(extra)
    return JSJSONResponse(body, status_code=status_code)


@router.get("/leaderboard")
async def leaderboard(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        return _ok(await ps.leaderboard(db))
    except Exception as exc:  # noqa: BLE001
        log.error("[points.py] %s", exc)
        return _fail(500, "操作失败")


@router.get("/shop")
async def shop(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        return _ok(await cp.shop_overview(db, current.cid))
    except Exception as exc:  # noqa: BLE001
        log.error("[points.py] shop: %s", exc)
        return _fail(500, "操作失败")


@router.post("/shop/redeem")
async def shop_redeem(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        product_id = int((body or {}).get("productId") or 0)
        if product_id <= 0:
            return _fail(400, "请选择商品")
        result = await cp.redeem(db, current.cid, product_id)
        return _ok(result, message="兑换成功")
    except cp.ShopError as exc:
        return _fail(exc.status_code, exc.message)
    except Exception as exc:  # noqa: BLE001
        log.error("[points.py] redeem: %s", exc)
        return _fail(500, "操作失败")


@router.get("/transactions")
async def transactions(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        return _ok(await cp.list_transactions(db, current.cid, limit))
    except Exception as exc:  # noqa: BLE001
        log.error("[points.py] transactions: %s", exc)
        return _fail(500, "操作失败")


@router.get("/assets")
async def assets(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        return _ok(await cp.list_assets(db, current.cid))
    except Exception as exc:  # noqa: BLE001
        log.error("[points.py] assets: %s", exc)
        return _fail(500, "操作失败")


@router.get("/config")
async def public_config(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        cfg = await cp.get_config(db)
        return _ok(
            {
                "pointsPerHour": cfg["points_per_hour"],
                "activityPoints": cfg["activity_points"],
                "activityMinHours": cfg["activity_min_hours"],
                "videoPoints": cfg["video_points"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        log.error("[points.py] config: %s", exc)
        return _fail(500, "操作失败")


@router.get("/videos/mine")
async def my_videos(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        return _ok(await cp.list_user_videos(db, current.cid))
    except Exception as exc:  # noqa: BLE001
        log.error("[points.py] videos: %s", exc)
        return _fail(500, "操作失败")


@router.post("/videos")
async def submit_video(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        result = await cp.submit_video(
            db, current.cid, (body or {}).get("title"), (body or {}).get("url")
        )
        return _ok(result, message="已提交，等待审核")
    except cp.ShopError as exc:
        return _fail(exc.status_code, exc.message)
    except Exception as exc:  # noqa: BLE001
        log.error("[points.py] submit_video: %s", exc)
        return _fail(500, "操作失败")


@router.get("")
@router.get("/")
async def my_points(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        points = await ps.get_points(db, current.cid)
        if not points:
            points = ps.default_points(current.cid)
        achievements = await ps.list_achievements(db, current.cid)
        from app.services import community_points as cp

        total_hours = await cp.get_total_hours(db, current.cid)
        return _ok(
            {"points": points, "achievements": achievements, "user_total_hours": total_hours}
        )
    except Exception as exc:  # noqa: BLE001
        log.error("[points.py] %s", exc)
        return _fail(500, "操作失败")


__all__ = ["router"]
