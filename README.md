# 啾信 Companion（juus-companion）

[English Documentation](README_EN.md) ｜ [中文说明](README.md)

> 创建日期：2026-09-27 ｜ 最后更新：2026-10-16 ｜ 版本：v0.2（M6 开源发布就绪）

一个“会主动找你聊天”的碧蓝航线同人陪伴 AI：每位舰娘都是独立的聊天成员，可以单聊，也可以几个人在小群里像游戏里的「啾信」一样自然交流；她们会按自己的节奏发消息、发 JUUs 动态、提醒你的日程，通知必达，历史可查。

> **非官方同人项目声明**：本项目与蛮啾网络、上海勇仕、bilibili、Yostar 及碧蓝航线官方没有任何商业或运营关联。仓库**不包含**任何游戏原文、语音、立绘、Live2D 或由其生成的角色卡；这些内容由使用者在本地通过导入脚本自行获取，仅供个人学习与离线研究使用。

---

## 核心特性

- **独立成员单聊**：每位舰娘拥有独立身份与头像，流式回复，深度融入人设与口吻。
- **主动关怀与日程提醒**：按角色专属习惯与免打扰时间窗主动发消息，舰娘可自建提醒（如早安唤醒、自习刷题监督）。
- **独创群聊导演引擎**：支持 2~6 人小群聊，导演调度轮次与发言角色，内置 `[SKIP]` 与防循环机制，告别死循环互聊。
- **JUUs 社交动态流**：角色自发展开朋友圈发帖、互相评论点赞，并随时 @指挥官 互动。
- **双路必达通知**：FCM（主通道）+ 自建轻量 ntfy（兜底）；服务端账本保证离线消息打开即补齐，不遗漏、不重复。
- **长期记忆与知识库**：短期上下文结合长期记忆适配层（Chronicle / Mnemosyne），自然引用过往对话与指挥官背景。
- **折叠屏适配**：针对三星 Galaxy Z Fold 7 等 Android 折叠屏提供展开双栏（会话列表 + 对话区）与合上单栏视图。

---

## 项目导航与关键文档

- **架构与需求**：
  - [产品需求 PRD](docs/PRD.md)
  - [架构设计草案](docs/ARCHITECTURE.md)
  - [路线图与里程碑](docs/ROADMAP.md)
  - [数据、隐私与开源政策](docs/DATA_POLICY.md)
  - [技术决策记录 ADR](docs/decisions/)（ADR-0003 大脑形态已定稿：A 独立服务为主线）
- **开源发布与部署**：
  - [全量发布审计报告 (M6)](docs/release-audit-report.md)
  - [自部署指南 (NAS / Docker Compose)](deploy/README.md)
  - [演示视频分镜头脚本](docs/demo-video-script.md)
  - [AI 开发与 Agent 协作规程](AGENTS.md)

---

## 组成模块

| 目录 | 模块内容 | 许可证 | 状态 |
|---|---|:---:|:---:|
| `server/` | 啾信大脑：角色注册表、会话、群聊导演、主动调度、投递账本、推送 | AGPL-3.0 | 架构与接口已定稿，骨架就绪 |
| `pipeline/` | 人设流水线：从公开解包数据抽取并生成 SillyTavern / AstrBot 角色卡 | AGPL-3.0 | 已实现 v1，本地运行 |
| `deploy/` | 开源自部署：Docker Compose 模板、环境变量配置、ntfy 必达推送 | AGPL-3.0 | 模板与指南完备 |
| `adapters/` | 外部适配层：AstrBot 插件、Chronicle 记忆系统集成 | AGPL-3.0 | 规划中 |
| `app-android/` | Android 原生客户端（fork 自 [oneroomlife/blyy](https://github.com/oneroomlife/blyy)） | GPL-3.0 | 源码审计完成，待集成接入 |
| `pwa/` | iPhone / Web 客户端 | AGPL-3.0 | 规划中 |

---

## 开发入门与本地检查

### 环境准备

工具链固定为 Python 3.12 与 [uv](https://docs.astral.sh/uv/)。在仓库根目录执行：

```sh
uv sync
```

### 本地环境变量配置

```sh
cp .env.example .env
```

编辑 `.env`，配置本地大模型网关地址与 API 密钥。

### 自动化测试与开源守卫门禁

提交代码前请运行以下检查：

```sh
# 1. 代码规范与格式检查
uv run ruff check .
uv run ruff format --check .

# 2. 全量单元测试
uv run pytest

# 3. 敏感素材守卫（拦截音频、图片、Live2D 与超限文件）
uv run python tools/check_repository_guard.py

# 4. 全量历史与开源发布审计器（扫描密钥、私网拓扑与历史 Commit）
uv run python tools/audit_release.py
```

---

## 人设数据流水线（Pipeline）

人设流水线用于在本地将公开解包文本转化为 SillyTavern 角色卡与世界书。所有游戏原文素材与生成的私有人设卡均保存在本地 `data/`（已被 `.gitignore` 忽略），严格遵守数据红线。

```sh
# 运行流水线
uv run python pipeline/run.py

# 运行流水线专项测试
uv run pytest tests/test_batch.py tests/test_e2e_pipeline.py tests/test_exporter.py tests/test_extractor.py tests/test_fetcher.py tests/test_generator.py tests/test_validator.py
```

---

## 私有化部署（Self-Hosting）

完整部署指南请参阅 [deploy/README.md](deploy/README.md)。

```sh
cd deploy
cp .env.example .env
docker compose -f docker-compose.example.yml up -d
```

---

## 开源许可证与版权声明

1. **开源许可证**：
   - 本项目除 `app-android/` 目录采用 **GPL-3.0** 许可证（继承自 upstream 项目 blyy）外，整体以 **AGPL-3.0** 许可证开源（详见 [LICENSE](LICENSE)）。
2. **版权声明**：
   - 碧蓝航线（Azur Lane）及其角色、原声、美术、世界观与官方衍生文本版权均归属于其原始权利人（上海蛮啾网络、上海勇仕网络、bilibili 及 Yostar 等）。
   - 本项目为同人交流与技术研究之用，不含官方专有资源，严禁用于任何商业牟利行为。
