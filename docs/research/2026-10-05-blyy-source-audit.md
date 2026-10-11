> 创建日期：2026-10-05 ｜ 最后更新：2026-10-05 ｜ 版本：v1.0
>
> 审计对象：oneroomlife/blyy（只读 clone）
>
> 审计快照：879b9cba9c4cff44914ec69e64d2f01a3b66874e（2026-10-04，仓库 main）
>
> 证据约定：［事实］是当前源码直接读到的行为；［推断］是基于事实和 Juus 现有设计得出的建议；［未确认］是当前源码或本地文档没有足够证据的事项。下文的 blyy/...:行号 均指本票工作目录中临时 clone 的源码，不会复制进 Juus 仓库。

## 结论先行

1. ［事实］ blyy 已经是可用的本地 Android 聊天客户端：API Key、Base URL、模型、人设、会话和消息都落在手机本地 DataStore；模型请求由手机直接发出，当前没有 Juus 服务端参与。证据：blyy/app/src/main/java/com/azurlane/blyy/data/local/PlayerSettingsDataStore.kt:489-556、blyy/app/src/main/java/com/azurlane/blyy/data/repository/JiuxinApiRepository.kt:167-205。
2. ［事实］ 单聊提示词只有一段可编辑的 systemPrompt、该角色的长期记忆摘要和最近 20 条消息；没有源码级的 V2/V3 角色卡、Lorebook、开场白或提示词 trace 装配器。证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2953-3011、blyy/app/src/main/java/com/azurlane/blyy/data/model/JiuxinModels.kt:349-375。
3. ［事实］ 长期记忆是私聊本地增量摘要：累计 40 条消息、保留最近 12 条、至少新增 20 条才触发，摘要最长 1200 字；群聊直接跳过。证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:127-136、2048-2050、3041-3145。
4. ［事实］ 群聊导演不是独立模块，而是 JiuxinViewModel 中的随机调度：首轮并发选成员，后续以 85% 概率逐轮互回，最多 min(成员数, 3) 轮，模型可输出 [SKIP]；状态随会话和消息保存在手机本地。证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2188-2401、2576-2698、blyy/app/src/main/java/com/azurlane/blyy/data/model/JiuxinModels.kt:232-278。
5. ［事实］ 设置已经支持独立保存 API 配置、舰娘人格和完整预设，并能在新建聊天时组合 API 配置与人格；但“完整预设一键开始新聊天”没有成为当前新建聊天页的主路径。证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:1080-1387、blyy/app/src/main/java/com/azurlane/blyy/ui/screens/ConversationListScreen.kt:356-380、917-1050。
6. ［事实］ 当前“语音”是舰娘语音输出和播放，不是用户语音输入；聊天输入栏只有加号、单行文本框和发送按钮，也没有录音/语音识别权限或识别器。证据：blyy/app/src/main/java/com/azurlane/blyy/ui/screens/chat/ChatInputBar.kt:163-325、blyy/app/src/main/AndroidManifest.xml:1-26、blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2707-2796。
7. ［事实］ 当前源码没有外部角色卡导入器；用户可以手填或粘贴一段人格提示词，但没有读到 SillyTavern V2/V3、Lorebook 或角色卡文件解析流程。证据：blyy/app/src/main/java/com/azurlane/blyy/data/model/JiuxinModels.kt:349-375、blyy/app/src/main/java/com/azurlane/blyy/ui/screens/config/ConfigSections.kt:704-765；这是对当前快照的“未发现”结论。
8. ［未确认］ API 地址能否直接指向 OpenCodex：blyy 没有 OpenCodex 专用适配或引用。仅从通用实现推断，若 OpenCodex 提供 OpenAI 兼容的 POST /chat/completions、Bearer 鉴权和可接受的模型名，则有机会工作；具体地址、鉴权头、模型列表接口和兼容程度必须实测确认。证据：blyy/app/src/main/java/com/azurlane/blyy/data/repository/JiuxinApiRepository.kt:108-123、167-185、279-310、330-385。
9. ［推断］ blyy 的 Compose 页面、会话/群成员快照、OpenAI-compatible 请求边界和 [SKIP]/轮数上限思路可以借到 Juus Android 端；消息真源、群导演、记忆权限、主动消息、必达推送和角色卡流水线不能继续放在客户端。
10. ［推断］ Juus 下一步应以 ADR-0003 的 A 独立服务为真源，让 fork 后的 Android 只做 UI、缓存和投递确认；这与当前 ARCHITECTURE.md 的“服务端唯一真源、密钥不进客户端”一致。证据：juus-companion/docs/ARCHITECTURE.md:31-35、41-48；juus-companion/docs/decisions/ADR-0003-brain-shape.md:61-74。

