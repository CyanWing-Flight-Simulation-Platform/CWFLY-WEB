"""/api/meetings 路由（逐接口对齐 Node src/routes/meetings.js）。

- GET  /        会议列表（**需登录**，见下方 MEETINGS_REQUIRE_AUTH）
- POST /upload  上传会议资料（需 rating >= 11；表单字段 `file`，20MB；先返回 processing，后台解析）

返回结构：`{ success: true, data: { ...meeting, fileUrl, status: 'processing' } }`

安全（2026-11-07 审计 P1-4 / P2-10）：
- 上传加「扩展名白名单 + 魔数校验 + 20MB 上限」，杜绝 `.html/.svg` 同域存储型 XSS；
- `/uploads/**` 静态响应统一 `X-Content-Type-Options: nosniff`，非图片强制
  `Content-Disposition: attachment`（见 `app/main.py`），即便内容可执行也不会被内联渲染；
- 会议列表属于内部纪要，改为要求登录（应急回滚开关 `MEETINGS_REQUIRE_AUTH=0`）。
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_rating
from app.services import meetings_uploads as mu
from app.utils.json_compat import JSJSONResponse

log = logging.getLogger("cwfly.meetings")
router = APIRouter(prefix="/meetings", tags=["meetings"])

# 应急回滚开关：设为 0 时恢复「会议列表公开」（默认强制登录）。
MEETINGS_REQUIRE_AUTH = os.getenv("MEETINGS_REQUIRE_AUTH", "1").strip().lower() not in (
    "0",
    "false",
    "no",
)


def _ok(data: Any = None, message: str | None = None) -> JSJSONResponse:
    body: dict[str, Any] = {"success": True}
    if data is not None:
        body["data"] = data
    if message is not None:
        body["message"] = message
    return JSJSONResponse(body)


def _fail(status_code: int, message: str) -> JSJSONResponse:
    return JSJSONResponse({"success": False, "message": message}, status_code=status_code)


async def meetings_viewer(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[CurrentUser]:
    """会议列表鉴权：默认要求登录；`MEETINGS_REQUIRE_AUTH=0` 时降级为可选登录。"""
    try:
        return await get_current_user(request, Response(), db)
    except Exception:
        if MEETINGS_REQUIRE_AUTH:
            raise
        return None


@router.get("")
async def list_meetings(
    db: AsyncSession = Depends(get_db),
    _viewer: Optional[CurrentUser] = Depends(meetings_viewer),
) -> JSJSONResponse:
    try:
        return _ok(await mu.list_meetings(db))
    except Exception as exc:  # noqa: BLE001
        log.error("[meetings] 查询失败: %s", exc)
        return _fail(500, "查询失败")


@router.post("/upload")
async def upload_meeting(
    file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_rating(11)),
) -> JSJSONResponse:
    try:
        if file is None or not (file.filename or ""):
            return _fail(400, "请选择文件")

        # 扩展名/魔数白名单 → 400（不落盘）；超过 20MB → 与原 Node 行为一致的 500
        try:
            path, size_bytes = await mu.save_upload(file)
        except mu.UnsupportedFileType as exc:
            return _fail(400, f"不支持的文件类型：{exc}")
        except mu.MeetingUploadRejected:
            return _fail(500, "服务器内部错误")

        original_name = file.filename
        title = mu.display_title(original_name)

        # 先创建「处理中」记录并立即返回
        meeting = await mu.create_meeting(
            db,
            {
                "title": title,
                "date": mu.utc_date_string(),
                "size": mu.size_label(size_bytes),
                "content": "",
                "status": "processing",
            },
        )

        # 后台解析，完成后更新记录（不阻塞上传响应）
        asyncio.get_running_loop().create_task(
            mu.parse_in_background(int(meeting.get("id") or 0), path, original_name)
        )

        file_url = f"/uploads/meetings/{path.name}"
        return _ok({**meeting, "fileUrl": file_url, "status": "processing"})
    except Exception as exc:  # noqa: BLE001
        log.error("[meetings] 上传失败: %s", exc)
        return _fail(500, "操作失败")


__all__ = ["router"]
