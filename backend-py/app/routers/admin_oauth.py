"""/api/admin/oauth-clients  OAuth2 客户端注册表管理（管理员）。

- 环境变量内置客户端（Merak）只读展示，不可在此修改
- 数据库注册表客户端支持新增 / 改资料 / 轮换密钥 / 停用 / 删除
- 密钥仅在创建与轮换时返回一次（库里只存 sha256）
"""
from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.deps import CurrentUser, require_admin_access, require_permission
from app.services import oauth2 as oauth
from app.utils.json_compat import JSJSONResponse

log = logging.getLogger("cwfly.admin_oauth")

router = APIRouter(prefix="/admin/oauth-clients", tags=["admin-oauth"])

SCOPE_CHOICES = ["profile", "email", "qq", "openid"]


def _ok(data: Any = None, **extra: Any) -> JSJSONResponse:
    body: dict[str, Any] = {"success": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return JSJSONResponse(body)


def _fail(status_code: int, message: str) -> JSJSONResponse:
    return JSJSONResponse({"success": False, "message": message}, status_code=status_code)


def _normalize_uris(raw: Any) -> list[str]:
    if isinstance(raw, str):
        items = raw.splitlines()
    elif isinstance(raw, list):
        items = [str(x) for x in raw]
    else:
        return []
    out: list[str] = []
    for item in items:
        uri = str(item).strip()
        if not uri:
            continue
        if not (uri.startswith("https://") or uri.startswith("http://127.0.0.1") or uri.startswith("http://localhost")):
            raise ValueError(f"回调地址必须是 https（本地可用 http://127.0.0.1）：{uri}")
        if uri not in out:
            out.append(uri)
    return out


def _normalize_scopes(raw: Any) -> list[str]:
    if isinstance(raw, str):
        items = [s.strip() for s in raw.replace(",", " ").split()]
    elif isinstance(raw, list):
        items = [str(x).strip() for x in raw]
    else:
        items = []
    out = []
    for item in items:
        if not item:
            continue
        if item not in SCOPE_CHOICES:
            raise ValueError(f"不支持的 scope：{item}")
        if item not in out:
            out.append(item)
    return out or ["profile", "email", "openid"]


async def _rows(db: AsyncSession) -> list[dict[str, Any]]:
    result = (
        await db.execute(
            text(
                "SELECT client_id, name, homepage, redirect_uris, scopes, enabled, createdAt "
                "FROM `oauth2_clients` ORDER BY createdAt DESC"
            )
        )
    ).all()
    items = []
    for r in result:
        d = dict(r._mapping)
        items.append(
            {
                "clientId": d["client_id"],
                "name": d.get("name") or "",
                "homepage": d.get("homepage") or "",
                "redirectUris": [u for u in str(d.get("redirect_uris") or "").splitlines() if u],
                "scopes": [s for s in str(d.get("scopes") or "").split(",") if s],
                "enabled": bool(int(d.get("enabled") or 0)),
                "createdAt": str(d.get("createdAt") or ""),
                "source": "db",
                "editable": True,
            }
        )
    env = oauth._env_client()
    if env:
        items.insert(
            0,
            {
                "clientId": env["id"],
                "name": env["name"],
                "homepage": env["homepage"],
                "redirectUris": env["redirectUris"],
                "scopes": env["scopes"],
                "enabled": True,
                "createdAt": "",
                "source": "env",
                "editable": False,
            },
        )
    return items


@router.get("")
@router.get("/")
async def list_clients(
    _admin: CurrentUser = Depends(require_admin_access),
    _perm: CurrentUser = Depends(require_permission("user")),
    db: AsyncSession = Depends(get_db),
) -> JSJSONResponse:
    await oauth.ensure_clients_schema(db)
    return _ok({"items": await _rows(db), "scopeChoices": SCOPE_CHOICES})


@router.post("")
async def create_client(
    request: Request,
    _admin: CurrentUser = Depends(require_admin_access),
    _perm: CurrentUser = Depends(require_permission("user")),
    db: AsyncSession = Depends(get_db),
) -> JSJSONResponse:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _fail(400, "请求体格式错误")
    name = str((body or {}).get("name") or "").strip()
    if not name:
        return _fail(400, "应用名称不能为空")
    try:
        uris = _normalize_uris((body or {}).get("redirectUris"))
        scopes = _normalize_scopes((body or {}).get("scopes"))
    except ValueError as exc:
        return _fail(400, str(exc))
    if not uris:
        return _fail(400, "至少填写一个回调地址")
    homepage = str((body or {}).get("homepage") or "").strip()
    client_id = "cwf_" + secrets.token_hex(8)
    client_secret = secrets.token_urlsafe(32)
    await oauth.ensure_clients_schema(db)
    await db.execute(
        text(
            "INSERT INTO `oauth2_clients` (client_id, secret_hash, name, homepage, redirect_uris, scopes) "
            "VALUES (:i, :h, :n, :hp, :u, :s)"
        ),
        {
            "i": client_id,
            "h": oauth.hash_client_secret(client_secret),
            "n": name,
            "hp": homepage,
            "u": "\n".join(uris),
            "s": ",".join(scopes),
        },
    )
    await db.commit()
    log.warning("[admin_oauth] %s 创建 OAuth 客户端 %s", _admin.cid, client_id)
    return _ok(
        {
            "clientId": client_id,
            "clientSecret": client_secret,
            "name": name,
            "redirectUris": uris,
            "scopes": scopes,
        }
    )


@router.patch("/{client_id}")
async def update_client(
    client_id: str,
    request: Request,
    _admin: CurrentUser = Depends(require_admin_access),
    _perm: CurrentUser = Depends(require_permission("user")),
    db: AsyncSession = Depends(get_db),
) -> JSJSONResponse:
    target = str(client_id or "").strip()
    env = oauth._env_client()
    if env and env["id"] == target:
        return _fail(400, "内置客户端由环境变量管理，不能在此修改")
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _fail(400, "请求体格式错误")
    body = body or {}
    fields: list[str] = []
    params: dict[str, Any] = {"i": target}
    if "name" in body:
        name = str(body.get("name") or "").strip()
        if not name:
            return _fail(400, "应用名称不能为空")
        fields.append("`name` = :n")
        params["n"] = name
    if "homepage" in body:
        fields.append("`homepage` = :hp")
        params["hp"] = str(body.get("homepage") or "").strip()
    if "redirectUris" in body:
        try:
            uris = _normalize_uris(body.get("redirectUris"))
        except ValueError as exc:
            return _fail(400, str(exc))
        if not uris:
            return _fail(400, "至少保留一个回调地址")
        fields.append("`redirect_uris` = :u")
        params["u"] = "\n".join(uris)
    if "scopes" in body:
        try:
            scopes = _normalize_scopes(body.get("scopes"))
        except ValueError as exc:
            return _fail(400, str(exc))
        fields.append("`scopes` = :s")
        params["s"] = ",".join(scopes)
    if "enabled" in body:
        fields.append("`enabled` = :e")
        params["e"] = 1 if body.get("enabled") else 0
    if not fields:
        return _fail(400, "没有需要更新的字段")
    result = await db.execute(
        text(f"UPDATE `oauth2_clients` SET {', '.join(fields)} WHERE client_id = :i"),
        params,
    )
    await db.commit()
    if result.rowcount == 0:
        return _fail(404, "客户端不存在")
    log.warning("[admin_oauth] %s 更新 OAuth 客户端 %s", _admin.cid, target)
    return _ok({"clientId": target})


@router.post("/{client_id}/rotate")
async def rotate_secret(
    client_id: str,
    _admin: CurrentUser = Depends(require_admin_access),
    _perm: CurrentUser = Depends(require_permission("user")),
    db: AsyncSession = Depends(get_db),
) -> JSJSONResponse:
    target = str(client_id or "").strip()
    env = oauth._env_client()
    if env and env["id"] == target:
        return _fail(400, "内置客户端由环境变量管理，不能在此轮换密钥")
    new_secret = secrets.token_urlsafe(32)
    result = await db.execute(
        text("UPDATE `oauth2_clients` SET `secret_hash` = :h WHERE client_id = :i"),
        {"h": oauth.hash_client_secret(new_secret), "i": target},
    )
    await db.commit()
    if result.rowcount == 0:
        return _fail(404, "客户端不存在")
    log.warning("[admin_oauth] %s 轮换 OAuth 客户端密钥 %s", _admin.cid, target)
    return _ok({"clientId": target, "clientSecret": new_secret})


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    _admin: CurrentUser = Depends(require_admin_access),
    _perm: CurrentUser = Depends(require_permission("user")),
    db: AsyncSession = Depends(get_db),
) -> JSJSONResponse:
    target = str(client_id or "").strip()
    env = oauth._env_client()
    if env and env["id"] == target:
        return _fail(400, "内置客户端由环境变量管理，不能删除")
    result = await db.execute(text("DELETE FROM `oauth2_clients` WHERE client_id = :i"), {"i": target})
    await db.commit()
    if result.rowcount == 0:
        return _fail(404, "客户端不存在")
    log.warning("[admin_oauth] %s 删除 OAuth 客户端 %s", _admin.cid, target)
    return _ok({"clientId": target})
