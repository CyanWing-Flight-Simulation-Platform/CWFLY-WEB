# CWFLY × Dubhe Nexus（Merak Identity）账号绑定对接说明

CWFLY 作为 **OAuth2 授权服务器（Provider）**，Dubhe Nexus 作为 **客户端（Client）**。
用户在 `https://merak.dubhenexus.io/apps`（授权应用管理）点「绑定 CWFLY 账号」→ 跳转 CWFLY 授权页 →
同意后带 `code` 回跳 `https://merak.dubhenexus.io/api/auth/callback` →
Merak 用 `code` 换 `access_token` → 调 `userinfo` 读取资料完成绑定。

实现文件：

| 文件 | 作用 |
| --- | --- |
| `app/services/oauth2.py` | 表结构、授权码/令牌签发与校验、同意页 HMAC 签名、按 scope 裁剪资料 |
| `app/routers/oauth2.py` | `/api/oauth/*` 路由 + 授权同意页（服务端直出 HTML） |
| `app/config.py` | `OAUTH2_*` 配置项 |
| `app/middleware/gateway.py` | `/oauth` 加入 UA 白名单（Merak 服务器无浏览器 UA） |
| `app/middleware/csrf.py` | `/api/oauth/` 免双提交校验（改用签名隐藏域） |
| `CWFLY-DEPLOY/sql/migrate-oauth2.sql` | 表结构（启动时也会自动建表） |

## 1. 生产环境变量（已写入 `/opt/cwfly/backend-py/.env`）

```ini
OAUTH2_ENABLED=true
OAUTH2_CLIENT_ID=cwfly_380a8ff4b2908206
OAUTH2_CLIENT_SECRET=l3NRuGyagGFjlqJrtE8zp2w4ubKuLH7zwEru0r6MHnu8ZHOy
OAUTH2_CLIENT_NAME=Dubhe Nexus
OAUTH2_REDIRECT_URIS=https://merak.dubhenexus.io/api/auth/callback
OAUTH2_SCOPES=profile email qq openid
OAUTH2_CODE_TTL_SECONDS=300
OAUTH2_TOKEN_TTL_SECONDS=3600
OAUTH2_REFRESH_TTL_SECONDS=2592000
```

> `OAUTH2_REDIRECT_URIS` 必须与 Merak 侧登记的 `redirect_uri` **完全一致**（精确匹配，
> 不支持通配/前缀）。若 Merak 侧实际回调地址不是 `https://merak.dubhenexus.io/api/auth/callback`，
> 改这一行后 `pm2 reload cwfly-api-py --update-env` 即可。

## 2. Merak 侧需要登记的 Provider 配置

| 字段 | 值 |
| --- | --- |
| provider id | `cwfly` |
| 名称 | CWFLY 青翼模拟飞行 |
| authorize / 授权地址 | `https://www.cwflysim.cn/api/oauth/authorize` |
| token 地址 | `https://www.cwflysim.cn/api/oauth/token` |
| userinfo / profile 地址 | `https://www.cwflysim.cn/api/oauth/userinfo` |
| client_id | `cwfly_380a8ff4b2908206` |
| client_secret | `l3NRuGyagGFjlqJrtE8zp2w4ubKuLH7zwEru0r6MHnu8ZHOy` |
| redirect_uri | `https://merak.dubhenexus.io/api/auth/callback` |
| scope | `profile email qq openid` |

协议细节（按 RFC 6749 标准即可，无需特殊适配）：

- 授权：`GET authorize?client_id&redirect_uri&response_type=code&scope&state`
  → 302 回跳 `redirect_uri?code=...&state=...`
- 换令牌：`POST token`，`application/x-www-form-urlencoded`
  `grant_type=authorization_code&code&redirect_uri&client_id&client_secret`
  → 支持 Basic 认证；支持 PKCE（`code_challenge` / `code_verifier`，S256/plain）
- 刷新：`grant_type=refresh_token&refresh_token&client_id&client_secret`（会轮换旧令牌）
- 用户信息：`GET userinfo`，`Authorization: Bearer <access_token>`
- 撤销：`POST revoke`，`token=...`
- 错误体：`{"error": "...", "error_description": "..."}`（RFC 6749 §5.2）

## 3. userinfo 返回结构

```json
{
  "sub": "1001",
  "cid": "1001",
  "openid": "cwfly:1001",
  "username": "CW-001",
  "nickname": "CW-001",
  "avatar": "https://www.cwflysim.cn/uploads/avatars/xxx.png",
  "rating": 5,
  "fsdLevel": 2,
  "permissions": "",
  "created_at": "2024-01-01T00:00:00",
  "email": "user@example.com",
  "qq": "123456",
  "scope": "profile email qq openid"
}
```

`profile` / `openid` / `email` / `qq` 字段严格按用户同意（granted scope）返回。
`sub` 恒等于 CWFLY 的 CID，是账号绑定的稳定主键。

## 4. 安全设计

- 授权码、access/refresh token **只存 SHA-256 摘要**（`oauth2_codes.code_hash` /
  `oauth2_tokens.access_hash|refresh_hash`），数据库被读也无法冒用。
- 授权码一次性消费（`UPDATE ... WHERE used = 0` 的 rowcount 判定），TTL 300 秒。
- 同意页参数用 `HMAC-SHA256(JWT_SECRET, "oauth2-approval")` 签名，隐藏域不可篡改，
  10 分钟过期；提交时二次校验登录态与签名里的 CID 一致。
- `redirect_uri` 精确白名单；`client_secret` 用 `hmac.compare_digest` 常量时间比较。
- 不传输密码、Passkey 私钥、生物特征数据。

## 5. 自检命令

```bash
curl -s https://www.cwflysim.cn/api/oauth/health | jq
```

应返回 `"configured": true` 与四个端点地址。

模拟 Merak 换令牌（预期 `invalid_grant`，证明客户端认证与表结构正常）：

```bash
curl -s -X POST https://www.cwflysim.cn/api/oauth/token \
  -d 'grant_type=authorization_code&code=fake' \
  -d 'redirect_uri=https://merak.dubhenexus.io/api/auth/callback' \
  -d 'client_id=cwfly_380a8ff4b2908206' \
  -d 'client_secret=l3NRuGyagGFjlqJrtE8zp2w4ubKuLH7zwEru0r6MHnu8ZHOy'
```

浏览器联调（需已登录 CWFLY）：

```
https://www.cwflysim.cn/api/oauth/authorize?client_id=cwfly_380a8ff4b2908206&redirect_uri=https%3A%2F%2Fmerak.dubhenexus.io%2Fapps&response_type=code&scope=profile%20email%20qq%20openid&state=test
```

## 6. 授权记录与解绑

授权记录存 `oauth2_tokens`（`cid` + `scope` 可查）。需要后台「已授权应用」列表时，
新增只读接口即可：

```sql
SELECT cid, scope, createdAt, accessExpiresAt
FROM `oauth2_tokens` WHERE revoked = 0 AND accessExpiresAt > NOW(3);
```

解绑 = `POST /api/oauth/revoke` 或把对应行 `revoked = 1`。
