"""OAuth2 授权服务器路由（挂载在 /api/oauth/*）。

对外提供：
- GET  /api/oauth/authorize  浏览器授权页（需已登录 CWFLY）
- POST /api/oauth/authorize  同意 / 拒绝（签名隐藏域保护）
- POST /api/oauth/token      授权码 / 刷新令牌换取 access_token
- GET  /api/oauth/userinfo   Bearer 读取用户资料
- POST /api/oauth/revoke     撤销授权
- GET  /api/oauth/health     运维自检（是否已配置）

第三方（Dubhe Nexus / Merak）只需要配置：
    authorize_url = https://www.cwflysim.cn/api/oauth/authorize
    token_url     = https://www.cwflysim.cn/api/oauth/token
    userinfo_url  = https://www.cwflysim.cn/api/oauth/userinfo
    client_id / client_secret / redirect_uri = 与 .env 中的 OAUTH2_* 一致
"""
from __future__ import annotations

import base64
import html
import json
import logging
from string import Template
from typing import Any, Optional
from urllib.parse import parse_qs, quote, unquote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.services import oauth2 as oauth
from app.services import users as users_service
from app.services.token import TokenError, TokenExpiredError, verify_token
from app.utils.session_cookie import access_token_from_request

router = APIRouter(prefix="/oauth", tags=["oauth2"])
log = logging.getLogger("cwfly.oauth2")

_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
def _json_error(status_code: int, error: str, description: str) -> JSONResponse:
    return JSONResponse(
        {"error": error, "error_description": description},
        status_code=status_code,
        headers=_NO_STORE,
    )


def _html(status_code: int, title: str, body: str) -> HTMLResponse:
    page = _PAGE_TEMPLATE.substitute(title=html.escape(title), body=body)
    return HTMLResponse(page, status_code=status_code, headers=_NO_STORE)


def _not_configured() -> Response:
    return _html(
        503,
        "OAuth2 未启用",
        "<p>CWFLY 尚未配置 OAuth2 客户端凭据（OAUTH2_CLIENT_ID / "
        "OAUTH2_CLIENT_SECRET / OAUTH2_REDIRECT_URIS）。</p>",
    )


def _session_user(request: Request) -> Optional[dict[str, Any]]:
    """读取 CWFLY 登录态（HttpOnly cookie 或 Bearer）。失败返回 None。"""
    token = access_token_from_request(request)
    if not token:
        header = request.headers.get("authorization") or ""
        if header.lower().startswith("bearer "):
            token = header[7:].strip()
    if not token:
        return None
    try:
        decoded = verify_token(token)
    except (TokenError, TokenExpiredError):
        return None
    cid = str(decoded.get("cid") or "").strip()
    if not cid:
        return None
    return {"cid": cid, "username": str(decoded.get("username") or "")}


async def _read_params(request: Request) -> dict[str, str]:
    """兼容 application/x-www-form-urlencoded 与 application/json 两种请求体。"""
    ctype = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    raw = await request.body()
    if not raw:
        return {}
    if ctype == "application/json":
        try:
            data = json.loads(raw.decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items() if v is not None}
    parsed = parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)
    return {k: v[0] for k, v in parsed.items()}


def _basic_auth(request: Request) -> tuple[str, str]:
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("basic "):
        return "", ""
    try:
        decoded = base64.b64decode(header[6:].strip()).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return "", ""
    client_id, _, client_secret = decoded.partition(":")
    return unquote(client_id), unquote(client_secret)


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return ""
    return header[7:].strip()


def _redirect_error(redirect_uri: str, state: str, error: str, description: str = "") -> Response:
    return RedirectResponse(
        oauth.build_redirect(
            redirect_uri,
            {"error": error, "error_description": description, "state": state},
        ),
        status_code=302,
        headers=_NO_STORE,
    )


def _login_url(request: Request) -> str:
    """未登录时回跳 CWFLY 登录页（登录后由前端整页跳回授权地址）。"""
    target = request.url.path + ("?" + request.url.query if request.url.query else "")
    return f"{settings.oauth2_issuer}/login?redirect={quote(target, safe='')}"


