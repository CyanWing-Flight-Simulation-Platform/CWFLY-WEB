# CWFLY-WEB · 青翼模拟飞行连飞平台

[![Frontend CI](https://github.com/CyanWing-Flight-Simulation-Platform/CWFLY-WEB/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/CyanWing-Flight-Simulation-Platform/CWFLY-WEB/actions/workflows/frontend-ci.yml)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Website](https://img.shields.io/badge/website-cwflysim.cn-0b7285)](https://www.cwflysim.cn)

CWFLY（青翼虚拟航空）的社区门户与连飞平台，包含对外站点、登录后工作台、管理后台，以及配套的 Python API 服务。

本仓库是独立部署仓，包含：

- `frontend/`：Vue 3 + Vite 单页应用
- `backend-py/`：FastAPI + SQLAlchemy async + MySQL + Redis 后端
- `docs/`：前端架构、测试与运维交接文档

> 线上站点：<https://www.cwflysim.cn>
>
> 关联项目：FSD 连飞服务器、管制中心、QQ 机器人、文档站（均为独立仓库）。

## 快速开始

### 环境要求

- Node.js 18+（推荐 20 / 22 LTS）
- Python 3.12
- MySQL 8.x
- Git LFS（背景图、飞机模型等资源使用 LFS）

```bash
git lfs install
git clone https://github.com/CyanWing-Flight-Simulation-Platform/CWFLY-WEB.git
cd CWFLY-WEB
```

### 前端

```bash
cd frontend
npm ci
npm run dev
```

访问 <http://localhost:5173>。

生产构建与本地预览：

```bash
npm run build     # 输出 frontend/dist/
npm run preview   # 默认 http://localhost:4173
```

### 后端（本地联调）

```bash
cd backend-py
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中至少配置：

- `DATABASE_URL`：MySQL 连接串
- `JWT_SECRET`：至少 32 字符的随机密钥
- `SMTP_*`：邮箱验证码 / 通知所需
- `CORS_ORIGIN`：本地开发的前端地址

启动：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 3001 --reload
```

### 端口说明

前端开发代理当前指向 `http://localhost:3000`，后端示例配置默认端口为 `3001`。联调时任选一种方式：

1. 后端改到 `3000`：`uvicorn app.main:app --port 3000`，或修改 `.env` 的 `PORT`；
2. 或把 `frontend/vite.config.js` 中的代理目标改为 `3001`。

前端代理覆盖 `/api`、`/uploads`、`/socket.io`，修改后重启 `npm run dev`。

## 功能

| 模块 | 能力 |
|---|---|
| 门户 / 仪表盘 | 首页展示、公告、活动报名、连飞状态、个人统计、签到 |
| 在线地图 | 高德 2D + Mapbox GL 3D 地球 + three.js 飞机模型；实时机组/管制、航迹、管制边界、气象雷达、航迹回放 |
| 航图与机场 | 机场详情、跑道与频率、METAR/TAF 多源查询、航图 PDF 预览 |
| 飞行计划 | 官网提交/编辑、FSD 同步、计划锁定、呼号校验、共享链接 |
| 培训与社区 | 培训考试、课程题库、知识库、通知、积分/成就/排行榜 |
| 申请与工单 | 管制员/职员申请、工单中心、投诉反馈 |
| 管理后台 | 用户与权限、审批、内容审核、审计/登录/网络日志、系统配置、IP/设备封禁 |

访问层级：公开页 → 登录后工作台（`AppLayout`）→ 管理后台（`/admin/*`，按 rating 与细分权限控制）。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3、Vite、Vue Router、Pinia、Axios、Socket.IO Client |
| 地图 / 可视化 | 高德 JSAPI、Mapbox GL JS、three.js、pdf.js、Chart.js |
| 后端 | Python 3.12、FastAPI、SQLAlchemy 2 async、asyncmy、Alembic、MySQL |
| 实时 / 任务 | Socket.IO、Redis、后台定时任务 |
| 部署 | Nginx、PM2、静态资源直出 |

前端为纯 JavaScript 项目，没有 TypeScript 构建步骤。

## 目录结构

```text
CWFLY-WEB/
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── api/              # Axios 实例与业务 API
│   │   ├── components/       # 基础组件、布局、地图组件
│   │   ├── composables/      # 组合式业务逻辑
│   │   ├── router/           # 路由与权限守卫
│   │   ├── store/            # Pinia 状态
│   │   ├── styles/           # tokens/base/dark/mobile 等分层样式
│   │   ├── utils/            # JWT、Socket、主题、PoW 等工具
│   │   └── views/            # 业务页面
│   ├── public/               # 不打包的静态资源（背景、模型、vendor）
│   ├── vite.config.js        # 别名、代理、分包
│   └── package.json
├── backend-py/               # FastAPI 后端
│   ├── app/                  # 路由、服务、中间件、Socket、任务
│   ├── alembic/              # 数据库迁移（baseline）
│   ├── deploy/               # 后端生产部署与运维文档
│   └── .env.example
├── docs/                     # 架构、测试、交接文档
├── .github/workflows/        # 前端 CI
├── CONTRIBUTING.md
├── CHANGELOG.md
├── CLA.md
└── LICENSE
```

## 开发与质量

```bash
cd frontend

npm run test        # Vitest 单元测试
npm run test:watch  # 单元测试 watch
npm run lint        # ESLint（0 warning）
npm run build       # 生产构建
```

- `npm run dev` 已为大型地图页面设置 4 GB Node 堆；内存不足时可提高 `NODE_OPTIONS`。
- CI 在 `frontend/` 变更时执行 `npm ci → test → lint → build`，Node 20/22 双版本。
- 提交前建议至少跑一遍 `npm run lint` 和 `npm run build`。

## 环境变量

前端使用 Vite 构建期变量，模板见 `frontend/.env.example`：

```bash
# 复制为 .env.local（本地）或 .env.production（生产），不要提交真实值
VITE_MAPBOX_TOKEN=
VITE_OWM_KEY=
```

| 变量 | 说明 | 缺失时 |
|---|---|---|
| `VITE_MAPBOX_TOKEN` | Mapbox GL 3D 地球 / 卫星底图 | 3D 地图不可用，可切高德 2D |
| `VITE_OWM_KEY` | OpenWeatherMap 气象雷达图层 | 雷达图层加载失败 |

注意：

- `.env`、`.env.*` 已被忽略；环境变量修改后必须重新构建才会生效。
- 高德 JSAPI Key 目前在源码中配置，需在高德控制台配置域名白名单。
- 后端环境变量、生产配置与迁移说明见 [`backend-py/README.md`](backend-py/README.md) 和 [`backend-py/deploy/PRODUCTION.md`](backend-py/deploy/PRODUCTION.md)。

## 构建与部署

### 构建

```bash
cd frontend
npm ci
npm run build
```

产物位于 `frontend/dist/`，其中 `index.html` 和带 hash 的 `assets/` 可直接由 Nginx 静态返回。

### 部署流程

生产拓扑：`dist/` 上传到服务器 `/opt/cwfly/frontend/dist`，Nginx 静态直出；`/api`、`/socket.io`、`/uploads` 反代到本机后端。

```bash
# 1. 本地构建并打包
cd frontend
npm ci
npm run build
tar -czf /tmp/cwfly-frontend-dist.tgz -C dist .

# 2. 上传（<server> 按运维登记填写）
scp /tmp/cwfly-frontend-dist.tgz root@<server>:/tmp/

# 3. 服务器：备份后增量覆盖
ssh root@<server> '
  cd /opt/cwfly/frontend &&
  cp -a dist "dist.bak-$(date +%Y%m%d-%H%M%S)" &&
  tar -xzf /tmp/cwfly-frontend-dist.tgz -C dist &&
  nginx -t && nginx -s reload
'

# 4. 验证
curl -sI https://www.cwflysim.cn/ | head -n 3
```

**部署纪律：**

1. `dist/` 必须增量覆盖，不要 `rm -rf dist`：旧页面仍可能请求旧 hash 资源。
2. 前端发布不需要重启后端；后端变更只重启 `cwfly-api-py`，禁止 `pm2 restart all`。
3. 静态资源有长缓存，替换图片请换文件名。
4. 先 `nginx -t` 再 `reload`；回滚时恢复上一份 `dist.bak-*`。

## 安全设计

- JWT 登录态 + 活跃滑动续签；登出/改密后旧 token 可失效。
- 设备指纹、登录失败锁定、IP/设备封禁与限流。
- 新 IP 登录触发邮箱二次验证；邮箱验证码与登录挑战均一次性使用。
- 登录挑战绑定 CID + IP，防止仅凭 CID + 验证码直接换取 token。
- 邮箱验证码按 `register` / `login` / `reset` / `bind` 用途隔离，数据库不可用时返回 503。
- 管理操作、登录与网络访问保留审计日志。

## 常见问题

**Q：发布后用户白屏 / 控制台 404？**

A：通常是整体替换了 `dist/`，旧 hash 资源被删除。按增量覆盖重新发布，用户强刷即可恢复。

**Q：本地接口 404 / 登录失败？**

A：检查后端是否启动，以及前端代理 `3000` 与后端端口 `3001` 是否一致（见「端口说明」）。

**Q：在线地图空白或缺少 3D？**

A：检查 `VITE_MAPBOX_TOKEN`、高德 Key 域名白名单；3D 不可用时可切高德 2D。

**Q：登录后很快被踢回登录页？**

A：检查 `/api/auth/refresh`、`localStorage.cw_last_active` 以及服务器时间；超过活跃窗口会要求重新登录。

**Q：`npm ci` 很慢或内存不足？**

A：可临时使用 `npm ci --registry=https://registry.npmmirror.com`；OOM 时提高 `NODE_OPTIONS=--max-old-space-size=8192`。

**Q：`public/` 下为什么有大文件？**

A：背景图、`.glb` 飞机模型和地图 vendor 文件均为运行期按需加载；部分资源使用 Git LFS。

## 文档

| 文档 | 内容 |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 前端架构、路由守卫、布局、状态、实时 Socket、关键文件索引 |
| [`docs/TESTING.md`](docs/TESTING.md) | 测试 / lint / 构建命令与覆盖范围 |
| [`docs/交接文档.md`](docs/交接文档.md) | 服务器角色、Nginx、发布回滚、数据库与排查命令 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 分支策略、提交规范、PR 检查清单、代码约定 |
| [`CHANGELOG.md`](CHANGELOG.md) | 变更记录 |
| [`frontend/docs/performance.md`](frontend/docs/performance.md) | 前端性能与分包记录 |
| [`backend-py/README.md`](backend-py/README.md) | 后端接口、迁移与本地运行 |
| [`backend-py/deploy/PRODUCTION.md`](backend-py/deploy/PRODUCTION.md) | 后端生产部署手册 |

## 许可

本项目以 **GNU General Public License v3.0（GPL-3.0）** 开源，详见 [`LICENSE`](LICENSE)。

贡献前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md) 与 [`CLA.md`](CLA.md)。

© CWFLY 模拟飞行社区 · <https://www.cwflysim.cn>
