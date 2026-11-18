"""邮件与验证码（对齐 Node src/utils/mailer.js 的关键行为）。

- 验证码：只写 `VerificationCode` 表（多实例共享，带 purpose），DB 异常抛
  `VerificationUnavailable`，由调用方返回 503；
- 校验：按 purpose 一次性消费，通过即删；连续失败达到上限作废该邮箱验证码；
- 发送：aiosmtplib（异步 SMTP），邮件发送失败不影响主流程（Node 同样 catch 忽略）。
"""
from __future__ import annotations

import asyncio
import logging
import secrets
import threading
from typing import Any

from aiosmtplib import send as smtp_send
from email.message import EmailMessage

from app.config import settings
from app.db.session import SessionLocal
from app.services import users

log = logging.getLogger("cwfly.mailer")

CODE_TTL_MS = max(1, int(settings.VERIFY_CODE_TTL_SECONDS)) * 1000
MAX_ATTEMPTS = max(1, int(settings.VERIFY_CODE_MAX_ATTEMPTS))


class VerificationUnavailable(Exception):
    """验证码存储不可用：调用方必须返回 503，禁止进程内降级。"""


def generate_code() -> str:
    """6 位数字验证码（对齐 Node crypto.randomInt(100000, 1000000)）。"""
    return str(secrets.randbelow(900000) + 100000)


async def store_code(email: str, code: str, purpose: str = "register") -> None:
    try:
        async with SessionLocal() as db:
            await users.store_verification_code(db, email, code, CODE_TTL_MS, purpose)
    except Exception as exc:  # noqa: BLE001
        log.error("[mailer] 验证码写入失败: %s", exc)
        raise VerificationUnavailable("验证码存储暂不可用") from exc


async def verify_code(email: str, code: str, purpose: str = "register") -> bool:
    """按用途校验并消费验证码；数据库不可用时抛 VerificationUnavailable。"""
    try:
        async with SessionLocal() as db:
            return await users.consume_verification_code(
                db, email, code, purpose, MAX_ATTEMPTS
            )
    except Exception as exc:  # noqa: BLE001
        log.error("[mailer] 验证码校验失败: %s", exc)
        raise VerificationUnavailable("验证码校验服务暂不可用") from exc


async def _smtp_send(to: str, subject: str, html: str, text_body: str = "") -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        return
    message = EmailMessage()
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body or "请使用支持 HTML 的客户端查看本邮件")
    message.add_alternative(html, subtype="html")
    await smtp_send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME or None,
        password=settings.SMTP_PASSWORD or None,
        use_tls=settings.SMTP_PORT == 465,
        start_tls=settings.SMTP_PORT == 587,
        timeout=12,
    )


async def send_verify_code(to: str, code: str, purpose: str = "验证") -> None:
    html = (
        f"<p>您的{purpose}验证码是：</p>"
        f"<p style='font-size:24px;font-weight:bold;letter-spacing:4px'>{code}</p>"
        f"<p>10 分钟内有效，请勿泄露给他人。</p>"
    )
    await _smtp_send(to, f"{settings.SMTP_FROM_NAME} {purpose}验证码", html, f"验证码：{code}")


def fire_and_forget_thread(coro_factory: Any) -> None:
    """在独立线程 + 独立事件循环里发信。

    aiosmtplib 的 DNS/握手在部分环境下会拖住共享事件循环（表现为第二个请求整体卡 10s+），
    因此验证码邮件一律扔到独立线程：SMTP 再慢也不阻塞 API 响应。
    """
    def _run() -> None:
        try:
            asyncio.run(coro_factory())
        except Exception as exc:  # noqa: BLE001
            log.error("[mail] 后台发信失败: %s", exc)

    threading.Thread(target=_run, daemon=True, name="cwfly-mail").start()


def fire_and_forget(coro: Any) -> None:
    """Node 版 `sendNotification(...).catch(() => {})`：不阻塞响应、失败静默。"""
    try:
        asyncio.get_running_loop().create_task(coro)
    except RuntimeError:
        pass


async def send_notification(to: str, payload: dict[str, Any]) -> None:
    subject = payload.get("subject") or "通知"
    intro = payload.get("intro") or ""
    body = payload.get("body") or ""
    action = payload.get("action") or ""
    action_url = payload.get("actionUrl") or settings.FRONTEND_URL
    html = f"<p>{intro}</p><p>{body}</p>"
    if action:
        html += f"<p><a href='{action_url}'>{action}</a></p>"
    await _smtp_send(to, subject, html, f"{intro}\n{body}\n{action_url}")


async def send_security_alert(to: str, payload: dict[str, Any]) -> None:
    subject = f"安全提醒：{payload.get('action') or '账号操作'}"
    html = (
        f"<p>{payload.get('action') or ''}</p>"
        f"<p>{payload.get('detail') or ''}</p>"
        f"<p>时间：{payload.get('time') or ''}<br/>IP：{payload.get('ip') or ''}</p>"
    )
    await _smtp_send(to, subject, html, str(payload))


__all__ = [
    "VerificationUnavailable",
    "generate_code",
    "store_code",
    "verify_code",
    "send_verify_code",
    "send_notification",
    "send_security_alert",
    "fire_and_forget",
]
