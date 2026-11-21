"""/api/admin/points 管理端接口（积分配置、商品、宣传视频、结算）。"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_permission
from app.services import community_points as cp
from app.utils.json_compat import JSJSONResponse

log = logging.getLogger("cwfly.admin_points")
router = APIRouter(prefix="/admin/points", tags=["admin-points"])
_admin = Depends(require_permission("user"))


def _ok(data: Any = None, message: str | None = None) -> JSJSONResponse:
    body: dict[str, Any] = {"success": True}
    if data is not None:
        body["data"] = data
    if message:
        body["message"] = message
    return JSJSONResponse(body)


def _fail(status_code: int, message: str) -> JSJSONResponse:
    return JSJSONResponse({"success": False, "message": message}, status_code=status_code)


async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


@router.get("/config")
async def get_config(
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = _admin,
) -> JSJSONResponse:
    try:
        return _ok(await cp.get_config(db))
    except Exception as exc:  # noqa: BLE001
        log.error("[admin_points.py] config get: %s", exc)
        return _fail(500, "操作失败")


@router.put("/config")
async def update_config(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = _admin,
) -> JSJSONResponse:
    try:
        data = await _body(request)
        return _ok(await cp.update_config(db, data), "配置已保存")
    except cp.ShopError as exc:
        return _fail(exc.status_code, exc.message)
    except Exception as exc:  # noqa: BLE001
        log.error("[admin_points.py] config update: %s", exc)
        return _fail(500, "操作失败")


@router.get("/products")
async def list_products(
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = _admin,
) -> JSJSONResponse:
    try:
        return _ok(await cp.admin_list_products(db))
    except Exception as exc:  # noqa: BLE001
        log.error("[admin_points.py] products: %s", exc)
        return _fail(500, "操作失败")


@router.post("/products")
async def create_product(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = _admin,
) -> JSJSONResponse:
    try:
        result = await cp.admin_save_product(db, await _body(request))
        return _ok(result, "商品已创建")
    except cp.ShopError as exc:
        return _fail(exc.status_code, exc.message)
    except Exception as exc:  # noqa: BLE001
        log.error("[admin_points.py] product create: %s", exc)
        return _fail(500, "操作失败")


@router.put("/products/{product_id}")
async def update_product(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = _admin,
) -> JSJSONResponse:
    try:
        result = await cp.admin_save_product(db, await _body(request), product_id)
        return _ok(result, "商品已更新")
    except cp.ShopError as exc:
        return _fail(exc.status_code, exc.message)
    except Exception as exc:  # noqa: BLE001
        log.error("[admin_points.py] product update: %s", exc)
        return _fail(500, "操作失败")


@router.get("/videos")
async def list_videos(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = _admin,
) -> JSJSONResponse:
    try:
        return _ok(await cp.list_videos(db, status))
    except Exception as exc:  # noqa: BLE001
        log.error("[admin_points.py] videos: %s", exc)
        return _fail(500, "操作失败")


@router.post("/videos/{video_id}/review")
async def review_video(
    video_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = _admin,
) -> JSJSONResponse:
    try:
        data = await _body(request)
        result = await cp.review_video(
            db,
            video_id,
            str(data.get("status") or ""),
            int(data.get("reward") or 0),
            admin.cid,
            str(data.get("note") or ""),
        )
        return _ok(result, "审核完成")
    except cp.ShopError as exc:
        return _fail(exc.status_code, exc.message)
    except Exception as exc:  # noqa: BLE001
        log.error("[admin_points.py] video review: %s", exc)
        return _fail(500, "操作失败")


@router.post("/events/{event_id}/settle")
async def settle_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = _admin,
) -> JSJSONResponse:
    try:
        return _ok(await cp.settle_event(db, event_id), "活动积分结算完成")
    except cp.ShopError as exc:
        return _fail(exc.status_code, exc.message)
    except Exception as exc:  # noqa: BLE001
        log.error("[admin_points.py] event settle: %s", exc)
        return _fail(500, "操作失败")


@router.post("/hours/settle")
async def settle_hours(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = _admin,
) -> JSJSONResponse:
    try:
        data = await _body(request)
        cid = str(data.get("cid") or "").strip() or None
        return _ok(await cp.settle_hours(db, cid), "飞行时长积分结算完成")
    except cp.ShopError as exc:
        return _fail(exc.status_code, exc.message)
    except Exception as exc:  # noqa: BLE001
        log.error("[admin_points.py] hours settle: %s", exc)
        return _fail(500, "操作失败")


__all__ = ["router"]
