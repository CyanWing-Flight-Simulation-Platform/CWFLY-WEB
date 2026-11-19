"""/api/tickets 路由（逐接口对齐 Node src/routes/tickets.js）。

Node 侧 ``router.use(authenticate)`` → 本模块每个端点都带 ``Depends(get_current_user)``。
- GET    /            我的工单列表（id desc）
- GET    /:id         工单详情（非本人 → 403「无权查看此工单」）
- POST   /            创建工单（createdAt/updatedAt 存 zh-CN 字符串）
- DELETE /:id         删除工单（存在关联回复 → 409）
"""
from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.services import tickets_service as ts
from app.services.js_compat_service import js_int, read_json_body
from app.utils.json_compat import JSJSONResponse

log = logging.getLogger("cwfly.tickets")
router = APIRouter(prefix="/tickets", tags=["tickets"])

TICKET_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "tickets"
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ATTACHMENT_TYPES = {
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", (b"PK\x03\x04",)),
}
ATTACHMENT_NAME_RE = re.compile(r"^[a-f0-9]{32}\.(?:png|jpg|jpeg|pdf|docx)$")
ATTACHMENT_URL_RE = re.compile(r"^/api/tickets/attachment/[a-f0-9]{32}\.(?:png|jpg|jpeg|pdf|docx)$")


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


@router.get("")
@router.get("/")
async def list_tickets(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        return _ok(await ts.list_tickets(db, current.cid))
    except Exception as exc:  # noqa: BLE001
        log.error("[tickets.py] %s", exc)
        return _fail(500, "操作失败")


@router.post("")
@router.post("/")
async def create_ticket(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        body = await read_json_body(request)
        title = body.get("title")
        content = body.get("content")
        if not title or not content:
            return _fail(400, "请填写标题和内容")
        attachment = body.get("attachment") or ""
        if attachment and not ATTACHMENT_URL_RE.fullmatch(str(attachment)):
            return _fail(400, "附件地址无效")
        ticket = await ts.create_ticket(
            db,
            current.cid,
            title,
            body.get("category"),
            body.get("priority"),
            content,
            attachment,
        )
        return _ok(ticket)
    except Exception as exc:  # noqa: BLE001
        log.error("[tickets.py] %s", exc)
        return _fail(500, "操作失败")


@router.post("/upload")
async def upload_ticket_attachment(
    file: UploadFile | None = File(None),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        if not file or not file.filename:
            return _fail(400, "请选择附件")
        ext = Path(file.filename).suffix.lower()
        meta = ATTACHMENT_TYPES.get(ext)
        if not meta:
            return _fail(400, "仅支持 PNG/JPG/DOCX/PDF 附件")
        data = await file.read(MAX_ATTACHMENT_BYTES + 1)
        if len(data) > MAX_ATTACHMENT_BYTES:
            return _fail(413, "附件不能超过 10MB")
        if not any(data.startswith(sig) for sig in meta[1]):
            return _fail(400, "附件内容与格式不符")
        TICKET_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = uuid.uuid4().hex + ext
        (TICKET_UPLOAD_DIR / safe_name).write_bytes(data)
        return _ok({
            "url": f"/api/tickets/attachment/{safe_name}",
            "name": Path(file.filename).name[:120],
        })
    except Exception as exc:  # noqa: BLE001
        log.error("[tickets.py] upload attachment: %s", exc)
        return _fail(500, "附件上传失败")


@router.get("/attachment/{filename}")
async def download_ticket_attachment(
    filename: str,
    current: CurrentUser = Depends(get_current_user),
) -> Any:
    if not ATTACHMENT_NAME_RE.fullmatch(filename):
        return _fail(404, "附件不存在")
    path = TICKET_UPLOAD_DIR / filename
    if not path.is_file():
        return _fail(404, "附件不存在")
    ext = path.suffix.lower()
    media_type = ATTACHMENT_TYPES.get(ext, ("application/octet-stream", ()))[0]
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        ticket = await ts.get_ticket(db, js_int(ticket_id))
        if not ticket:
            return _fail(404, "工单不存在")
        if str(ticket.get("userId")) != str(current.cid):
            return _fail(403, "无权查看此工单")
        return _ok(ticket)
    except Exception as exc:  # noqa: BLE001
        log.error("[tickets.py] %s", exc)
        return _fail(500, "操作失败")


@router.delete("/{ticket_id}")
async def delete_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> JSJSONResponse:
    try:
        ticket = await ts.get_ticket(db, js_int(ticket_id))
        if not ticket:
            return _fail(404, "工单不存在")
        if str(ticket.get("userId")) != str(current.cid):
            return _fail(403, "无权删除此工单")
        await ts.delete_ticket(db, int(ticket["id"]))
        return JSJSONResponse({"success": True, "message": "工单已删除"})
    except IntegrityError as exc:
        # Prisma P2003（外键约束，存在 TicketReply）→ 409
        log.warning("[tickets.py] 删除失败（外键）: %s", exc)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return _fail(409, "该工单存在关联回复，无法删除")
    except Exception as exc:  # noqa: BLE001
        log.error("[tickets.py] %s", exc)
        return _fail(500, "操作失败")


__all__ = ["router"]
