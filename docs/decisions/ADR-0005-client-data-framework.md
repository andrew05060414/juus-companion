# ADR-0005：客户端与数据层框架 — fork 起步、独立项目演进、DB 分离

> 创建日期：2026-10-05 ｜ 最后更新：2026-10-05 ｜ 版本：v0.1 ｜ 状态：提议
> 对应任务：Multica PX-866（blyy 路线）、Andrew 2026-10-05 指示"explore and make the frame work first"

## 摘要

Android 客户端以 fork `oneroomlife/blyy` 起步（已建 `andrew05060414/blyy`），但**从第一天起就按"未来会变成独立开源项目"来划边界**：新代码全部进 `com.juus.*` 命名空间、只通过服务端 API 拿数据、任何游戏衍生内容永不进客户端仓库。DB 不单独建 repo：**服务端是唯一真源**，客户端本地只做缓存；游戏衍生数据已有私有 `juus-data` 承载，经服务端在运行时提供。本 ADR 先定框架，功能开发按框架走。

## 背景与决策驱动因素

- 2026-10-05 决定：不再新写 App，fork blyy 做 Android 客户端，后端自建（ADR-0003：A 独立服务为主线）。
- fork 继承 GPL-3.0，且上游代码与游戏资产强相关（语音 URL 解析、头像资源）。长期以 fork 形态发布/上架，IP 边界会越来越难理清；M6 本来就要做开源发布。
- Andrew 指示：现在基于当前 repo 改，但以后可能变成独立项目（仍开源）；DB 要独立 repo 或其他方式隔离，规避未来的法律风险；先搭框架再做功能。
- ARCHITECTURE.md 既定：服务端是角色、会话、消息、记忆的唯一真源；密钥不进客户端。

## 决策

### 1. 客户端演进路径：fork（现在）→ 独立项目（以后）

分三个阶段，触发条件明确写死，不设模糊的"以后再说"：

| 阶段 | 做什么 | 触发条件 |
|---|---|---|
| P1 fork 起步（现在） | 在 `andrew05060414/blyy` 上加功能；所有 Juus 新代码进 `com.juus.*`，见第 3 节规则 | 已开始（PX-868） |
| P2 API 化（M1 同步） | fork 里所有 Juus 功能走服务端 API：不再直连模型、不再以本地 DataStore 为真源；本地只做带同步游标的缓存 | 服务端 API 稳定（`docs/api/openapi.yaml` v1 冻结） |
| P3 独立项目 | 新建 `andrew05060414/juus-android`（暂定名），干净 UI，直接复用 `com.juus.*` 模块；丢掉上游 blyy 代码 | 任一成立：① fork 的 GPL/游戏资产纠缠成为发布阻塞；② M6 开源发布准备开始；③ Andrew 拍板 |

P3 的 repo 许可证到时再定（候选：Apache-2.0；GPL-3.0 传染性在此不适用，因为 P3 不含上游代码）。

### 2. DB  placement：不另建 repo，服务端独占真源

评估过的选项：

- **A. 服务端独占 DB，客户端只做缓存（推荐）**：DB（Postgres/SQLite）在服务端 repo 内；客户端本地存储明确定义为"带 TTL 和同步游标的缓存"，不是真源。游戏衍生数据走 `juus-data`（私有）→ 服务端启动时加载 → API 运行时提供，**永不进入任何客户端 repo**。
- B. 独立 `juus-db` repo（schema + migration 共享）：多一个 repo 的版本维护成本，只有客户端需要离线关系型查询时才值得，目前看不到这个需求。
- C. 客户端 repo 内独立 Gradle 模块：达不到 repo 级隔离，不解决法律顾虑。

选 A 的理由：与"服务端唯一真源"一致；法律隔离效果与 B 相同（隔离的关键是游戏数据不进客户端 repo，不是 schema 放哪）；维护成本最低。Andrew 要的"DB 独立"实质已经由私有 `juus-data` 承担——本 ADR 把这条链路正式定为框架：`juus-data` → 服务端 → API → 客户端缓存。

### 3. fork 内的代码边界规则（即刻执行）

1. **命名空间**：所有 Juus 新代码放在 `com.juus.*` 下，禁止新增 `com.azurlane.blyy.*` 下的 Juus 功能代码。例外：PR blyy#1 的 `data/persona/PersonaPackImporter.kt` 写在了上游命名空间下，**合并前必须搬到 `com.juus.persona`**。
2. **依赖方向**：`com.juus.*` 不得 import 上游的游戏资产相关模块（语音 URL 解析、头像资源）；只允许依赖上游的通用 UI/基础设施（Compose 组件、DataStore 读写、HTTP client）。
3. **数据规则**：`com.juus.*` 不得内置、下载后转存游戏语音/立绘/原文到 repo；运行时数据一律走服务端 API（P2 起）或用户手工输入（P1 过渡）。
4. **审查卡点**：以后每个 fork PR 的 review 清单加一条"命名空间与依赖方向检查"。

### 4. Repo / 模块地图（框架）

| Repo | 公开性 | 放什么 |
|---|---|---|
| `juus-companion` | public | 代码、流水线、文档、ADR、**服务端 API 契约**（`docs/api/openapi.yaml`，待写） |
| `andrew05060414/blyy` | public fork | 短期 Android 客户端；我们的代码在 `com.juus.*` |
| `juus-data` | private | 881 卡、世界书、语音索引——纯数据，无代码 |
| `juus-server`（新建，M1 开工时） | 待定（建议先 private，M6 前再定） | M1 后端；独占 DB；实现 API 契约 |
| `juus-android`（未来，P3 触发时） | public | 独立客户端，复用 `com.juus.*` 模块 |

数据流：`juus-data` → `juus-server`（启动加载/定时同步）→ API → 客户端缓存。任何方向都不允许游戏衍生内容写入客户端 repo。

### 5. "框架先行"的交付顺序

1. 本 ADR（提议 → Andrew 接受）。
2. `docs/api/openapi.yaml` v1 草稿：认证、人设、会话、消息、记忆、推送注册、同步游标——这是 B/C 两端（服务端 M1 与 fork P2）的共同接口，先冻结接口再并行开工。
3. blyy#1 的命名空间搬移（合并前）。
4. 之后才进 M1 服务端实现与 fork P2 改造。

## 未覆盖与风险

- P3 独立项目的 UI 是重写还是从 fork 提取，届时看 `com.juus.*` 的纯净度再定；本 ADR 只保证"能搬"，不承诺"零改动搬"。
- GPL-3.0 对 fork 阶段的要求（修改后分发需开源）我们天然满足（fork 本来就是 public）。
- 上游 blyy 若引入破坏性改动，fork 的同步成本由维护者承担；P3 之后不再有此问题。
- `juus-server` 的公开性未定：建议 M1 期间先 private，避免把未完成的鉴权/密钥管理暴露出去；M6 前按本 ADR 的"无游戏内容进 repo"原则重新评估。

## 备选（未采纳）

- 现在就建独立 `juus-android`：时机太早，服务端 API 还不存在，独立项目没有数据源；且 fork 已验证可用，抛弃它重写 UI 是浪费。
- 独立 `juus-db` repo：见第 2 节，不值得。
