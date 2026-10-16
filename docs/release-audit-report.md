# M6 开源发布审计报告

> 创建日期：2026-10-16 ｜ 最后更新：2026-10-16 ｜ 版本：v1.0
> 执行主体：Engineer (Fast) · Chariot ｜ 依据：`docs/DATA_POLICY.md` 第 5 节与 `docs/ROADMAP.md` 阶段 7（M6）

## 1. 审计结论

**审计结论：PASS（通过，0 项违规）**

本次审计覆盖从仓库初始提交（`e46b063`）至当前 HEAD（`7fae2b1`）的全部 12 个历史提交以及工作区当前全部已跟踪与未忽略文件。经自动化扫描与逐项人工复核，未发现任何游戏原版素材、Live2D 模型、未脱敏密钥、个人隐私聊天记录或内部网络拓扑信息，代码与文档完全符合 `docs/DATA_POLICY.md` 的开源合规红线。

## 2. 审计范围与指标

- **审计对象**：`andrew05060414/juus-companion` 全量 Git 提交历史 + 工作区代码树
- **历史提交扫描数**：12 / 12 commits
- **工作区扫描文件数**：90 files
- **Diff 行数审计**：10,217 lines
- **违规项数量**：0 violations

## 3. 分项合规检查

### 3.1 游戏素材与衍生资产守卫（Material Guard）

| 检查项 | 规则与标准 | 检查结果 | 说明 |
|---|---|:---:|---|
| 音频素材 | 禁止提交 `.mp3`, `.wav`, `.ogg`, `.flac`, `.aac`, `.opus`, `.m4a` | ✅ 通过 | 历史与当前树无任何音频文件 |
| 图像素材 | 禁止提交 `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.svg`, `.ico` | ✅ 通过 | 历史与当前树无任何媒体图片 |
| Live2D 资产 | 禁止提交 `.moc`, `.moc3`, `.model3.json`, `.atlas` 等动画文件 | ✅ 通过 | 历史与当前树无任何 Live2D 资产 |
| 大体积数据文件 | 非白名单目录下禁止提交 > 1 MiB 的 JSON 数据 | ✅ 通过 | 无超限 JSON；角色生成仅在本地 `data/`（已 gitignore） |

### 3.2 密钥与凭据安全扫描（Secret Guard）

| 检查项 | 规则与标准 | 检查结果 | 说明 |
|---|---|:---:|---|
| LLM 网关与 API Key | 扫描 OpenAI `sk-...`、Anthropic `sk-ant-...` 等格式 | ✅ 通过 | 仅 `.env.example` 中保留安全占位符 |
| 代码托管与平台凭据 | 扫描 GitHub Token（`ghp_...`, `gho_...`）、AWS Access Key | ✅ 通过 | 无真实 Token，CI 使用 GitHub Secret |
| 私钥与证书 | 扫描 `BEGIN PRIVATE KEY` 等证书文件 | ✅ 通过 | 无任何私钥或生产证书 |
| 环境变量文件 | 禁止提交生产 `.env` | ✅ 通过 | 仅保留 `.env.example`，`.env` 在 `.gitignore` 中 |

### 3.3 个人隐私与真实网络拓扑（Privacy & Network Guard）

| 检查项 | 规则与标准 | 检查结果 | 说明 |
|---|---|:---:|---|
| 私有 IP 与真实内网 | 扫描 `192.168.x.x`, `10.x.x.x`, Tailscale `100.x.x.x` | ✅ 通过 | 文档与配置样例仅包含泛化占位符 |
| 本机与 NAS 绝对路径 | 扫描 `/volume1/...`, `C:\Users\...`, `/home/...` | ✅ 通过 | 路径配置统一通过环境变量相对引用 |
| 真实个人聊天记录与记忆 | 禁止提交真实 Chronicle / 微信 / JUUs 聊天记录 | ✅ 通过 | 测试与示例全部使用自造虚构数据 |

### 3.4 许可证与开源合规（License & Compliance）

- **主项目许可证**：采用 GNU Affero General Public License v3.0（AGPL-3.0），见 [LICENSE](../LICENSE)。
- **客户端许可证**：`app-android/` fork 自 [oneroomlife/blyy](https://github.com/oneroomlife/blyy)，遵循 GPL-3.0 许可证，保留原作者署名与版权声明。
- **同人声明（Fan Project Notice）**：在 README、英文文档、部署指南及演示脚本中均显式声明：
  > “本项目为非官方同人衍生项目，与蛮啾网络、上海勇仕、bilibili、Yostar 及碧蓝航线官方没有任何商业或运营关联。仓库不分发任何受版权保护的官方素材。”

## 4. 全量历史提交审计清单

| Commit | 类型 | 提交说明 | 审计结论 |
|---|---|---|:---:|
| `e46b063` | chore | bootstrap juus-companion (PRD, architecture, roadmap, data policy) | ✅ Clean |
| `c7c5c07` | feat | 建立 M0-1 工程骨架与仓库守卫 (#7) | ✅ Clean |
| `8b30b8b` | feat | M0-2 人设流水线 v1 + 首批 8 张角色卡 (#2) (#5) | ✅ Clean |
| `f456ac0` | rebase | land M0-3 brain-shape prototypes on current main (#6) | ✅ Clean |
| `2f2fe75` | rebase | place M0-4 evaluation baseline after M0-3 (#8) | ✅ Clean |
| `f0fdf07` | docs | 将 ADR-0003 状态变更为已接受 | ✅ Clean |
| `235b393` | docs | audit blyy chat and backend gaps | ✅ Clean |
| `31cf698` | docs | ADR-0005 客户端与数据层框架（提议） | ✅ Clean |
| `3d6bcfc` | docs | 增加首批 8 张卡与 881 位批量卡抽样 12 位试聊清单 (#14) | ✅ Clean |
| `0bd9b27` | merge | Merge PR #11 (ADR-0003 已接受) | ✅ Clean |
| `abcfd83` | merge | Merge PR #12 (blyy 源码审计) | ✅ Clean |
| `7fae2b1` | merge | Merge PR #13 (ADR-0005 客户端数据层框架) | ✅ Clean |

## 5. 持续审计与验证工具

为防止后续开发或开源后社区提交引入违规内容，仓库提供两级自动化工具：
1. **工作区素材守卫**：`tools/check_repository_guard.py`（拦截媒体文件与超限 JSON，在 CI 中作为前置门禁）。
2. **全量发布审计器**：`tools/audit_release.py`（扫描从初次提交至 HEAD 的全量历史，覆盖素材、密钥、网络与隐私泄露）。
3. **单元测试与回归套件**：`tests/test_audit_release.py` 已纳入整体 `pytest` 测试集。

## 6. Andrew 最终批准门禁（🛑 停止点）

依据 `docs/DATA_POLICY.md` 第 5 节与总控任务规程：
- [x] 全量历史扫描完成，0 违规，无须清理 Git 提交历史。
- [x] 文档、部署配置与演示脚本均已脱敏，无个人隐私或真实内网拓扑。
- [x] 开源协议与同人免责声明完备。
- [ ] **🛑 待 Andrew 最终批准后，方可在 GitHub 仓库设置中将仓库属性从 Private 改为 Public。**

