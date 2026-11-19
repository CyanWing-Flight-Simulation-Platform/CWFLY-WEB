"""会议资料上传 + 文档解析 + Meeting 表访问。

逐条对齐 Node `src/routes/meetings.js`：
- 落盘目录 `uploads/meetings`，上限 20MB（multer limits.fileSize）
- 文件名 `{Date.now()}-{safeName}`，`safeName = basename(name).replace(/[^a-zA-Z0-9._\\u4e00-\\u9fa5-]/g, '_')`
- 记录先以 `status='processing'` 落库并立即响应，解析完成后后台更新为 `ready` / `failed`
- 解析规则：`.docx` → HTML；`.pdf` → 文本包 `<p>`；其它 →「文件已上传。」

依赖说明（Node 用 mammoth / pdf-parse，Python 环境未安装同等库）：
- `.docx`：用标准库 zipfile + ElementTree 读 `word/document.xml`，逐段输出 `<p>`（不转换内嵌图片）；
- `.pdf`：用标准库 zlib 解压内容流并提取文本操作符，失败时与 Node 的 catch 分支同构。
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal

log = logging.getLogger("cwfly.meetings")

UPLOAD_ROOT = Path("uploads")
MEETINGS_DIR = UPLOAD_ROOT / "meetings"
MAX_BYTES = 20 * 1024 * 1024
_CHUNK = 64 * 1024

MEETING_COLS = "id, title, date, size, content, status"

_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._\u4e00-\u9fa5-]")

# ==================== 上传白名单（安全审计 P1-4） ====================
# 历史问题：只限制大小，不限制类型 → rating>=11 可上传 `.html`/`.svg`，
# 由于 `/uploads` 与主站同域且静态托管，构成同域存储型 XSS（可窃取 localStorage 里的
# Bearer Token）。现在：扩展名白名单 + 魔数校验 + 大小上限三重限制。
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".zip",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
    }
)
IMAGE_EXTENSIONS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})

_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # doc/xls/ppt（OLE2 复合文档）
_ZIP_MAGICS = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")  # zip/docx/xlsx/pptx


class MeetingUploadRejected(Exception):
    """等价 multer 的 LIMIT_FILE_SIZE（Node 全局错误处理 → 500）。"""


class UnsupportedFileType(Exception):
    """扩展名/魔数不在白名单（返回 400，不落盘）。"""


def ext_of(original_name: str | None) -> str:
    """`path.extname(name).toLowerCase()`。"""
    return os.path.splitext(os.path.basename((original_name or "").replace("\\", "/")))[1].lower()


def is_image_ext(ext: str) -> bool:
    return ext.lower() in IMAGE_EXTENSIONS


def check_extension(original_name: str | None) -> str:
    """校验扩展名白名单，返回规范化扩展名。"""
    ext = ext_of(original_name)
    if not ext:
        raise UnsupportedFileType("缺少文件扩展名")
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileType(f"不支持的文件类型：{ext}")
    return ext


def _looks_like_text(head: bytes) -> bool:
    """`.txt`：无 NUL 字节且能被 UTF-8（或 GBK 回退）解码。"""
    if b"\x00" in head:
        return False
    for encoding in ("utf-8", "gbk"):
        try:
            head.decode(encoding)
            return True
        except UnicodeDecodeError:
            continue
    return False


def magic_ok(ext: str, head: bytes) -> bool:
    """按扩展名核对文件头（魔数）。"""
    if not head:
        return False
    ext = ext.lower()
    if ext == ".pdf":
        return head.startswith(b"%PDF")
    if ext in (".docx", ".xlsx", ".pptx", ".zip"):
        return head.startswith(_ZIP_MAGICS)
    if ext in (".doc", ".xls", ".ppt"):
        return head.startswith(_OLE2_MAGIC)
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == ".gif":
        return head.startswith((b"GIF87a", b"GIF89a"))
    if ext == ".webp":
        return len(head) >= 12 and head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    if ext == ".txt":
        return _looks_like_text(head)
    return False


def validate_upload(original_name: str | None, head: bytes) -> str:
    """扩展名 + 魔数双重校验；不通过抛 UnsupportedFileType。返回规范化扩展名。"""
    ext = check_extension(original_name)
    if not magic_ok(ext, head):
        raise UnsupportedFileType(f"文件内容与扩展名 {ext} 不匹配")
    return ext


# ==================== 文件名与落盘 ====================
def safe_filename(original_name: str | None) -> str:
    """`{Date.now()}-{sanitized basename}`（与 Node 完全一致）。"""
    raw = original_name or ""
    base = os.path.basename(raw.replace("\\", "/"))
    sanitized = _SAFE_NAME_RE.sub("_", base)
    return f"{int(time.time() * 1000)}-{sanitized}"


def display_title(original_name: str | None) -> str:
    """标题 = 原始文件名去扩展名（Node: path.basename(name, ext)）。"""
    raw = original_name or ""
    base = os.path.basename(raw.replace("\\", "/"))
    return os.path.splitext(base)[0]


async def save_upload(file: UploadFile) -> tuple[Path, int]:
    """落盘并返回 (路径, 字节数)。

    校验顺序（安全审计 P1-4）：
    1. 扩展名白名单（不落盘即拒绝）；
    2. 首块字节魔数校验（与扩展名匹配，防 `.html` 改名为 `.pdf` 绕过）；
    3. 20MB 大小上限（等价 multer limits.fileSize）。
    """
    check_extension(file.filename)  # 扩展名不合法 → 直接抛错，不创建任何文件
    MEETINGS_DIR.mkdir(parents=True, exist_ok=True)
    dest = MEETINGS_DIR / safe_filename(file.filename)
    written = 0
    head_checked = False
    try:
        with dest.open("wb") as fh:
            while True:
                chunk = await file.read(_CHUNK)
                if not chunk:
                    break
                if not head_checked:
                    validate_upload(file.filename, chunk[:512])
                    head_checked = True
                written += len(chunk)
                if written > MAX_BYTES:
                    raise MeetingUploadRejected("LIMIT_FILE_SIZE")
                fh.write(chunk)
        if not head_checked:
            raise UnsupportedFileType("文件内容为空")
    except Exception:
        _unlink(dest)
        raise
    finally:
        try:
            await file.close()
        except Exception:  # noqa: BLE001
            pass
    return dest, written


def _unlink(path: Path | None) -> None:
    if path is None:
        return
    try:
        if os.path.isfile(path):
            os.unlink(path)
    except OSError:
        pass


def size_label(size_bytes: int) -> str:
    """`${(size/1024).toFixed(1)} KB`。"""
    return f"{size_bytes / 1024:.1f} KB"


def utc_date_string() -> str:
    """`new Date().toISOString().slice(0, 10)`。"""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


# ==================== HTML 转义 ====================
def escape_html(value: Any) -> str:
    """对齐 Node escapeHtml（`&` 先转义，避免二次转义）。"""
    if value is None or value == "":
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


# ==================== DOCX → HTML ====================
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_to_html(path: Path) -> str:
    """把 docx 正文转成 HTML（等价 mammoth.convertToHtml 的常用子集）。

    - 普通段落 → `<p>text</p>`（转义 HTML）；
    - 内嵌图片（`<a:blip r:embed>`）→ `<img src="data:<mime>;base64,..." />`（与 mammoth 一致）；
    - 制表符/换行按 mammoth 行为保留。
    """
    _R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    _A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    mime_by_ext = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".emf": "image/x-emf",
        ".wmf": "image/x-wmf",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }
    with zipfile.ZipFile(path) as archive:
        try:
            xml_bytes = archive.read("word/document.xml")
        except KeyError as exc:
            raise ValueError("docx 缺少 word/document.xml") from exc
        # rId -> 包内媒体路径
        rels: dict[str, str] = {}
        try:
            rel_xml = archive.read("word/_rels/document.xml.rels")
            for rel in ET.fromstring(rel_xml).iter():
                if rel.tag.endswith("}Relationship"):
                    rid = rel.get("Id")
                    target = (rel.get("Target") or "").lstrip("/")
                    if rid and target:
                        rels[rid] = target if target.startswith("word/") else f"word/{target}"
        except KeyError:
            rels = {}

        def image_tag(rid: str) -> str:
            media_path = rels.get(rid)
            if not media_path:
                return ""
            try:
                data = archive.read(media_path)
            except KeyError:
                return ""
            ext = Path(media_path).suffix.lower()
            mime = mime_by_ext.get(ext, "application/octet-stream")
            import base64

            return f'<img src="data:{mime};base64,{base64.b64encode(data).decode()}" />'

        root = ET.fromstring(xml_bytes)
        paragraphs: list[str] = []
        for paragraph in root.iter(f"{_W_NS}p"):
            pieces: list[str] = []
            for node in paragraph.iter():
                if node.tag == f"{_W_NS}t" and node.text:
                    pieces.append(node.text)
                elif node.tag == f"{_W_NS}tab":
                    pieces.append("	")
                elif node.tag in (f"{_W_NS}br", f"{_W_NS}cr"):
                    pieces.append("\n")
                elif node.tag == f"{_A_NS}blip":
                    rid = node.get(f"{_R_NS}embed") or ""
                    tag = image_tag(rid) if rid else ""
                    if tag:
                        pieces.append(tag)
            raw = "".join(pieces)
            if not raw.strip():
                continue
            # 文本块转义、img 标签保留
            html_parts: list[str] = []
            for chunk in re.split(r"(<img [^>]*/>)", raw):
                if chunk.startswith("<img "):
                    html_parts.append(chunk)
                elif chunk:
                    html_parts.append(escape_html(chunk))
            paragraphs.append(f"<p>{''.join(html_parts)}</p>")
        return "".join(paragraphs)


# ==================== PDF → 文本 ====================
def _pdf_unescape(raw: bytes) -> str:
    out = bytearray()
    index = 0
    length = len(raw)
    while index < length:
        char = raw[index]
        if char == 0x5C and index + 1 < length:  # 反斜杠转义
            nxt = raw[index + 1]
            mapping = {0x6E: 0x0A, 0x72: 0x0D, 0x74: 0x09, 0x62: 0x08, 0x66: 0x0C}
            if nxt in mapping:
                out.append(mapping[nxt])
                index += 2
                continue
            if 0x30 <= nxt <= 0x37:  # 八进制 \ddd
                digits = raw[index + 1 : index + 4]
                try:
                    out.append(int(digits, 8) & 0xFF)
                except ValueError:
                    pass
                index += 1 + len(digits)
                continue
            out.append(nxt)
            index += 2
            continue
        out.append(char)
        index += 1
    return out.decode("utf-8", "replace")


def _pdf_stream_text(stream: bytes) -> str:
    pieces: list[str] = []
    token_re = re.compile(
        rb"\[(?:[^\[\]\\]|\\.)*\]\s*TJ"
        rb"|\((?:[^()\\]|\\.)*\)\s*(?:Tj|'|\")"
        rb"|T\*"
        rb"|T[dD]",
        re.S,
    )
    for match in token_re.finditer(stream):
        token = match.group(0)
        if token in (b"T*", b"Td", b"TD"):
            pieces.append("\n")
            continue
        for literal in re.finditer(rb"\((?:[^()\\]|\\.)*\)", token, re.S):
            pieces.append(_pdf_unescape(literal.group(0)[1:-1]))
    return "".join(pieces)


def pdf_to_text(path: Path) -> str:
    """优先用 pypdf 正确解码字体/ToUnicode；旧环境无依赖时回退到极简解析。"""
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise ValueError("文件内容不是有效的 PDF")
    try:
        from pypdf import PdfReader
    except ImportError:
        PdfReader = None
    if PdfReader is not None:
        try:
            reader = PdfReader(str(path))
            pages = [(page.extract_text() or "") for page in reader.pages]
            return "\n".join(pages).strip()
        except Exception as exc:  # noqa: BLE001 - 加密/损坏 PDF 回退旧解析
            log.warning("[Meeting] pypdf 解析失败，回退旧解析: %s", exc)
    # 旧版极简解析：仅作为 pypdf 不可用时的回退
    chunks: list[str] = []
    for match in re.finditer(rb"stream\r?\n", data):
        start = match.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        raw = data[start:end]
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass  # 未压缩流
        text_value = _pdf_stream_text(raw)
        if text_value.strip():
            chunks.append(text_value)
    return "\n".join(chunks)


# ==================== 解析总入口 ====================
_PDF_WATERMARK_RE = re.compile(
    r"^(?:CWFLY|青翼模拟飞行|CWFLY青翼模拟飞行)+$",
    re.IGNORECASE,
)


def _is_pdf_watermark(line: str) -> bool:
    """过滤 PDF 页眉/页脚中的纯品牌水印（如重复的 CWFLY）。"""
    key = re.sub(r"\s+", "", str(line or ""))
    return bool(key) and bool(_PDF_WATERMARK_RE.fullmatch(key))


async def parse_document(path: Path, original_name: str | None) -> str:
    """对齐 Node parseDocument：返回要落库的 HTML。"""
    ext = os.path.splitext(original_name or "")[1].lower()
    if ext == ".docx":
        value = docx_to_html(path)
        return value or "<p>文档内容为空</p>"
    if ext == ".pdf":
        try:
            raw_text = pdf_to_text(path)
            escaped = (
                raw_text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#039;")
            )
            body = "".join(
                f"<p>{line}</p>"
                for line in escaped.split("\n")
                if line.strip() and not _is_pdf_watermark(line)
            )
            return body or "<p>PDF 文件内容为空</p>"
        except Exception as exc:  # noqa: BLE001
            return f"<p>PDF 文件已上传，但解析失败: {escape_html(str(exc))}</p>"
    return "<p>文件已上传。</p>"


# ==================== Meeting 表访问 ====================
def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


async def list_meetings(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.execute(text(f"SELECT {MEETING_COLS} FROM `Meeting` ORDER BY id DESC"))
    ).all()
    return [_row(r) for r in rows]


async def get_meeting(db: AsyncSession, meeting_id: int) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text(f"SELECT {MEETING_COLS} FROM `Meeting` WHERE id = :id LIMIT 1"),
            {"id": meeting_id},
        )
    ).first()
    return _row(row) if row else None


async def create_meeting(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    result = await db.execute(
        text(
            "INSERT INTO `Meeting` (title, date, size, content, status) "
            "VALUES (:title, :date, :size, :content, :status)"
        ),
        {
            "title": data["title"],
            "date": data["date"],
            "size": data["size"],
            "content": data.get("content") or "",
            "status": data.get("status") or "ready",
        },
    )
    await db.commit()
    meeting_id = int(result.lastrowid)
    created = await get_meeting(db, meeting_id)
    return created or {"id": meeting_id, **data}


async def update_meeting_content(
    db: AsyncSession, meeting_id: int, content: str, status: str
) -> None:
    await db.execute(
        text("UPDATE `Meeting` SET content = :content, status = :status WHERE id = :id"),
        {"content": content, "status": status, "id": meeting_id},
    )
    await db.commit()


async def parse_in_background(meeting_id: int, path: Path, original_name: str | None) -> None:
    """等价 Node `setImmediate(async () => { ... })`：独立会话更新记录。"""
    try:
        async with SessionLocal() as db:
            content = await parse_document(path, original_name)
            await update_meeting_content(db, meeting_id, content, "ready")
    except Exception as exc:  # noqa: BLE001
        log.error("[Meeting] 解析失败 id=%s: %s", meeting_id, exc)
        try:
            async with SessionLocal() as db:
                await update_meeting_content(
                    db, meeting_id, f"<p>解析失败: {escape_html(str(exc))}</p>", "failed"
                )
        except Exception:  # noqa: BLE001
            pass


__all__ = [
    "MEETINGS_DIR",
    "MAX_BYTES",
    "MEETING_COLS",
    "ALLOWED_EXTENSIONS",
    "IMAGE_EXTENSIONS",
    "MeetingUploadRejected",
    "UnsupportedFileType",
    "ext_of",
    "is_image_ext",
    "check_extension",
    "magic_ok",
    "validate_upload",
    "safe_filename",
    "display_title",
    "save_upload",
    "size_label",
    "utc_date_string",
    "escape_html",
    "parse_document",
    "list_meetings",
    "get_meeting",
    "create_meeting",
    "update_meeting_content",
    "parse_in_background",
]
