"""个人中心「已授权应用」：查看 / 取消第三方（Dubhe Nexus 等）的账号授权。

- GET    /api/user/oauth/apps        当前用户已授权的应用列表
- DELETE /api/user/oauth/apps/{id}   取消授权（吊销该应用在本账号下的全部令牌）

鉴权：全部取自会话 Cookie / Bearer 里的 `cid`，不接受前端传入用户标识，
因此「只能查看和取消自己的授权」由服务端保证。
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, get_verified_user
from app.services import oauth2 as oauth
from app.utils.json_compat import JSJSONResponse

router = APIRouter(prefix="/user/oauth", tags=["user-oauth"])
log = logging.getLogger("cwfly.user_oauth")

MESSAGE_OPERATION_FAILED = "操作失败，请稍后重试"


def _ok(data: Any = None, message: str | None = None) -> JSJSONResponse:
    body: dict[str, Any] = {"success": True}
    if data is not None:
        body["data"] = data
    if message is not None:
        body["message"] = message
    return JSJSONResponse(body)


def _fail(status_code: int, message: str) -> JSJSONResponse:
    return JSJSONResponse({"success": False, "message": message}, status_code=status_code)


@router.get("/apps")
async def list_authorized_apps(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        apps = await oauth.list_authorized_apps(db, current.cid)
        return _ok(apps)
    except Exception as exc:  # noqa: BLE001
        log.error("[user_oauth] 读取已授权应用失败: %s", exc)
        return _fail(500, MESSAGE_OPERATION_FAILED)


@router.delete("/apps/{app_id}")
async def revoke_authorized_app(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_verified_user),
) -> JSJSONResponse:
    """取消授权。`get_verified_user` 每请求查库，封禁/注销后立即拒绝。"""
    client_id = (app_id or "").strip()
    if not client_id:
        return _fail(400, "缺少应用标识")
    registered = {item["id"] for item in oauth.registered_apps()}
    if client_id not in registered:
        return _fail(404, "应用不存在或未登记")
    app_name = oauth._app_meta(client_id)["name"]

    try:
        revoked = await oauth.revoke_app(db, current.cid, client_id)
    except Exception as exc:  # noqa: BLE001
        log.error("[user_oauth] 取消授权失败 cid=%s app=%s: %s", current.cid, client_id, exc)
        return _fail(500, MESSAGE_OPERATION_FAILED)

    log.info("[user_oauth] 取消授权 cid=%s app=%s rows=%s", current.cid, client_id, revoked)
    return _ok({"appId": client_id, "revoked": revoked}, f"已取消对「{app_name}」的授权")


__all__ = ["router"]