## 1. 审计范围与源码地图

本次只读了两个仓库：

- blyy：按票据执行 git clone https://github.com/oneroomlife/blyy，固定在上面的 commit；没有修改、构建或复制其游戏素材。
- juus-companion：只读取 AGENTS.md、PRD、ARCHITECTURE、DATA_POLICY、ROADMAP 与 ADR-0001～0004，用来做架构对照；只会在本 PR 中新增本报告。

与本报告最相关的 blyy 入口如下：

| 领域 | 入口 | 读到的职责 |
|---|---|---|
| 数据模型 | blyy/app/src/main/java/com/azurlane/blyy/data/model/JiuxinModels.kt:21-72、168-375、389-430 | 消息、私聊/群聊会话、群成员、预设、API 配置、人格配置、长期记忆和 UI 状态 |
| 本地存储 | blyy/app/src/main/java/com/azurlane/blyy/data/local/PlayerSettingsDataStore.kt:489-701 | DataStore 中的 API、人设、会话、消息、预设、记忆 |
| 单聊/群聊编排 | blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:1951-2401、2953-3145 | 发送、上下文、群导演、语音/表情、记忆摘要 |
| HTTP API | blyy/app/src/main/java/com/azurlane/blyy/data/repository/JiuxinApiRepository.kt:103-310 | OpenAI-compatible 请求、重试、响应解析、URL 拼接 |
| 全局设置 UI | blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinConfigScreen.kt:125-334、blyy/app/src/main/java/com/azurlane/blyy/ui/screens/config/ConfigSections.kt:120-998 | API、人设、预设、记忆、语音和表情 |
| 当前会话设置 UI | blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinShipConfigScreen.kt:86-552 | 当前会话的人格、API、模型、语音和表情 |
| 会话/群聊入口 | blyy/app/src/main/java/com/azurlane/blyy/ui/screens/ConversationListScreen.kt:108-430、1356-1553 | 新建单聊、组合 API+人格、新建群聊和会话列表 |
| 聊天 UI | blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinChatScreen.kt:178-522、blyy/app/src/main/java/com/azurlane/blyy/ui/screens/chat/ChatInputBar.kt:163-325 | 消息列表、打字指示、文本输入、发送、语音播放 |

## 2. 单聊：提示词、记忆与 API

### 2.1 配置与会话快照

［事实］ blyy 的人格不是结构化角色卡，而是 PersonaConfig 中的一组平面字段：名称、啾信显示名、头像、systemPrompt、语音舰娘和语音/表情参数；没有 description、first_mes、alternate_greetings、examples 或 Lorebook 字段。会话 ChatSession 会复制 API URL、API Key、模型、systemPrompt 和语音/表情设置，保证切换会话时配置不串。证据：blyy/app/src/main/java/com/azurlane/blyy/data/model/JiuxinModels.kt:232-278、343-375。

［事实］ 发送前若没有会话，ViewModel 自动创建一个空消息会话；创建会话时消息列表写入空数组，随后用户消息才加入。因此没有“创建角色后自动发开场白”的源码路径。证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:821-832、1270-1387、2139-2151。

### 2.2 每轮提示词怎么拼

单聊每次调用的实际顺序是：

1. 从当前 ChatSession 读取 API Key、Base URL、模型和 systemPrompt；缺省时回退全局 DataStore。
2. 把该角色的长期记忆文本追加到 systemPrompt 后面，并用一段固定说明要求模型自然使用记忆。
3. 从消息列表取最近 20 条，只把 USER 映射成 user、AI 映射成 assistant；语音、表情包和 SYSTEM 消息不进入单聊模型上下文。
4. 组成一条 system 消息加历史消息数组，交给 ChatCompletionRequest；最新用户消息已经在调用前加入列表，不会再重复追加。

