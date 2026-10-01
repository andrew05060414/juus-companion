# 啾信 Companion（juus-companion）

> 创建日期：2026-09-27 ｜ 最后更新：2026-09-27 ｜ 版本：v0.1（立项）

一个"会主动找你聊天"的碧蓝航线同人陪伴 AI：每位舰娘都是独立的聊天成员，可以单聊，也可以几个人在小群里像游戏里的「啾信」一样聊天；她们会按自己的节奏发消息、发 JUUs 动态、提醒你的日程，通知必达，历史可查。

> **非官方同人项目**：本项目与蛮啾网络、上海勇仕、bilibili、Yostar 及碧蓝航线官方没有任何关系。仓库**不包含**任何游戏原文、语音、立绘、Live2D 或由其生成的角色卡；这些内容由使用者在本地通过导入脚本自行获取，仅供个人使用。

## 当前状态

立项阶段。计划、需求与架构见：

- [产品需求 PRD](docs/PRD.md)
- [架构草案](docs/ARCHITECTURE.md)
- [路线图与工作量](docs/ROADMAP.md)
- [数据、隐私与开源政策](docs/DATA_POLICY.md)
- [AI 开发规则（给 Agent 看的）](AGENTS.md)
- [决策记录](docs/decisions/)

## 组成（计划）

| 目录 | 内容 | 许可证 |
|---|---|---|
| `server/` | 啾信大脑：角色、会话、群聊导演、主动消息、投递账本、推送 | AGPL-3.0 |
| `pipeline/` | 人设流水线：从公开解包数据生成 SillyTavern 角色卡与世界书（在本地运行） | AGPL-3.0 |
| `adapters/` | 与 AstrBot、Chronicle 等外部系统的适配 | AGPL-3.0 |
| `app-android/` | Android 客户端（基于 [oneroomlife/blyy](https://github.com/oneroomlife/blyy) 修改） | GPL-3.0 |
| `pwa/` | iPhone 等设备的网页 App | AGPL-3.0 |
| `deploy/` | 部署配置样例（不含任何密钥） | AGPL-3.0 |

## 开发入门

### 环境

开发工具链固定为 Python 3.12、[uv](https://docs.astral.sh/uv/)、Ruff 和
pytest。安装 uv 后，在仓库根目录运行：

```sh
uv sync
```

`server/` 与 `pipeline/` 共用根目录的 `pyproject.toml` 和 `uv.lock`，但
代码分别放在自己的 `src/` 目录中。这样可以让 lint/test 工具只有一份锁定
版本，同时避免两个运行时包互相导入。

### 本地配置

复制 `.env.example` 为 `.env`，再填入本机模型网关地址和密钥：

```sh
cp .env.example .env
uv run --env-file .env pytest
```

`.env`、模型网关密钥、数据库和推送凭据都不得提交。运行时代码只从环境变量
读取配置；仓库中的 `.env.example` 仅是无效占位值。

### 本地检查

提交前运行与 CI 相同的检查：

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python tools/check_repository_guard.py
```

素材守卫检查 Git 已跟踪文件和本地未忽略文件：音频、图片、Live2D 文件一律拒绝；超过 1 MiB
的 JSON 只能放在本地 `data/` 或使用虚构数据的 `tests/fixtures/`。`data/`
本身已被 `.gitignore` 忽略。想在不提交测试文件的情况下验证某个候选文件，可
显式传入路径：

```sh
uv run python tools/check_repository_guard.py --paths server/candidate.ogg
```

密钥扫描由 GitHub Actions 中的 gitleaks 执行。验证守卫时可以在临时分支放入
假 `.ogg` 或假密钥；看到失败输出后删除临时文件和提交，不能把验证样例合入
本仓库。

## 许可证

除 `app-android/`（GPL-3.0，继承自 blyy）外，本仓库以 [AGPL-3.0](LICENSE) 发布。游戏相关内容的版权归其各自权利人所有，不在本许可证范围内。
