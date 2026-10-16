# deploy

# 啾信 Companion 部署指南（Self-Hosting Guide）

> 创建日期：2026-10-16 ｜ 最后更新：2026-10-16 ｜ 版本：v1.0
> 目标环境：个人 NAS（群晖 Synology / 威联通 QNAP / TrueNAS / Unraid）、Linux 物理服务器或云 VPS

本文档指导指挥官如何在自备服务器或家庭 NAS 上私有化部署 **啾信 Juus Companion** 大脑服务，并配置模型网关、持久化存储与必达通知推送。

## 1. 部署架构概览

```text
 移动端（Android App / PWA）
       │ HTTPS（Cloudflare Tunnel / 反向代理）
       ▼
 ┌───────────── NAS / 服务器宿主机 ─────────────┐
 │                                              │
 │  ┌────────────────────────────────────────┐  │
 │  │        Juus Brain 容器 (FastAPI)       │  │
 │  │  - 角色注册表与世界书按需装载          │  │
 │  │  - 单聊路由与小群导演引擎              │  │
 │  │  - 主动调度器与免打扰时间窗            │  │
 │  │  - 消息真源账本与离线补齐              │  │
 │  └───────┬────────────┬───────────┬───────┘  │
 │          │            │           │          │
 │          ▼            ▼           ▼          │
 │     SQLite 数据卷   本地人设    轻量 ntfy     │
 │     (db/data)      (已生成卡)  (推送兜底)     │
 └──────────┼────────────┴───────────┴──────────┘
            ▼
    外部大模型网关（9router / OneAPI / OpenAI 兼容接口）
```

### 关键原则
1. **服务端为唯一真源**：聊天记录、投递账本、角色人设与记忆均保存在服务端；客户端仅作离线缓存与展现。
2. **零受版权保护资产分发**：Docker 镜像与仓库不包含任何游戏原文或音频。角色卡需在本地运行 pipeline 脚本生成后挂载至容器。
3. **安全红线**：禁止将任何包含真实 IP、域名或 API Key 的配置文件提交至版本控制；所有凭据均通过环境变量注入。

---

## 2. 部署前准备

1. **环境依赖**：
   - Docker Engine 24.0+ 与 Docker Compose v2.0+
   - Python 3.12+ 与 uv（若需在宿主机直接运行数据流水线）
2. **模型服务**：
   - 任意 OpenAI 兼容的 API 接口（如 9router、OneAPI、DeepSeek、OpenAI、Ollama 本地大模型）
3. **网络与访问**：
   - 本地内网访问：使用局域网 IP 或 Tailscale 组网访问
   - 公网必达访问：推荐使用 **Cloudflare Tunnel**（零开放端口、自动 HTTPS 证书）或 Nginx 反向代理

---

## 3. 快速上手（Docker Compose）

### 步骤 1：复制配置文件模板

进入 deploy 目录：

```sh
cd deploy
cp .env.example .env
```

编辑 `.env`，填入你的模型网关地址与密钥：

```env
JUUS_PORT=8000
MODEL_GATEWAY_BASE_URL=https://api.your-model-gateway.example/v1
MODEL_GATEWAY_API_KEY=your_actual_api_key_here
DEFAULT_MODEL=deepseek-chat
```

### 步骤 2：准备角色卡数据

在仓库根目录下运行流水线脚本（或手动将已生成的 SillyTavern / Juus Brain 格式角色卡放置在 data/personas）：

```sh
# 本地生成角色卡（详见 pipeline/README.md）
uv run python pipeline/run.py
```

### 步骤 3：启动服务

使用 docker-compose.example.yml 启动服务：

```sh
docker compose -f docker-compose.example.yml up -d
```

查看运行状态与容器日志：

```sh
docker compose -f docker-compose.example.yml ps
docker compose -f docker-compose.example.yml logs -f juus-brain
```

### 步骤 4：健康检查与服务验证

在大脑服务启动后，验证健康状态：

```sh
curl -s http://127.0.0.1:8000/health
# 预期返回: {"status": "ok", "service": "juus-brain"}
```

---

## 4. 必达推送配置（Push Notifications）

啾信采用“**双路推送路由**”确保消息不遗漏：

1. **FCM（Firebase Cloud Messaging，推荐主通道）**：
   - 适用于带有 Google 服务的海外或国际版 Android 设备。
   - 前往 Firebase 控制台下载 service-account.json，放置在宿主机安全目录（如 deploy/secrets/fcm.json，已被 gitignore 忽略）。
   - 在 .env 中配置 FCM_CREDENTIALS_FILE=/app/secrets/fcm.json。
2. **ntfy（轻量自建，推荐国内或无 GMS 兜底）**：
   - docker-compose.example.yml 中已内置 juus-ntfy 容器。
   - 客户端 App 订阅指定 Topic，服务端通过 HTTP POST 发送唤醒事件。
   - 无论网络切换或进程后台休眠，打开 App 后均会向账本拉取游标自动补齐。

---

## 5. 数据持久化与备份建议

Docker 挂载卷包含以下关键数据：
- juus_data：存放 SQLite 数据库文件（会话、账本、记忆索引）。
- ../data/personas：存放生成的角色卡与世界书（只读挂载）。
- ../data/chronicle：个人长程记忆库（可选挂载）。

---

## 6. 安全与运维红线

1. **管理接口隔离**：请勿将未经鉴权的端口直接映射至公网。公网访问务必经由 HTTPS 反向代理或 VPN/Tailscale 隧道。
2. **凭据安全**：禁止在版本库或公开工单中粘贴 .env、FCM 密钥文件或 Cookie。
3. **非官方免责声明**：对外提供服务时，须保留“非官方同人衍生项目”提示，不可用于任何商业获利行为。