证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2953-3005；消息类型定义见 blyy/app/src/main/java/com/azurlane/blyy/data/model/JiuxinModels.kt:21-29、59-72。

［事实］ 这不是 ADR-0004 所要求的可追踪 PromptAssembler：没有 L0/L1/L2/L3/L4 的结构化 source_id、hash、priority、token 估算或 prompt_trace；外部角色卡也没有单独的注入层。对照目标见 juus-companion/docs/decisions/ADR-0004-chat-engine.md:39-70。

### 2.3 记忆摘要如何沉淀

［事实］ 摘要逻辑是本地、按角色身份 key 保存的增量任务：

- 仅私聊触发，群聊直接 return。
- 消息总数少于 40 条不触发；摘要时保留最近 12 条；距上次摘要新增不足 20 条不触发。
- 对待摘要区间生成最多 6000 字符的 transcript；用固定的“记忆整理助手” system prompt 调同一个模型。
- 新摘要最长 1200 字，写入 PersonaMemory；同时用 summarizedCount 和 summarizedLastTs 推进进度，避免消息窗口裁剪后重复/漏摘要。
- 之后每次单聊把这段摘要直接附加进 systemPrompt；用户也可在配置页手工编辑或清空。

证据：阈值与长度见 blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:126-136；触发点见 :2048-2050；摘要与进度见 :3014-3145；UI 手工入口见 blyy/app/src/main/java/com/azurlane/blyy/ui/screens/config/ConfigSections.kt:793-858。

［推断］ 对 Juus 来说，这套“按角色隔离、异步摘要、时间戳锚点”的思路可以作为客户端原型参考；摘要正文、消息来源和成长修改不能直接作为服务端生产记忆，因为 ADR-0004 要求来源锚点、审阅 diff 和可回滚版本。对照 juus-companion/docs/decisions/ADR-0004-chat-engine.md:64-70。

### 2.4 API 调用位置、行为和硬编码

［事实］ JiuxinViewModel 只负责从会话/全局设置构造 ChatCompletionRequest，JiuxinApiRepository 负责 HTTP。请求固定带 Authorization: Bearer、Content-Type、Accept，body 包含 model、messages、max_tokens 和 temperature；默认值是 max_tokens=1024、temperature=0.7。证据：blyy/app/src/main/java/com/azurlane/blyy/data/repository/JiuxinApiRepository.kt:103-123、167-185、279-300。

［事实］ Base URL 会在没有 /chat/completions 时直接追加该路径；模型列表另试 /v1/models、/models 等候选端点。证据：blyy/app/src/main/java/com/azurlane/blyy/data/repository/JiuxinApiRepository.kt:302-310、315-328、439-485。

［事实］ 非 2xx、解析失败和部分网络异常会分类；超时/连接/空响应最多重试 2 次并指数退避 500ms→1000ms，4xx 和解析错误不重试。证据：blyy/app/src/main/java/com/azurlane/blyy/data/repository/JiuxinApiRepository.kt:143-206、267-277。

［事实］ 当前实现没有把 stream=true 放入请求，也没有 SSE/增量回调；响应通过一次性 response.body?.string() 读取。解析器虽兼容单个 delta.content 字段，但这不等于实现了流式传输。证据：blyy/app/src/main/java/com/azurlane/blyy/data/repository/JiuxinApiRepository.kt:209-238、279-300、654-755。

值得迁移到 Juus 的硬编码清单：

| 常量/规则 | 当前值 | 位置 | 对 Juus 的影响 |
|---|---:|---|---|
| 默认模型 | gpt-4o-mini | blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:102-105 | 应由服务端逻辑路由配置，不写死在客户端 |
| 单聊 prompt 历史 | 最近 20 条 | blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2979-2996 | 应由服务端上下文预算决定 |
| 本地消息上限 | 200 条 | blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:102-106、2894-2900 | 不能替代服务端历史真源 |
| HTTP 输出 | 1024 tokens、temperature 0.7 | blyy/app/src/main/java/com/azurlane/blyy/data/repository/JiuxinApiRepository.kt:108-115、292-297 | 应按路由/角色预设配置 |
| 记忆触发 | 40 / 12 / 20 / 1200 字符 | blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:126-136 | 只能作为实验默认值 |
| 默认语音关键词 | 你好;早安;晚安;加油;辛苦了 | blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:123-124 | 应进入角色能力配置而不是全局常量 |

