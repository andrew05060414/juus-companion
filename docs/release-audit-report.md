# M6 开源发布审计报告

> 创建日期：2026-10-16 ｜ 最后更新：2026-10-26 ｜ 版本：v1.1（经 Senior Reviewer 审查复核并修复）
> 执行主体：Engineer (Fast) · Chariot ｜ 依据：`docs/DATA_POLICY.md` 第 5 节与 `docs/ROADMAP.md` 阶段 7（M6）

## 1. 审计结论

**审计结论：PASS（通过，0 项违规）**

本次审计使用升级后的全量历史扫描工具（覆盖 `git rev-list --all` 全部 27 个提交、根提交 `diff-tree --root` 检查、片段级严格安全豁免与私有目录过滤）。经扫描与人工复核，未发现任何游戏原版素材、Live2D 模型、未脱敏密钥、个人隐私聊天记录、私有网络地址或内部拓扑信息，全量代码与历史提交严格符合 `docs/DATA_POLICY.md` 的开源合规红线。

## 2. 审计范围与指标

- **审计对象**：`andrew05060414/juus-companion` 全量 Git 提交历史（跨所有分支引用）+ 当前工作区代码树
- **历史提交扫描数**：27 / 27 commits（覆盖 `git rev-list --all`）
- **工作区扫描文件数**：95 files
- **Diff 行数审计**：24,560 lines
- **违规项数量**：0 violations

## 3. 分项合规检查

### 3.1 游戏素材与衍生资产守卫（Material Guard）

| 检查项 | 规则与标准 | 检查结果 | 说明 |
|---|---|:---:|---|
| 音频素材 | 禁止提交 `.mp3`, `.wav`, `.ogg`, `.flac`, `.aac`, `.opus`, `.m4a` | ✅ 通过 | 全部分支与工作区无任何音频媒体文件 |
| 图像素材 | 禁止提交 `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.svg`, `.ico` | ✅ 通过 | 全部分支与工作区无任何图像媒体文件 |
| Live2D 资产 | 禁止提交 `.moc`, `.moc3`, `.model3.json`, `.atlas` 等动画文件 | ✅ 通过 | 无任何 Live2D 模型与配置文件 |
| 大体积数据文件 | 非白名单目录下禁止提交 > 1 MiB 的 JSON 数据 | ✅ 通过 | 无超限 JSON；角色生成严格限制在本地 `data/`（已 gitignore） |
| 私有/秘密目录拦截 | 拦截 `deploy/secrets/` 与 `private-data/` | ✅ 通过 | 已在 `.gitignore` 与守卫脚本中双重阻断，禁止跟踪 |

### 3.2 密钥与凭据安全扫描（Secret Guard）

| 检查项 | 规则与标准 | 检查结果 | 说明 |
|---|---|:---:|---|
| LLM 网关与 API Key | 扫描 OpenAI `sk-...`、Anthropic `sk-ant-...` 等格式 | ✅ 通过 | 仅占位符文本，且豁免规则严格限定在命中片段本身 |
| 代码托管与平台凭据 | 扫描 GitHub Token（`ghp_...`, `gho_...`）、AWS Access Key | ✅ 通过 | 无真实 Token |
| 私钥与证书 | 扫描 `BEGIN PRIVATE KEY` 等证书文件 | ✅ 通过 | 无任何私钥或生产证书 |
| 环境变量文件 | 禁止提交生产 `.env` | ✅ 通过 | 仅保留 `.env.example`，`.env` 在 `.gitignore` 中 |

### 3.3 个人隐私与真实网络拓扑（Privacy & Network Guard）

| 检查项 | 规则与标准 | 检查结果 | 说明 |
|---|---|:---:|---|
| 私有 IP 与真实内网 | 扫描 `192.168.x.x`, `10.x.x.x`, Tailscale `100.x.x.x` | ✅ 通过 | 占位符豁免精准生效，未放过任何整行附带泄漏 |
| 本机与 NAS 绝对路径 | 扫描 `/volume1/...`, `C:\Users\...`, `/home/...` | ✅ 通过 | 路径配置统一通过环境变量相对引用 |
| 真实个人聊天记录与记忆 | 禁止提交真实 Chronicle / 微信 / JUUs 聊天记录 | ✅ 通过 | 测试与示例全部使用自造虚构数据 |

### 3.4 许可证与开源合规（License & Compliance）

- **主项目许可证**：GNU Affero General Public License v3.0（AGPL-3.0），见 [LICENSE](../LICENSE)。
- **客户端许可证**：`app-android/` fork 自 [oneroomlife/blyy](https://github.com/oneroomlife/blyy)，遵循 GPL-3.0 许可证，保留原作者署名与版权声明。
- **同人声明（Fan Project Notice）**：在 README、英文文档、部署指南及演示脚本中均显式声明：
  > “本项目为非官方同人衍生项目，与蛮啾网络、上海勇仕、bilibili、Yostar 及碧蓝航线官方没有任何商业或运营关联。仓库不分发任何受版权保护的官方素材。”

## 4. 持续审计与验证工具

为防止后续开发或社区提交引入违规内容，仓库提供两级自动化工具：
1. **工作区素材守卫**：`tools/check_repository_guard.py`（拦截媒体文件、超限 JSON、以及 `deploy/secrets/`、`private-data/` 私有目录，在 CI 中作为前置门禁）。
2. **全量发布审计器**：`tools/audit_release.py`（扫描 `git rev-list --all` 全部分支历史提交与工作树，支持根提交审查与片段级安全豁免）。
3. **单元测试与回归套件**：`tests/test_repository_guard.py` 与 `tests/test_audit_release.py` 已完整覆盖回归用例并接入 `pytest`。

## 5. 仓库公开状态确认

依据 `docs/DATA_POLICY.md` 第 5 节与 Andrew 决策：
- [x] 全量历史扫描完成，0 违规，无须清理 Git 提交历史。
- [x] 文档、部署配置与演示脚本均已脱敏，无个人隐私或真实内网拓扑。
- [x] 开源协议与同人免责声明完备。
- [x] **已于 2026-10-17 经 Andrew 确认将仓库设为 Public。**