# --------------------------------------------------------------------------- #
# 授权页
# --------------------------------------------------------------------------- #
@router.get("/authorize")
async def authorize(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    if not oauth.is_configured():
        return _not_configured()

    params = request.query_params
    client_id = (params.get("client_id") or "").strip()
    redirect_uri = (params.get("redirect_uri") or "").strip()
    response_type = (params.get("response_type") or "").strip()
    raw_scope = params.get("scope") or ""
    state = params.get("state") or ""
    code_challenge = (params.get("code_challenge") or "").strip()
    code_challenge_method = (params.get("code_challenge_method") or "").strip().upper()

    # 1) client_id（环境变量内置客户端或数据库注册表）
    client = await oauth.get_client(db, client_id)
    if client is None or not client.get("enabled", True):
        return _html(400, "无效的客户端", "<p>client_id 未注册，拒绝授权请求。</p>")

    # 2) redirect_uri 白名单（必须与客户端登记的回调完全一致，避免开放重定向）
    if not await oauth.redirect_uri_ok(db, client_id, redirect_uri):
        return _html(
            400,
            "无效的回调地址",
            "<p>redirect_uri 不在白名单内（需与 OAUTH2_REDIRECT_URIS 完全一致）。</p>",
        )

    # 3) response_type
    if response_type != "code":
        return _redirect_error(
            redirect_uri, state, "unsupported_response_type", "仅支持 response_type=code"
        )

    # 4) scope
    scopes = oauth.parse_scope_for(raw_scope, client["scopes"])
    if scopes is None:
        return _redirect_error(redirect_uri, state, "invalid_scope", "包含未授权的 scope")

    # 5) PKCE 方法校验
    if code_challenge and code_challenge_method not in ("", "PLAIN", "S256"):
        return _redirect_error(
            redirect_uri, state, "invalid_request", "code_challenge_method 仅支持 S256/plain"
        )

    # 6) 登录态
    user = _session_user(request)
    if user is None:
        return RedirectResponse(_login_url(request), status_code=302, headers=_NO_STORE)

    approval = oauth.sign_approval(
        {
            "cid": user["cid"],
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": oauth.scope_string(scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
        }
    )

    # 交给前端 Vue 弹窗（OAuthConsentModal）完成确认，视觉与全站一致
    target = f"{settings.oauth2_issuer}/oauth/consent?approval={quote(approval, safe='')}"
    return RedirectResponse(target, status_code=302, headers=_NO_STORE)


@router.post("/authorize")
async def authorize_decision(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    if not oauth.is_configured():
        return _not_configured()

    form = await _read_params(request)
    data = oauth.verify_approval(form.get("approval") or "")
    if data is None:
        return _html(
            400,
            "授权请求已失效",
            "<p>本次授权确认已过期或被篡改，请回到第三方应用重新发起授权。</p>",
        )

    redirect_uri = str(data.get("redirect_uri") or "")
    state = str(data.get("state") or "")
    if not await oauth.redirect_uri_ok(db, str(data.get("client_id") or ""), redirect_uri):
        return _html(400, "无效的回调地址", "<p>redirect_uri 不在白名单内。</p>")

    if (form.get("decision") or "deny") != "approve":
        return _redirect_error(redirect_uri, state, "access_denied", "用户拒绝授权")

    # 二次确认登录态必须与签署载荷一致，防止「签完退出再换号」提权
    user = _session_user(request)
    if user is None or user["cid"] != str(data.get("cid") or ""):
        return _redirect_error(redirect_uri, state, "access_denied", "登录状态已变化，请重新授权")

    code = await oauth.issue_code(
        db,
        cid=user["cid"],
        client_id=str(data.get("client_id") or ""),
        redirect_uri=redirect_uri,
        scope=str(data.get("scope") or ""),
        code_challenge=str(data.get("code_challenge") or ""),
        code_challenge_method=str(data.get("code_challenge_method") or ""),
    )
    log.info(
        "[oauth2] 授权成功 cid=%s client=%s scope=%s",
        user["cid"],
        data.get("client_id"),
        data.get("scope"),
    )
    return RedirectResponse(
        oauth.build_redirect(redirect_uri, {"code": code, "state": state}),
        status_code=302,
        headers=_NO_STORE,
    )


# --------------------------------------------------------------------------- #
# 授权确认（前端 Vue 弹窗用的 JSON 接口）
# --------------------------------------------------------------------------- #
async def _consent_context(data: dict[str, Any], db: AsyncSession) -> dict[str, Any]:
    """把签名载荷翻译成弹窗需要的展示数据。"""
    cid = str(data.get("cid") or "")
    client_id = str(data.get("client_id") or "")
    meta = await oauth.app_meta(db, client_id)
    user = await users_service.find_user_public(db, cid) or {}
    scopes = [s for s in str(data.get("scope") or "").split() if s]
    return {
        "appName": meta["name"],
        "appOrigin": (meta.get("homepage") or "").split("://")[-1].strip("/"),
        "userName": str(user.get("username") or cid),
        "cid": cid,
        "scopes": [{"label": oauth.SCOPE_LABELS.get(s, s)} for s in scopes],
    }


@router.get("/consent")
async def consent_info(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    """弹窗打开时读取授权上下文（approval 由服务端签发，不可伪造）。"""
    if not oauth.is_configured():
        return _json_error(503, "temporarily_unavailable", "OAuth2 未配置")
    data = oauth.verify_approval(request.query_params.get("approval") or "")
    if data is None:
        return _json_error(400, "invalid_request", "授权请求已过期，请回到应用重新发起")
    user = _session_user(request)
    if user is None or user["cid"] != str(data.get("cid") or ""):
        return _json_error(401, "login_required", "登录状态已变化，请重新登录后授权")
    context = await _consent_context(data, db)
    return JSONResponse({"success": True, "data": context}, headers=_NO_STORE)


@router.post("/consent")
async def consent_decision(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    """同意 / 拒绝。同意返回第三方回跳地址，前端整页跳转即可。"""
    if not oauth.is_configured():
        return _json_error(503, "temporarily_unavailable", "OAuth2 未配置")

    payload = await _read_params(request)
    data = oauth.verify_approval(payload.get("approval") or "")
    if data is None:
        return _json_error(400, "invalid_request", "授权请求已过期，请回到应用重新发起")

    redirect_uri = str(data.get("redirect_uri") or "")
    state = str(data.get("state") or "")
    if not await oauth.redirect_uri_ok(db, str(data.get("client_id") or ""), redirect_uri):
        return _json_error(400, "invalid_request", "redirect_uri 不在白名单内")

    user = _session_user(request)
    if user is None or user["cid"] != str(data.get("cid") or ""):
        return _json_error(401, "login_required", "登录状态已变化，请重新登录后授权")

    if (payload.get("decision") or "deny") != "approve":
        return JSONResponse(
            {
                "success": True,
                "data": {
                    "redirect": oauth.build_redirect(
                        redirect_uri, {"error": "access_denied", "state": state}
                    )
                },
            },
            headers=_NO_STORE,
        )

    code = await oauth.issue_code(
        db,
        cid=user["cid"],
        client_id=str(data.get("client_id") or ""),
        redirect_uri=redirect_uri,
        scope=str(data.get("scope") or ""),
        code_challenge=str(data.get("code_challenge") or ""),
        code_challenge_method=str(data.get("code_challenge_method") or ""),
    )
    log.info(
        "[oauth2] 授权成功 cid=%s client=%s scope=%s",
        user["cid"],
        data.get("client_id"),
        data.get("scope"),
    )
    return JSONResponse(
        {
            "success": True,
            "data": {
                "redirect": oauth.build_redirect(
                    redirect_uri, {"code": code, "state": state}
                )
            },
        },
        headers=_NO_STORE,
    )


# --------------------------------------------------------------------------- #
# 令牌端点
# --------------------------------------------------------------------------- #
@router.post("/token")
async def token_endpoint(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    if not oauth.is_configured():
        return _json_error(503, "temporarily_unavailable", "OAuth2 未配置")

    form = await _read_params(request)
    client_id, client_secret = _basic_auth(request)
    if not client_id:
        client_id = form.get("client_id") or ""
        client_secret = form.get("client_secret") or ""
    if not await oauth.verify_client(db, client_id, client_secret):
        return _json_error(401, "invalid_client", "客户端认证失败")

    grant_type = (form.get("grant_type") or "").strip()
    client_id = client_id.strip()

    if grant_type == "authorization_code":
        code = form.get("code") or ""
        redirect_uri = form.get("redirect_uri") or ""
        if not code:
            return _json_error(400, "invalid_request", "缺少 code")
        if not redirect_uri:
            return _json_error(400, "invalid_request", "缺少 redirect_uri")
        if not await oauth.redirect_uri_ok(db, client_id, redirect_uri):
            return _json_error(400, "invalid_grant", "redirect_uri 不匹配")
        consumed = await oauth.consume_code(
            db,
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_verifier=form.get("code_verifier") or "",
        )
        if consumed is None:
            return _json_error(400, "invalid_grant", "授权码无效、已使用或已过期")
        issued = await oauth.issue_token(
            db, cid=consumed["cid"], client_id=client_id, scope=consumed["scope"]
        )
        return JSONResponse(issued, headers=_NO_STORE)

    if grant_type == "refresh_token":
        refresh_value = form.get("refresh_token") or ""
        if not refresh_value:
            return _json_error(400, "invalid_request", "缺少 refresh_token")
        issued = await oauth.refresh_token(
            db, refresh_value=refresh_value, client_id=client_id
        )
        if issued is None:
            return _json_error(400, "invalid_grant", "刷新令牌无效或已过期")
        return JSONResponse(issued, headers=_NO_STORE)

    return _json_error(400, "unsupported_grant_type", "仅支持 authorization_code / refresh_token")


# --------------------------------------------------------------------------- #
# 用户信息
# --------------------------------------------------------------------------- #
@router.get("/userinfo")
async def userinfo(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    if not oauth.is_configured():
        return _json_error(503, "temporarily_unavailable", "OAuth2 未配置")

    access_token = _bearer(request)
    if not access_token:
        return _json_error(401, "invalid_token", "缺少 Bearer 令牌")
    loaded = await oauth.load_access_token(db, access_token)
    if loaded is None:
        return _json_error(401, "invalid_token", "令牌无效或已过期")
    profile = await oauth.user_profile(db, loaded["cid"], loaded["scope"])
    if profile is None:
        return _json_error(404, "invalid_token", "账号不存在")
    return JSONResponse(profile, headers=_NO_STORE)


@router.post("/revoke")
async def revoke_endpoint(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    if not oauth.is_configured():
        return _json_error(503, "temporarily_unavailable", "OAuth2 未配置")
    form = await _read_params(request)
    client_id, client_secret = _basic_auth(request)
    if not client_id:
        client_id = form.get("client_id") or ""
        client_secret = form.get("client_secret") or ""
    if not await oauth.verify_client(db, client_id, client_secret):
        return _json_error(401, "invalid_client", "客户端认证失败")
    await oauth.revoke(db, form.get("token") or "")
    # RFC 7009：无论是否存在都返回 200
    return JSONResponse({}, headers=_NO_STORE)


@router.get("/health")
async def health() -> Response:
    return JSONResponse(
        {
            "success": True,
            "configured": oauth.is_configured(),
            "client_id": (settings.OAUTH2_CLIENT_ID or "")[:8] + "…"
            if settings.OAUTH2_CLIENT_ID
            else "",
            "redirect_uris": settings.oauth2_redirect_uris,
            "scopes": settings.oauth2_scopes,
            "endpoints": {
                "authorize": f"{settings.oauth2_issuer}/api/oauth/authorize",
                "token": f"{settings.oauth2_issuer}/api/oauth/token",
                "userinfo": f"{settings.oauth2_issuer}/api/oauth/userinfo",
                "revoke": f"{settings.oauth2_issuer}/api/oauth/revoke",
            },
        },
        headers=_NO_STORE,
    )


# --------------------------------------------------------------------------- #
# 页面模板
# --------------------------------------------------------------------------- #
_PAGE_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title · CWFLY 青翼模拟飞行</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
    padding: 24px; background: #0f172a;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
      "Microsoft YaHei", sans-serif; color: #e2e8f0;
  }
  .card {
    width: 100%; max-width: 420px; background: #111c33; border: 1px solid #1e293b;
    border-radius: 16px; padding: 28px 26px; box-shadow: 0 18px 48px rgba(0,0,0,.45);
  }
  h1 { font-size: 19px; margin: 0 0 6px; color: #f8fafc; }
  .sub { font-size: 12.5px; color: #94a3b8; margin: 0 0 20px; line-height: 1.6; }
  .user {
    display: flex; align-items: center; gap: 10px; padding: 12px 14px; margin-bottom: 18px;
    background: #0b1526; border: 1px solid #1e293b; border-radius: 11px; font-size: 13px;
  }
  .badge {
    width: 30px; height: 30px; border-radius: 50%; background: #1d4ed8; color: #fff;
    display: flex; align-items: center; justify-content: center; font-size: 13px;
    font-weight: 600; flex: none;
  }
  .user b { color: #f1f5f9; }
  .user span { color: #8fa3bf; }
  ul { margin: 0 0 22px; padding-left: 20px; font-size: 13px; color: #cbd5e1; line-height: 1.9; }
  .note { font-size: 11.5px; color: #7c8ba1; line-height: 1.7; margin: 0 0 20px; }
  .row { display: flex; gap: 10px; }
  button {
    flex: 1; padding: 11px 14px; border-radius: 10px; font-size: 13.5px; font-weight: 600;
    cursor: pointer; border: 1px solid transparent; font-family: inherit;
  }
  .approve { background: #1d4ed8; color: #fff; }
  .approve:hover { background: #2563eb; }
  .deny { background: transparent; color: #cbd5e1; border-color: #334155; }
  .deny:hover { background: #1e293b; }
  p { font-size: 13px; color: #cbd5e1; line-height: 1.8; }
</style>
</head>
<body>
  <div class="card">$body</div>
</body>
</html>
"""
)

__all__ = ["router"]