## 3. 群聊与“导演”

### 3.1 状态模型

［事实］ GROUP 会话把 groupMembers 作为配置快照保存，每个 GroupMember 包含 personaId、显示名、头像、systemPrompt、语音和表情参数；ChatMessage 用 shipName/avatarUrl 标识发言成员，groupId 用于跨历史会话聚合。证据：blyy/app/src/main/java/com/azurlane/blyy/data/model/JiuxinModels.kt:168-205、232-278。

［事实］ 创建群聊时从已保存 PersonaConfig 复制成员快照，并要求至少 2 个成员；群聊使用全局 API 配置的快照。证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:934-1010。

［事实］ 会话和消息仍然只存手机：会话列表序列化到一个 DataStore key，消息按 ai_session_msgs_<sessionId> 另一个 key 保存，没有 Room 消息表、服务端 ID、同步游标或设备确认。证据：blyy/app/src/main/java/com/azurlane/blyy/data/local/PlayerSettingsDataStore.kt:523-556；消息写入调用见 blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2894-2951。

### 3.2 谁说话、怎么互回

［事实］ 每次用户消息的首轮成员选择规则是：成员数不超过 2 时全员回复，3～4 人取 3 人，5 人以上也取 3 人；这些请求并行发出，谁先返回谁先显示。证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2188-2228。

［事实］ 每个成员的 API 请求都重新构造自己的 system prompt：加入该成员人格、群名、其他成员名单、标签解释和短回复约束；自己历史用 assistant，其他成员历史用带 ASCII name 的 user 消息，消息正文另加中文身份标签。证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2576-2685。

［事实］ 首轮至少一人成功后，进入互回 while 循环：每轮 85% 概率继续，最多 min(成员数, 3) 轮；每轮选择一个成员，输出 [SKIP]、空串或以 [SKIP] 开头时不落消息，否则写入该成员的 AI 消息。用户清空、删除或切换会话时，代际计数器使后续回复丢弃。证据：常量见 blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:107-121；循环与 [SKIP] 见 :2300-2401。

［事实］ 这不是“导演模型/服务”：选择成员和轮次都由客户端的随机数、列表和 ViewModel 局部状态决定；没有 turn_id、origin、跨设备并发锁或冷却键。Juus 架构要求这些状态归独立大脑统一调度。对照当前 blyy 代码 blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2200-2332、juus-companion/docs/ARCHITECTURE.md:31-35。

［事实］ 群聊没有长期记忆摘要：maybeUpdateMemory 在群聊会话上直接跳过。证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:3041-3045。

## 4. 设置、一键化与预设

### 4.1 当前实际配置流程

当前可按下面流程使用：

1. 从设置导航到 jiuxin_config；导航入口在 blyy/app/src/main/java/com/azurlane/blyy/ui/AppRoot.kt:683-750。
2. 在 API 分区填写 Base URL、API Key、Model，可拉取模型并测试连接；输入 Base URL 时 UI 会显示自动补全后的 /chat/completions。证据：blyy/app/src/main/java/com/azurlane/blyy/ui/screens/config/ConfigSections.kt:460-645。
3. 在舰娘人格分区填写头像、啾信名称和人格提示词，另行设置语音舰娘、随机概率、关键词和表情包；保存为 PersonaConfig。证据：blyy/app/src/main/java/com/azurlane/blyy/ui/screens/config/ConfigSections.kt:704-998。
4. 可将当前 API+人格+语音+表情保存为 JiuxinPreset，也可分别保存 ApiConfig 与 PersonaConfig；预设应用会覆盖全局设置。证据：保存/应用 UI 见 blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinConfigScreen.kt:343-639，ViewModel 见 blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:1080-1267。
5. 从会话列表点加号进入新建聊天，最多各选一个 API 配置和人格配置，再创建带配置快照的新会话；群聊则输入群名并多选至少 2 个 PersonaConfig。证据：blyy/app/src/main/java/com/azurlane/blyy/ui/screens/ConversationListScreen.kt:356-405、917-1050、1356-1553。
6. 进入已有会话后，jiuxin_ship_config 可只改当前会话，不影响全局；API 选择和模型测试位于当前会话配置页。证据：blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinShipConfigScreen.kt:86-142、232-430。

