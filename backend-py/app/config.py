"""配置：与 Node 版 config/index.js 完全同名的环境变量。"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_duration_seconds(value: str, default: int = 600) -> int:
    """把 jsonwebtoken 风格的 '10m' / '600s' / '1h' 解析成秒。"""
    if not value:
        return default
    m = re.fullmatch(r"\s*(\d+)\s*([smhd]?)\s*", value)
    if not m:
        return default
    n = int(m.group(1))
    unit = m.group(2) or "s"
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- 基础 ----
    NODE_ENV: str = "development"
    PORT: int = 3000

    # ---- 数据库（与 Node 同一个 mysql:// URL）----
    DATABASE_URL: str = "mysql://root:password@localhost:3306/cwfly"
    DB_CONNECTION_LIMIT: int = 5

    # ---- JWT（与 Node 完全一致）----
    JWT_SECRET: str = ""
    JWT_EXPIRES: str = "12h"
    # 绝对会话上限：无论是否滑动续签，从首次登录起最多 12 小时必须重新登录
    JWT_MAX_SESSION_SECONDS: int = 43200
    JWT_REFRESH_GRACE_SECONDS: int = 1800
    JWT_REFRESH_BEFORE_SECONDS: int = 120
    # 安全（P0-3）：access token 必须带 typ="access"。
    # 滚动发布期如需避免存量会话集中掉线，可临时设 JWT_ALLOW_LEGACY_TYP=1，
    # 放行「无 typ 声明」的旧 token（≤ 一个 JWT_EXPIRES 周期后必须关闭）。
    JWT_ALLOW_LEGACY_TYP: bool = False

    # ---- CORS ----
    CORS_ORIGIN: Optional[str] = None

    # ---- 管理员初始化 ----
    ADMIN_PASSWORD: Optional[str] = None

    # ---- 邮件 ----
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "CW 模拟飞行"
    FRONTEND_URL: str = "http://localhost:5173"

    # ---- WebAuthn / Passkey ----
    WEBAUTHN_RP_ID: Optional[str] = None
    WEBAUTHN_RP_NAME: str = "CWFLY 青翼模拟飞行"
    WEBAUTHN_ORIGIN: Optional[str] = None

    # ---- OAuth2 授权服务器（供 Dubhe Nexus / Merak 等第三方绑定 CWFLY 账号）----
    # 留空 CLIENT_ID / CLIENT_SECRET 时 /api/oauth/* 返回 503（不影响其它功能）。
    OAUTH2_ENABLED: bool = True
    OAUTH2_CLIENT_ID: str = ""
    OAUTH2_CLIENT_SECRET: str = ""
    OAUTH2_CLIENT_NAME: str = "Dubhe Nexus"
    # 允许的回调地址（逗号分隔，精确匹配；生产填 Merak 的 callback）
    OAUTH2_REDIRECT_URIS: str = ""
    OAUTH2_SCOPES: str = "profile email qq openid"
    OAUTH2_CODE_TTL_SECONDS: int = 300
    OAUTH2_TOKEN_TTL_SECONDS: int = 3600
    OAUTH2_REFRESH_TTL_SECONDS: int = 2592000
    # 对外站点根地址（拼 avatar / 回跳地址）；留空回退 CORS_ORIGIN
    OAUTH2_ISSUER: Optional[str] = None

    # ---- 登录安全 / 验证码 ----
    VERIFY_CODE_TTL_SECONDS: int = 600
    VERIFY_CODE_MAX_ATTEMPTS: int = 5
    VERIFY_SEND_COOLDOWN_SECONDS: int = 60
    LOGIN_CHALLENGE_TTL_SECONDS: int = 600
    TRUSTED_IP_LOGIN_HISTORY: int = 50
    TRUSTED_DEVICE_TTL_SECONDS: int = 2592000

    # ---- 审计日志 ----
    AUDIT_LOG_ALL_REQUESTS: bool = True
    AUDIT_LOG_RETENTION_DAYS: int = 180

    # 备份加密：GPG 对称口令文件（root 600）；留空保留明文 .sql.gz
    BACKUP_GPG_PASSPHRASE_FILE: str = ""

    LOGIN_LOCK_WINDOW_MINUTES: int = 15
    LOGIN_LOCK_MAX_FAILS: int = 5

    # ---- 第三方 ----
    OPENAPI_KEY: str = ""
    FSD_WHAZZUP_FILE: str = ""
    FSD_SYS_CID: str = ""
    FSD_SYS_PASSWORD: str = ""
    # FSD 管理控制台（3012）：在线列表/广播/踢人/私聊；口令留空时读 FSD_CONSOLE_CONFIG 的 [system] password
    FSD_CONSOLE_HOST: str = "127.0.0.1"
    FSD_CONSOLE_PORT: int = 3012
    FSD_CONSOLE_PASSWORD: str = ""
    FSD_CONSOLE_CONFIG: str = "/opt/cwfly/fsd-py/fsd-db.conf"

    @property
    def is_prod(self) -> bool:
        return self.NODE_ENV == "production"

    @property
    def cors_origins(self) -> list[str]:
        """允许多个来源：显式配置的 CORS_ORIGIN + 生产主域名/裸域 + 本地开发地址。"""
        items: list[str] = []
        raw = (self.CORS_ORIGIN or "").strip()
        if raw:
            items.extend([x.strip() for x in raw.split(",") if x.strip()])
        else:
            items.append("https://www.cwflysim.cn")
        # 生产同一站点的裸域（nginx server_name 同时包含 cwflysim.cn 与 www）
        items.extend(["https://cwflysim.cn", "https://www.cwflysim.cn"])
        if self.NODE_ENV != "production":
            items.extend(["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"])
        # 去重保序
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    @property
    def cors_origin(self) -> str:
        """与 Node 一致的 CORS 回退逻辑（生产不再回退到 localhost）。"""
        if self.CORS_ORIGIN:
            return self.CORS_ORIGIN
        return "https://www.cwflysim.cn" if self.is_prod else "http://localhost:5173"

    @property
    def webauthn_rp_id(self) -> str:
        if self.WEBAUTHN_RP_ID:
            return self.WEBAUTHN_RP_ID.strip()
        source = self.WEBAUTHN_ORIGIN or self.CORS_ORIGIN or self.FRONTEND_URL
        host = (source or "").split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
        if host.startswith("www."):
            host = host[4:]
        return host or "localhost"

    @property
    def webauthn_origin(self) -> str:
        if self.WEBAUTHN_ORIGIN:
            return self.WEBAUTHN_ORIGIN.strip().rstrip("/")
        return (self.CORS_ORIGIN or self.FRONTEND_URL or self.cors_origin).rstrip("/")

    @property
    def webauthn_origins(self) -> list[str]:
        """允许的页面 Origin；生产同时兼容主域名和裸域。"""
        items = [self.webauthn_origin]
        if self.webauthn_rp_id.endswith("cwflysim.cn"):
            items.extend(["https://www.cwflysim.cn", "https://cwflysim.cn"])
        return list(dict.fromkeys(x for x in items if x))

    @property
    def oauth2_issuer(self) -> str:
        """对外站点根地址（无尾斜杠），用于拼接头像地址与登录回跳。"""
        if self.OAUTH2_ISSUER:
            return self.OAUTH2_ISSUER.strip().rstrip("/")
        return (self.CORS_ORIGIN or self.cors_origin).rstrip("/")

    @property
    def oauth2_redirect_uris(self) -> list[str]:
        raw = (self.OAUTH2_REDIRECT_URIS or "").strip()
        return [x.strip() for x in raw.split(",") if x.strip()]

    @property
    def oauth2_scopes(self) -> list[str]:
        items = (self.OAUTH2_SCOPES or "").replace(",", " ").split()
        return list(dict.fromkeys(x.strip() for x in items if x.strip()))

    @property
    def oauth2_ready(self) -> bool:
        return bool(
            self.OAUTH2_ENABLED
            and self.OAUTH2_CLIENT_ID.strip()
            and self.OAUTH2_CLIENT_SECRET.strip()
            and self.oauth2_redirect_uris
        )

    @property
    def jwt_expires_seconds(self) -> int:
        return parse_duration_seconds(self.JWT_EXPIRES, 21600)

    @property
    def async_database_url(self) -> str:
        """mysql:// → mysql+asyncmy://（同一个库、同一套表，不改结构）。"""
        url = self.DATABASE_URL
        if url.startswith("mysql://"):
            url = "mysql+asyncmy://" + url[len("mysql://") :]
        elif url.startswith("mariadb://"):
            url = "mysql+asyncmy://" + url[len("mariadb://") :]
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}charset=utf8mb4"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # 与 Node 版一致的安全门禁：密钥缺失/过短直接拒绝启动
    if not s.JWT_SECRET or s.JWT_SECRET == "cwfly-secret-key-2024" or len(s.JWT_SECRET) < 32:
        raise RuntimeError(
            "安全错误: JWT_SECRET 环境变量未设置或过短（需 >= 32 字符的随机密钥）"
        )
    return s


settings = get_settings()
