"""FSD 管理控制台（3012）客户端。

我方 FSD（CWFLY-FSD）在 127.0.0.1:3012 暴露一个带口令的文本控制台，命令：
    pwd <password> / clients / stats / servers / say <cs> <text> / wall <text> / kill <cs>

本模块把它包装成 Python API，供 /api/online 使用：
- 不修改 FSD 代码、不重启 FSD，仅走现有管理通道（只读 + 少量管理动作）
- 每次调用建一次短连接（FSD 控制台是低并发场景），失败统一抛 FsdConsoleError
"""
from __future__ import annotations

import asyncio
import configparser
import logging
import re
from typing import Any, Optional

from app.config import settings

log = logging.getLogger("cwfly.fsd_console")

PROMPT = b"> "
_CONNECT_TIMEOUT = 3.0
_READ_TIMEOUT = 5.0

_CLIENT_RE = re.compile(
    r"^\s*(?P<callsign>\S+)\s+(?P<cid>\S+)\s+(?P<type>PILOT|ATC)\s+"
    r"rating=(?P<rating>-?\d+)\s+idle=(?P<idle>-?\d+)s\s*$"
)
_STAT_RE = re.compile(r"^\s*(?P<key>[A-Za-z ()0-9,]+?):\s*(?P<value>.+?)\s*$")


class FsdConsoleError(RuntimeError):
    """FSD 管理口不可用 / 认证失败 / 命令失败。"""


def _password_from_config_file() -> str:
    """未显式配置口令时，从 FSD 运行配置里读取 [system] password。"""
    path = (settings.FSD_CONSOLE_CONFIG or "").strip()
    if not path:
        return ""
    try:
        cp = configparser.ConfigParser(interpolation=None)
        cp.read(path, encoding="utf-8")
        return cp.get("system", "password", fallback="") or ""
    except Exception as exc:  # noqa: BLE001
        log.warning("[fsd_console] 读取配置口令失败 %s: %s", path, exc)
        return ""


def console_password() -> str:
    return (settings.FSD_CONSOLE_PASSWORD or "").strip() or _password_from_config_file()


class _Session:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader = reader
        self.writer = writer

    async def read_prompt(self, timeout: float = _READ_TIMEOUT) -> str:
        buf = b""
        try:
            while True:
                chunk = await asyncio.wait_for(self.reader.read(4096), timeout=timeout)
                if not chunk:
                    break
                buf += chunk
                if buf.endswith(PROMPT):
                    break
        except asyncio.TimeoutError:
            pass
        return buf.decode("utf-8", "replace")

    async def command(self, line: str, timeout: float = _READ_TIMEOUT) -> str:
        self.writer.write(f"{line}\r\n".encode())
        await self.writer.drain()
        return await self.read_prompt(timeout)

    async def close(self) -> None:
        try:
            self.writer.close()
        except Exception:  # noqa: BLE001
            pass


class _open_console:
    """异步上下文管理器：连接 → 认证 → 交给调用方 → 关闭。"""

    def __init__(self) -> None:
        self.session: Optional[_Session] = None

    async def __aenter__(self) -> _Session:
        password = console_password()
        if not password:
            raise FsdConsoleError("未配置 FSD 管理口令（FSD_CONSOLE_PASSWORD 或 FSD_CONSOLE_CONFIG）")
        host = settings.FSD_CONSOLE_HOST or "127.0.0.1"
        port = int(settings.FSD_CONSOLE_PORT or 3012)
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=_CONNECT_TIMEOUT
            )
        except Exception as exc:  # noqa: BLE001
            raise FsdConsoleError(f"无法连接 FSD 管理口 {host}:{port}：{exc}") from exc
        self.session = _Session(reader, writer)
        await self.session.read_prompt()
        reply = await self.session.command(f"pwd {password}")
        if "Password correct" not in reply:
            await self.session.close()
            raise FsdConsoleError("FSD 管理口令不正确")
        return self.session

    async def __aexit__(self, *exc_info: Any) -> None:
        if self.session:
            try:
                await self.session.command("quit", timeout=1.0)
            except Exception:  # noqa: BLE001
                pass
            await self.session.close()
            self.session = None


def _strip_prompt(text: str) -> str:
    return text.replace("> ", "").strip()


def _parse_clients(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in _strip_prompt(text).splitlines():
        m = _CLIENT_RE.match(line)
        if not m:
            continue
        out.append(
            {
                "callsign": m.group("callsign"),
                "cid": m.group("cid"),
                "type": "ATC" if m.group("type") == "ATC" else "PILOT",
                "rating": int(m.group("rating")),
                "idle": int(m.group("idle")),
            }
        )
    return out


def _parse_stats(text: str) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    body = _strip_prompt(text)
    labels = {
        "Connections": "connections",
        "Clients": "clients",
        "Servers": "servers",
        "Certs": "certs",
        "Packets received": "packetsReceived",
        "Packets sent": "packetsSent",
        "Auth success": "authSuccess",
        "Auth fail": "authFail",
        "Loop lag max (5min)": "loopLagMaxMs",
        "Plan dispatch": "planDispatch",
        "Keepalive": "keepalive",
    }
    for line in body.splitlines():
        m = _STAT_RE.match(line)
        if not m:
            continue
        key = m.group("key").strip()
        value = m.group("value").strip()
        mapped = labels.get(key)
        if not mapped:
            continue
        if value.isdigit():
            stats[mapped] = int(value)
        elif value.endswith("ms") and value[:-2].isdigit():
            stats[mapped] = int(value[:-2])
        elif value in ("on", "off"):
            stats[mapped] = value == "on"
        else:
            stats[mapped] = value
    return stats


async def list_clients() -> list[dict[str, Any]]:
    async with _open_console() as s:
        return _parse_clients(await s.command("clients"))


async def stats() -> dict[str, Any]:
    async with _open_console() as s:
        return _parse_stats(await s.command("stats"))


async def say(callsign: str, message: str) -> bool:
    """向指定呼号发送一条服务端消息（客户端会显示为服务器消息）。"""
    target = (callsign or "").strip()
    text = " ".join((message or "").split())
    if not target or not text:
        raise ValueError("呼号与消息内容不能为空")
    async with _open_console() as s:
        reply = _strip_prompt(await s.command(f"say {target} {text}"))
    if reply.startswith("Sent to"):
        return True
    raise FsdConsoleError(reply or "发送失败")


async def wall(message: str) -> int:
    """全服广播，返回送达人数。"""
    text = " ".join((message or "").split())
    if not text:
        raise ValueError("广播内容不能为空")
    async with _open_console() as s:
        reply = _strip_prompt(await s.command(f"wall {text}"))
    m = re.search(r"Broadcast to (\d+) users", reply)
    if m:
        return int(m.group(1))
    raise FsdConsoleError(reply or "广播失败")


async def kick(callsign: str) -> bool:
    target = (callsign or "").strip()
    if not target:
        raise ValueError("呼号不能为空")
    async with _open_console() as s:
        reply = _strip_prompt(await s.command(f"kill {target}"))
    if reply.startswith("Killed"):
        return True
    raise FsdConsoleError(reply or "踢出失败")