### 4.2 已有一键能力与明显缺口

［事实］ 已有能力：保存/应用完整预设；保存/应用独立 API 配置；保存/应用独立人格；新建会话时组合 API+人格；一键清空人格字段；长期记忆手工编辑/清空。证据：blyy/app/src/main/java/com/azurlane/blyy/ui/screens/config/ConfigSections.kt:134-152、746-858；blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:1080-1387。

［事实］ 当前新建聊天页展示的是“API 配置”和“舰娘人格”两个独立选择区，并调用 startChatWithApiAndPersona；完整 JiuxinPreset 的应用入口在配置页，源码没有在该新建聊天页调用 startChatWithPreset。证据：blyy/app/src/main/java/com/azurlane/blyy/ui/screens/ConversationListScreen.kt:917-1050、blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinConfigScreen.kt:229-250、blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:1287-1296。

［推断］ 最适合做成一键预设的是“角色卡导入 → 服务端角色版本 → API 路由 → 新建会话”四步合一；Android 端只保留选择已发布角色和逻辑模型路由，不再让用户逐字段粘贴提示词或把 Key 复制进会话快照。

## 5. Voice 与 UI 改动入口

### 5.1 已有的是语音输出

［事实］ 用户消息发送前，ViewModel 从当前会话读取 voiceShipName、voiceShipAvatar、开关、概率和关键词；命中标签或随机概率后加载 VoiceLine，并把音频 URL、台词和发送者写成 VOICE 消息。聊天页通过 message.voiceUrl 调用 MediaPlayer 播放。证据：触发见 blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2001-2027、2707-2758；播放见 :2760-2796；消息渲染入口见 blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinChatScreen.kt:413-431。

### 5.2 语音输入接入点

［事实］ ChatInputBar 的公开输入契约是 inputText、onInputChange、onSend、enabled、onPlusClick，没有录音回调；底部布局只有加号、BasicTextField 和发送按钮。证据：blyy/app/src/main/java/com/azurlane/blyy/ui/screens/chat/ChatInputBar.kt:163-172、224-323。

［事实］ JiuxinChatScreen 只把 ChatInputBar 的 onSend 连接到 viewModel.sendMessage(chatState.inputText)，没有语音识别结果回调。证据：blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinChatScreen.kt:497-522。

［事实］ AndroidManifest 只有网络、通知、媒体播放、悬浮窗和文件/相机相关权限，没有 RECORD_AUDIO；app 依赖也没有读到 SpeechRecognizer/第三方 STT 依赖。证据：blyy/app/src/main/AndroidManifest.xml:1-26、blyy/app/build.gradle.kts:109-149。

［推断］ 最小接入方式是：在 ChatInputBar 增加麦克风按钮与 onVoiceInput 回调；在 JiuxinChatScreen 负责 Android SpeechRecognizer 生命周期/权限，把识别文本写回 setInputText；若改由服务端 STT，则在 JiuxinViewModel 与独立 repository 增加上传/转写接口。不要把语音输入和现有“舰娘语音输出”混为一个配置项。

主要 UI 修改入口：

| 要改的体验 | 首要文件 | 当前证据 |
|---|---|---|
| 页面路由、设置入口 | blyy/app/src/main/java/com/azurlane/blyy/ui/AppRoot.kt:683-750 | jiuxin_config、jiuxin_ship_config、jiuxin_chat、jiuxin_conversation_list |
| 全局 API/人设/预设 | blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinConfigScreen.kt:125-334；blyy/app/src/main/java/com/azurlane/blyy/ui/screens/config/ConfigSections.kt:120-998 | 分区状态和字段装配 |
| 当前会话配置 | blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinShipConfigScreen.kt:86-552 | 只影响当前会话 |
| 新建单聊/群聊 | blyy/app/src/main/java/com/azurlane/blyy/ui/screens/ConversationListScreen.kt:356-405、917-1050、1356-1553 | API+人格选择与群成员多选 |
| 聊天消息与输入栏 | blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinChatScreen.kt:389-522；blyy/app/src/main/java/com/azurlane/blyy/ui/screens/chat/ChatInputBar.kt:163-325 | 消息列表、打字态、输入/发送 |

