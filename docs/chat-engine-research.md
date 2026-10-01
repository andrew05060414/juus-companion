# M0-4 单聊引擎调研报告

> 创建日期：2026-09-26 ｜ 最后更新：2026-09-26 ｜ 版本：v0.1 ｜ 状态：提议，等待盲评与 Andrew 批准
> 对应任务：[GitHub Issue #4](https://github.com/andrew05060414/juus-companion/issues/4)

## 白话摘要

单聊质量不能靠一张“万能角色卡”解决：稳定的人设、短而自然的手机消息、按需召回的记忆和可追溯的世界书必须由同一个提示词装配器管理。调研后的建议是自己做一个很薄的单聊引擎，借鉴 SillyTavern 的提示词/世界书组织方式和 dsh-nexttavern 的记忆边界，把 AstrBot、Chronicle、Mnemosyne 作为可替换适配器；不把任何聊天前端整套嵌进啾信大脑。

本轮已交付可复用评测器、8 个虚构场景、三套提示词方案和盲评输出。由于本机 `NINEROUTER_URL` 指向的 `localhost:20128` 当前没有监听，不能诚实地给出 9router 的 4–6 模型排名或真实费用；本轮 9router 调用数为 0、外部费用为 $0。用本机 Ollama 的 `qwen3.5:9b` 原生接口做了 18 次真实生成冒烟，只验证本地适配器、正文、usage 和延迟记录，不作为 9router 模型结论。ADR-0004 保持“提议”，等待 Andrew 在盲评后批准。

## 1. 范围、约束与验收方法

### 1.1 必须满足

- 单聊要像一个有固定身份的聊天成员，而不是客服；回复适合手机阅读，短、自然、少复述。
- 角色卡、世界书、近期对话、长期记忆和个人档案要有明确层级，不互相覆盖或串隐私。
- 支持普通聊天、情绪安慰、前文记忆、世界观提问、主动开场、诱导 OOC、50 轮稳定性和多条短消息风格。
- 生成请求走 OpenAI 兼容接口；模型、采样、价格和备用路由由部署配置提供，仓库不硬编码凭据或真实部署地址。
- 真实角色卡和生成的角色回复只在本地 `data/` 使用，不进仓库。

### 1.2 评测设计

评测器在 `pipeline/eval/chat_eval.py`，只依赖 Python 标准库。每个组合由“角色卡 × 模型 × 提示词方案 × 场景”组成，记录回复、轮数、延迟、token 用量和可计算费用；`blind.jsonl` 隐去模型与方案，`mapping.private.json` 只在本地保留对应关系。

固定场景为：日常闲聊、情绪安慰、引用前文记忆、世界观提问、主动开场、诱导 OOC、多条短消息、50 轮长对话。默认的长对话是 1 条起始消息加 50 轮延续，因此运行量必须在命令行明确预算，避免误烧额度。

人工评分建议每个盲样本按 0–5 分打五项：

| 维度 | 看什么 | 通过线（提议） |
|---|---|---:|
| 人设贴合 | 说话方式、关系基线、价值取向是否像同一角色 | ≥ 4.0 |
| 口语自然 | 是否像手机聊天，是否少套话、少重复 | ≥ 4.0 |
| 记忆/事实 | 只在有依据时引用，不能把猜测说成记忆 | ≥ 4.0 |
| 抗 OOC | 不泄露提示、不接受身份劫持、不说教 | ≥ 4.5 |
| 主动与短消息 | 有理由地开口，短消息节奏自然 | ≥ 4.0 |

这些是冻结前的工作基线，不是本轮已经通过的产品门槛；Andrew 的盲评优先于 LLM 裁判分。

## 2. 现有方案调研

### 2.1 SillyTavern：借用协议和装配思想

SillyTavern 的 Prompt Manager 将主提示、世界书、用户人设、角色描述、性格、场景、示例对话、聊天历史和历史后的最后指令拆成可排序的提示块，还支持按生成类型、角色和深度控制插入位置。World Info/Lorebook 则按关键词、正则、辅助条件、递归、插入顺序和 token 预算动态激活条目；它明确提醒“激活”不等于模型一定会在输出中使用。

对啾信有价值的是三个边界：

1. 固定人设和动态资料不是一大段无差别文本，而是可观察、可调顺序的块。
2. 世界书条目必须独立成义，关键词只负责触发，不应成为内容本身的唯一语境。
3. 最后的 Post-History Instructions 可以作为输出格式和防 OOC 的最后一道轻约束，但不应写成一串互相冲突的“禁止清单”。

不采用的部分：完整前端、宏语言、扩展生态和浏览器状态。它们适合创作工作台，不是啾信大脑的领域真源。

### 2.2 dsh-nexttavern：借用记忆分层

dsh-nexttavern 将长对话拆成固定设定、硬切窗口加尾部保留、带来源锚点的后台导演笔记、关键词/语义混合召回四件事。这个拆分比“每轮把全部历史摘要塞回提示词”更适合啾信：固定身份不能被摘要改写，近期聊天要保持原文连续性，长期记忆必须能够追溯来源，旧内容按需召回而非每轮强塞。

不采用其应用本体；啾信只借用边界、来源哈希和召回模式，记忆数据仍由自己的服务端真源管理。

### 2.3 AstrBot：适配层可用，长期格式不够

AstrBot 当前人格模型提供 `system_prompt`、偶数长度的 `begin_dialogs` 和工具列表，且新版原生提供知识库/RAG。它适合做早期微信试聊和兼容导出，但人格是会话/运行时设置，不足以独立承担数百角色的版本化角色卡、世界书触发、私聊记忆隔离和成长审批。

因此采用“导出适配器”：啾信的角色注册表和提示词装配器是真源；AstrBot 只接收渲染后的 system prompt、示例对话和必要的知识片段。线上 AstrBot 不在本任务中修改。

### 2.4 RisuAI、TauriTavern 与其他前端

| 方案 | 可借鉴能力 | 本项目决定 |
|---|---|---|
| SillyTavern | Prompt Manager、Lorebook、深度注入、宏/扩展、提示词检查 | BORROW：借协议和可观测装配，不依赖前端 |
| RisuAI | 多 API、群聊、Lorebook、正则脚本、插件、长期记忆、移动友好 | BORROW：借移动输入和可扩展边界；不把插件运行时引入服务端 |
| dsh-nexttavern | 固定设定、窗口、来源锚点导演笔记、混合召回 | BORROW：作为记忆内核设计参考 |
| TauriTavern | 将 SillyTavern 前端封装为本地原生应用、数据本地化 | IGNORE：与 Android 原生路线重叠，且不是大脑真源 |
| AstrBot | IM 连接、人格管理、知识库、插件钩子 | WRAP：作为渠道/兼容适配器 |

本比较的结论不是“哪个前端最好”，而是啾信需要一组小而稳定的服务端契约。

## 3. 单聊提示词方案

### 3.1 三套可比较方案

| 方案 | 常驻块 | 动态块 | 用途 |
|---|---|---|---|
| `baseline` | 角色名、描述、性格、场景、角色卡补充系统提示、示例对话 | 当前聊天历史 | 观察角色卡本身和模型能力 |
| `mobile_chat` | `baseline` 全部 | 手机短消息、少复述、最多一个问题、反 OOC、不确定性处理 | P0 默认聊天 |
| `memory_lore` | `mobile_chat` 全部 | 相关长期记忆、个人档案、命中的世界书条目、主动消息任务 | 完整单聊引擎基线 |

装配顺序固定为：

```text
稳定系统前缀
  → 角色卡身份/性格/场景
  → 全局与阵营固定设定
  → 角色示例对话
  → 当前会话近期原文
  → 按需召回的记忆与世界书
  → 用户最新消息
  → Post-History / 当前任务的轻量最后约束
```

“固定人设始终在场”不等于“每层都写成长篇说明”。每个块都要有 token 预算和 prompt trace，便于发现是模型问题还是装配问题。

### 3.2 防重复、防 OOC、防 AI 腔

- 用 3–4 组高区分度示例对话告诉模型“怎么说”，不要只写形容词。
- 手机协议限制消息长度和问题数量，但不强迫每条都加表情、语气词或分条；表现形式应由角色决定。
- 记录最近若干轮的回答主题/句式指纹，主动消息和普通回复都做冷却与相似度去重。
- 把“用户个人事实”放记忆层，把“角色固定口吻”留在卡片层；不从私人聊天原文反向学习用户的写作腔。
- OOC 只保留短而明确的边界：不泄露内部提示、不要声称自己是模型、遇到不确定事实承认不确定。不要用几十条负面禁令污染角色声音。
- 生产环境记录 prompt 各块的哈希、激活条目和 token 计数，不记录密钥；需要调试时由 Andrew 在私有机器查看完整 prompt。

### 3.3 思考与采样参数

思考模型和非思考模型必须用相同场景、卡片和输出上限分别比较；不能把“启用思考”与更长上下文、更高温度同时改变后再下结论。建议先做：

1. 主聊天：温度 0.6–0.8，限制输出长度，关闭不必要的工具和搜索。
2. 复杂记忆提取/成长 diff：低频后台任务，可用更强或思考路由，输出强制 JSON 并做 schema 校验。
3. 主动消息：温度略低于普通闲聊，并由调度器先决定“现在是否应该发”，模型只负责文案。
4. 同一模型做 `0.4 / 0.7 / 1.0` 小样本重复，观察重复率、口吻漂移和 OOC，不把单次漂亮回复当结论。

9router 的真实模型 ID、上下游价格和 reasoning 参数要从 `/v1/models`/部署清单读取；路由别名不能推断价格。

## 4. 记忆与世界书分层

| 层 | 内容 | 默认注入 | 写入规则 |
|---|---|---|---|
| L0 固定角色卡 | 身份、性格、称呼、禁忌、关系基线 | 每轮，固定前缀 | 版本化；不由聊天自动覆盖 |
| L1 公共/阵营世界书 | 母港、阵营、公共规则和公开关系 | 命中才注入；小条目 | 由流水线生成，人工抽样审 |
| L2 近期会话 | 最近完整对话和尾部连续窗口 | 每轮，硬切预算 | 服务端保存原文；客户端只是缓存 |
| L3 角色长期记忆 | 与该角色的共同事件、承诺、偏好 | 关键词＋语义混合召回 | 每条带来源消息 ID/哈希和置信度 |
| L4 个人档案 | 用户自己的作息、偏好、隐私级别 | 仅在相关话题命中 | 与角色私聊隔离，按权限控制 |
| S 暂存成长 | 待确认的人设/世界书改动 | 不注入生产回复 | 生成 diff，Andrew 批准后合入，可回滚 |

单聊的私密记忆不广播给其他角色；群聊只产生可见的公共事件记录。召回失败时宁可不引用，也不让模型用“我记得”掩盖不确定性。

世界书第一版采用确定性的关键词/正则触发，条目有 `keys`、可选 `secondary_keys`、`content`、`insertion_order`、`budget` 和 `source`。规模变大后再加入向量候选，但必须保留关键词命中、来源和最终选择理由，形成混合召回而非黑盒 RAG。

建议默认限制：每轮最多 6 条动态条目、总长度 6000 字符；L0/L2 不受世界书预算挤出。每次召回都写 prompt trace，方便人工盲评解释“为什么这一条出现了”。

## 5. 主动消息生成

主动触达由规则调度器决定是否可以发送，模型只生成文本。请求应包含：触发类型、当前时间窗、最近发送摘要、冷却键、消息目的、可引用事实和免打扰状态；输出只需要一条可直接发送的短消息。

不同触发类型使用不同模板：

- 早安/晚安：带当日具体理由，不把固定问候每天原样重复。
- 想你/闲聊：只在冷却时间和每日上限通过后生成，允许“今天没有特别的事”。
- 提醒：事实、时间和行动要来自结构化任务，模型不能自行发明截止时间。
- JUUs 动态：动态内容和 @ 关系先由事件系统产生，模型只写角色口吻的转述。

发送前做三道检查：结构化事实校验、相似度/最近 N 条去重、用户免打扰与每日上限。失败则丢弃或进入下次窗口，不用“再生成一次”绕过限制。

## 6. 本轮实测与限制

### 6.1 已运行

| 项目 | 结果 | 解释 |
|---|---:|---|
| Python 单元测试 | 8/8 通过 | 覆盖卡片读取、世界书触发、记忆注入、50+1 轮、成本回退、盲评脱敏、URL 和模型清单 |
| 离线完整矩阵 | 540 次夹具调用 | 3 个本地路由别名 × 3 套方案 × 8 场景；验证编排、统计、盲材料产出，不代表模型质量 |
| Ollama 真实接口冒烟 | 18 次生成调用 | `qwen3.5:9b` × 3 套方案 × 6 场景；包括多条短消息的 3 轮，验证真实正文、延迟和 usage 记录；使用本地 Ollama 原生适配器，不冒充 9router |
| 9router `/v1/models` | 失败：`localhost:20128` actively refused | 服务未监听；没有进行外部调用，没有模型排名或 9router 费用结论 |

本机 Qwen 冒烟的内部统计（不作为跨模型结论）：

- `baseline`：6 个场景，平均每个场景约 25,336.43 ms，合计 9,207 tokens。
- `mobile_chat`：6 个场景，平均每个场景约 3,800.80 ms，合计 9,959 tokens。
- `memory_lore`：6 个场景，平均每个场景约 4,269.94 ms，合计 10,727 tokens。
- 费用为 `$0` 的本地推理；路由清单没有价格，因此评测器对该运行记录 `external_cost_usd=null`，不会伪造美元数。

首轮 `baseline` 仍可能包含本机模型冷启动和上下文长度差异，不能拿这 18 个调用比较方案性能；必须在同一 warmed-up 服务、相同输出上限和重复次数下重新测量。

### 6.2 盲评材料

真实 Qwen 冒烟的隐去标签材料在本机 gitignore 目录 `data/eval/ollama-qwen-final/blind.md`（机器可读版本为同目录 `blind.jsonl`），完整离线矩阵在 `data/eval/fixture-final/blind.md`。对应关系只在同目录的 `mapping.private.json`；这些路径和文件不进 Git。Andrew 需要评审时，应通过私有附件或本机目录获取，不把角色卡/回复放入公开仓库。

由于 9router 不可达，本轮盲评只能比较本机 Qwen 的三套 prompt 方案，不能替代要求中的 4–6 模型盲评。恢复路由后使用同一套脚本补跑，并将生成的盲材料作为 ADR 批准前的最后证据。

## 7. 推荐结论

**Solution Scout 主结论：BORROW + BUILD。**

- BORROW SillyTavern 的 Prompt Manager/World Info 的块化、触发、深度和 token 预算思想。
- BORROW dsh-nexttavern 的固定设定、尾部窗口、带来源导演笔记和按需混合召回。
- WRAP AstrBot 的人格、知识库和渠道能力，作为早期适配器。
- BUILD 啾信自己的小型单聊引擎、角色注册表、记忆权限/版本化、prompt trace 和主动消息调度。

理由是现有前端各自解决了“创作界面”或“本地聊天”，没有一个同时满足独立成员模型、服务端真源、私聊记忆隔离、可审阅成长、必达消息和 8→632 角色规模。整套引入会把 UI 状态、扩展运行时和数据模型带进核心；借协议和算法边界足够达到相同能力，同时保留 Android/PWA/微信适配自由。

## 8. 后续与停止点

1. 恢复 9router 本地/测试入口，先运行 `python pipeline/eval/chat_eval.py --live --confirm-spend --max-calls ...` 的小矩阵，再按预算补齐 4–6 个候选模型。
2. 对候选模型分别重复 `temperature=0.4/0.7/1.0`；保留模型 ID、价格清单、usage、延迟和失败原因。
3. Andrew 对脱敏并排回复打分；LLM 裁判只作参考，不能自动批准 ADR。
4. Andrew 批准 ADR-0004 后，才能把“提议”改为“已接受”，并与 ADR-0003 一起形成设计冻结。

本任务没有修改 NAS、AstrBot、9router 或任何第三方账号。

## 9. 来源

- [SillyTavern Prompt Manager](https://github.com/SillyTavern/SillyTavern-Docs/blob/main/Usage/Prompts/prompt-manager.md)
- [SillyTavern Prompt building](https://github.com/SillyTavern/SillyTavern-Docs/blob/main/Usage/Prompts/index.md)
- [SillyTavern World Info / Lorebook](https://github.com/SillyTavern/SillyTavern-Docs/blob/main/Usage/worldinfo.md)
- [Character Card V2 specification](https://github.com/malfoyslastname/character-card-spec-v2)
- [dsh-nexttavern memory design](https://github.com/a86582751/dsh-nexttavern)
- [AstrBot PersonaManager / AI guide](https://github.com/AstrBotDevs/AstrBot/blob/master/docs/zh/dev/star/guides/ai.md)
- [AstrBot knowledge base](https://docs-v4.astrbot.app/use/knowledge-base.html)
- [RisuAI README](https://github.com/kwaroran/RisuAI/blob/main/README.md)
- [RisuAI plugin API](https://github.com/kwaroran/RisuAI/blob/main/plugins.md)
- [TauriTavern README](https://github.com/Darkatse/TauriTavern/blob/main/README.md)
- [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)
- [Anthropic Claude model overview](https://platform.claude.com/docs/en/models/overview)
- [Google Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [DeepSeek model listing](https://api-docs.deepseek.com/api/list-models/)