## 6. 外部角色卡与 OpenCodex

### 6.1 外部角色卡能否导入

［事实］ 当前 PersonaConfig 只支持平面字段，设置 UI 也只提供头像选择、名称和人格提示词输入框；源码没有文件选择器、PNG/JSON 卡片解析、V2/V3 schema、Lorebook entries 或导入/导出 API。证据：blyy/app/src/main/java/com/azurlane/blyy/data/model/JiuxinModels.kt:343-375、blyy/app/src/main/java/com/azurlane/blyy/ui/screens/config/ConfigSections.kt:746-765。

［结论］ 不能从当前源码确认“可导入外部角色卡”；按已读实现，应视为“当前未支持”。手工把卡片内容复制到 systemPrompt 只能算人工迁移，不是角色卡导入。Juus 的角色卡格式决策是 SillyTavern V2/V3 + Lorebook，见 juus-companion/docs/PRD.md:27-36 和 juus-companion/docs/decisions/ADR-0004-chat-engine.md:74-95。

### 6.2 API 地址能否指向 OpenCodex

［事实］ blyy 接受用户输入的 HTTP(S) Base URL，聊天时补 /chat/completions，用 Bearer token 发 OpenAI 风格 JSON；拉模型时尝试多个 /models 端点，并额外发送 x-api-key。证据：blyy/app/src/main/java/com/azurlane/blyy/data/repository/JiuxinApiRepository.kt:167-185、302-310、330-385、439-485。

［未确认］ 当前 clone 没有 OpenCodex 字样、专用路径、专用鉴权或响应适配。不能仅凭“可填任意 URL”宣称 OpenCodex 一定兼容。

［推断］ 若 OpenCodex 对外提供与上述请求完全兼容的聊天端点，并接受该模型名/鉴权头，理论上可以把 Base URL 指向它；至少要实测：普通 POST、模型列表、非流式 JSON 响应、错误响应和长上下文。若它只提供 Responses API、不同鉴权或只支持 SSE，当前 blyy 不能直接确认可用。

## 7. 后端缺口：与 Juus 架构和 ADR 的对照

Juus 当前设计明确要求：服务端是角色、会话、消息、设备和投递状态的唯一真源，客户端只缓存；密钥只在服务端；群导演统一维护轮次、并发和冷却。证据：juus-companion/docs/ARCHITECTURE.md:31-35。ADR-0003 建议 A 独立服务作为主形态，ADR-0004 要求服务端单聊引擎、角色/记忆真源、权限隔离、prompt trace 和主动消息调度。证据：juus-companion/docs/decisions/ADR-0003-brain-shape.md:61-74、juus-companion/docs/decisions/ADR-0004-chat-engine.md:8-24。

| 后端能力 | blyy 当前事实 | Juus 需要补的服务端部分 | 可复用/冲突 |
|---|---|---|---|
| 角色注册表与 881 张角色卡导入 | 客户端只有 PersonaConfig 的 systemPrompt 平面字段，没有 V2/V3/Lorebook 导入。证据：blyy/app/src/main/java/com/azurlane/blyy/data/model/JiuxinModels.kt:343-375。 | 角色版本、V2/V3 + Lorebook parser、来源 manifest、变体合并、质检、发布/回滚；本票要求的 881 位数量还需与 PRD 中约 632 位的现有记录对账。 | 可复用“人格显示/头像/语音配置”的 UI 形状；格式和真源冲突，不能让手机成为角色卡仓库。 |
| 消息真源与多设备同步 | 会话/消息是 DataStore JSON，按 sessionId 本地保存。证据：blyy/app/src/main/java/com/azurlane/blyy/data/local/PlayerSettingsDataStore.kt:523-556。 | 账号、设备、会话、消息 ID、游标同步、幂等写入、离线补齐、删除/编辑/重生成语义。 | 可借 ChatMessage/ChatSession 的 UI 映射；存储和权限必须迁到服务端。 |
| 模型网关与密钥 | 手机直接持有 API Key，并把它复制进 ChatSession/JiuxinPreset/ApiConfig。证据：blyy/app/src/main/java/com/azurlane/blyy/data/model/JiuxinModels.kt:232-340、blyy/app/src/main/java/com/azurlane/blyy/data/local/PlayerSettingsDataStore.kt:99-130、508-520。 | 服务端逻辑路由、短期令牌、供应商密钥、重试/超时/usage 账本；客户端只拿短期访问凭据。 | 可复用 OpenAI-compatible 的消息抽象；直接 HTTP 和客户端存 Key 与 ARCHITECTURE/ADR-0004 冲突。 |
| 单聊提示词与记忆 | 当前是 systemPrompt + 20 条历史 + 本地摘要；没有 trace，摘要直接回写角色记忆。证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2953-3011、3041-3145。 | PromptAssembler、L0-L4 权限、Lorebook 检索、记忆来源锚点、memory_diff 审阅/回滚、Chronicle/Mnemosyne adapter。 | 可借最近窗口和异步摘要的实验参数；装配协议和生产写入规则冲突。 |
| 群聊导演 | 客户端随机选人、并发请求、概率互回、[SKIP]、最多 3 轮。证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2200-2401。 | 服务端 turn_id/origin、导演决策、轮数/并发/冷却、跨设备一致性、失败重试和可观测日志。 | [SKIP] 和物理轮数上限可复用为行为契约；随机局部状态不能作为生产真源。 |
| 主动消息与必达推送 | 源码没有 FCM、WorkManager、ntfy 或主动消息调度；现有通知主要是媒体播放/悬浮窗服务。证据：blyy/app/src/main/AndroidManifest.xml:4-11、65-96；blyy/app/build.gradle.kts:109-149。 | 触发规则、免打扰、每日上限、FCM+ntfy 路由、消息账本、客户端确认、幂等重试、打开 App 游标补齐。 | 现有 Android 通知权限可继续用；推送和调度不能由客户端临时定时器替代。 |
| 语音 | 客户端本地按关键词/概率拉语音 URL并播放。证据：blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2001-2027、2707-2796。 | 角色卡语音索引、私有素材目录、服务端消息事件中可选 voice attachment；后续再接语音输入/STT。 | 输出消息模型可借；真实游戏素材与语音索引必须遵守 Juus DATA_POLICY，不能进仓库。 |

## 8. 优化建议（按收益大、先做小范围可落地项排序）

每条都写“收益”和“改哪里”；这里是后续实现建议，不表示本票已经实现。

1. **做角色卡导入适配器。** 收益：把一次 V2/V3 + Lorebook 导入变成可审阅的角色版本，消除逐字段粘贴 systemPrompt；改动位置：服务端 pipeline/角色注册表，以及客户端当前平面模型/入口 blyy/app/src/main/java/com/azurlane/blyy/data/model/JiuxinModels.kt:343-375、blyy/app/src/main/java/com/azurlane/blyy/ui/screens/config/ConfigSections.kt:746-765。
2. **先把模型调用搬到独立大脑服务。** 收益：API Key 不再进手机和会话快照，并能统一路由、重试、usage 与审计；改动位置：替代 blyy/app/src/main/java/com/azurlane/blyy/data/repository/JiuxinApiRepository.kt:167-205 的直连，同时对齐 juus-companion/docs/ARCHITECTURE.md:31-35。
3. **引入消息真源、游标同步和投递账本。** 收益：多设备回看、断网补齐、去重和必达推送有可验证状态；改动位置：把 blyy/app/src/main/java/com/azurlane/blyy/data/local/PlayerSettingsDataStore.kt:523-556 和 blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2894-2951 的本地写入换成服务端 API + 本地缓存。
4. **补真正的流式 Chat Completions。** 收益：满足 Juus P0 的流式回复，用户不用等完整 body 才看到第一段；改动位置：blyy/app/src/main/java/com/azurlane/blyy/data/repository/JiuxinApiRepository.kt:209-238、279-300，以及 blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinChatScreen.kt:447-495 的增量状态渲染。
5. **把单聊/群聊 prompt 装配收口到 PromptAssembler。** 收益：角色卡、Lorebook、历史、记忆和 token 预算可追踪且能解释“为什么这样回复”；改动位置：替换 blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2953-3005、2576-2685，输出 ADR-0004 要求的 prompt_trace。
6. **把群导演状态搬到服务端并保留 [SKIP]/轮数契约。** 收益：多个设备或渠道看到同一轮次，避免客户端随机状态分叉和无限互聊；改动位置：把 blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:2188-2401 的选择、轮次、冷却和失败策略改成服务端 turn 状态，客户端只渲染。
7. **把“完整预设”接到新建聊天的一键路径。** 收益：用户选一个角色就能同时带上 API、人格、语音和表情，少做一次组合选择；改动位置：blyy/app/src/main/java/com/azurlane/blyy/ui/screens/ConversationListScreen.kt:917-1050、blyy/app/src/main/java/com/azurlane/blyy/viewmodel/JiuxinViewModel.kt:1287-1387。
8. **在聊天输入栏增加语音输入。** 收益：手机上可以说话转文字后直接发送，补齐当前只有舰娘语音输出的缺口；改动位置：blyy/app/src/main/java/com/azurlane/blyy/ui/screens/chat/ChatInputBar.kt:163-325、blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinChatScreen.kt:497-522、blyy/app/src/main/AndroidManifest.xml:4-26。
9. **短期保留本地模式时，至少把 API Key 放进 Keystore-backed storage。** 收益：降低 DataStore 明文偏好文件和会话快照泄露的影响；改动位置：blyy/app/src/main/java/com/azurlane/blyy/data/local/PlayerSettingsDataStore.kt:99-130、489-520、blyy/app/src/main/res/xml/backup_rules.xml:2-11。长期仍应按 Juus 架构移除客户端 Key。
10. **合并全局配置页与当前会话配置页的重复模型/API 选择组件。** 收益：减少两套模型列表、测试状态和字段同步逻辑不一致；改动位置：blyy/app/src/main/java/com/azurlane/blyy/ui/screens/config/ConfigSections.kt:460-698 与 blyy/app/src/main/java/com/azurlane/blyy/ui/screens/JiuxinShipConfigScreen.kt:232-430。

## 9. 本票验收结论与未确认项

### 已确认

- 单聊如何拼 prompt、如何取历史、如何做记忆摘要、API 在哪里调用：已在第 2 节给出源码行号。
- 群聊成员选择、并行首轮、互回概率、[SKIP]、轮数上限和本地状态：已在第 3 节给出源码行号。
- API Key、Base URL、模型、人设、预设和一键组合的当前流程：已在第 4 节给出源码行号。
- 语音输出与用户语音输入缺口、主要 UI 入口：已在第 5 节给出源码行号。
- 后端需要补的角色注册表、消息真源、设备同步、导演、主动消息、必达推送、记忆和密钥边界：已在第 7 节对照 ARCHITECTURE/ADR-0003/ADR-0004。

### 未确认/需要后续实测

1. OpenCodex 的真实 Base URL、鉴权要求、模型名、/models 行为、非流式响应和 SSE/Responses API 兼容性；源码没有专用适配。
2. 本票“881 位角色卡”与 juus-companion/docs/PRD.md:31 现有“约 632 个”范围数字不一致，导入总量需要在角色清单/规划票中统一。
3. blyy README.md:172-176 说“配置 API Key 和模型参数、创建人格、自动沉淀长期记忆”，但源码审计没有读到外部角色卡导入；README 的“人格”应理解为手工 systemPrompt 配置，不能据此推断支持 V2/V3。
4. 本报告未接真实模型、OpenCodex、FCM、ntfy、Chronicle、AstrBot 或 NAS；没有把任何未实测项写成可用承诺。

## 10. 交付边界

- 本票只新增本文件；不修改 blyy clone，不 fork，不构建 APK，不安装设备，不接真实 API，不碰 juus-data、游戏素材、角色卡、语音、密钥或个人数据。
- 当前结论支持短线“blyy 直接试聊”与长线“A 独立服务”并行：Android UI 可以复用，生产消息/角色/记忆/推送真源必须由 Juus 大脑承担。
- 这是一份只读源码审计，不是 ADR 接受、设计冻结、真实微信试聊或 NAS 部署批准。
