# ADR-0006：手机短消息气泡协议 v1 与纯函数边界

> 创建日期：2026-10-17 ｜ 最后更新：2026-10-17 ｜ 版本：v0.1 ｜ 状态：提议
> 对应任务：GitHub #29 / Multica PX-1208；依赖协调：#15（消息契约尚未定稿）、#18（单聊引擎）

## 问题与范围

现有模板要求括号动作和长段落，无法直接作为手机消息显示；模型发出的媒体编号也不能直接信任。本提议为服务端解析、生成模板和近期窗口回填提供同一套规则。它不冻结 OpenAPI、数据库或客户端格式，不改变 ADR-0004 状态。ADR 接受仍由 Andrew 批准。

## 格式与行为规则

以下文字与编号均为合成示例：

```text
<bubble>今天一起画云吗？</bubble>
<bubble>我带了画本。</bubble>
<bubble>[语音: fictional_voice]</bubble>
<bubble>[表情: fictional_sticker]</bubble>
```

| 情况 | 行为 |
| --- | --- |
| 有完整标签 | 用正则取完整气泡，按出现顺序处理；忽略标签外文字并返回 `outside_tags_ignored` 告警 |
| 无完整标签 | 删除已知的完整标签边界，按换行恢复；过长文本再按 `。！？!?～~…` 分句和长度拆分，返回 `fallback_split`；多行括号动作作为一个整体清理 |
| 括号动作 | 默认删除中英文括号及其内容，支持嵌套；未闭合左括号之后全部丢弃；孤立右括号删除。保守策略会同时移除普通括号说明，`strip_actions=False` 可关闭清理 |
| 过长单行 | 按可配置字符上限拆分，不直接截断单条；拆完仍受轮次气泡数限制。按 Python 字符计数，不是显示宽度或 token；SillyTavern `{{...}}` 宏不拆开，宏本身长于上限时允许超出 |
| 媒体 | 必须独占整条气泡；接受半角或全角冒号。候选表按本轮、媒体种类、大小写精确匹配；缺失编号或空字幕/描述视为无效 |
| 非候选编号 | 丢弃整个源气泡，返回 `invalid_media_id`，不修复、不转成普通文字；混排或不完整媒体标记返回 `malformed_media_bubble` 并整条丢弃。校验先于动作清理和长度拆分，避免未知编号被拆成文字 |
| 超过条数 | 清理及拆分后保留前 N 条有效气泡，N 默认 4、可调低至 1，返回 `bubble_limit` |
| 全空、全动作、全部媒体被拒绝 | 返回空元组、`empty_reply` 和 `needs_retry=True`；不编造兜底回复、不请求模型、不写存储 |

`BubblePolicy` 的起始值为 `max_chars=40`、`max_bubbles=4`、`max_tokens=300`、`typing_ms_per_char=35`。长度、预算和延迟均未做体验实测，可由部署配置构造策略对象传入。预算和延迟在本模块只作为配置提示，不自动修改网关请求或安排客户端计时。`brief` 动作风格与角色例外表不在本轮范围。

允许改变：拆分长段、清理动作、拒绝无效媒体、裁掉超额有效气泡。必须保留：合法气泡顺序、合法候选 ID 与对应的服务端文字、用户示例和角色示例的边界、SillyTavern 宏。重复执行相同输入和策略应得到相同结果，不改变调用方状态。

## 调用与契约协调

`server/src/juus_server/bubbles.py` 仅依赖标准库，公开 `parse_bubbles`、`render_bubbles`、`history_backfill`、`bind_message_fields` 和不可变结果类型。流水线在仓库根目录运行，通过 `server.src.juus_server.bubbles` 复用同一实现；这不是部署依赖或服务调用。服务端源根路径下可用 `juus_server.bubbles` 导入。未来拆包时应统一安装公共协议模块；当前不引入打包或框架改造。

```python
from juus_server.bubbles import bind_message_fields, history_backfill, parse_bubbles

result = parse_bubbles(
    output,
    voice_candidates={"fictional_voice": "虚构问候字幕"},
    sticker_candidates={"fictional_sticker": "虚构纸风车描述"},
)
# Host must persist result.warnings to prompt_trace before retry/delivery.
# Warning codes and source indexes contain no reply text, asset URLs or IDs.
if not result.needs_retry:
    rows = bind_message_fields(
        result.bubbles,
        turn_id=turn_id_from_engine,
        bubble_index=0,
        types={"text": "text", "voice": "voice", "sticker": "sticker"},
    )
    recent_assistant_text = history_backfill(result.bubbles)
```

`bind_message_fields` 只是边界适配示意，不代表 #15 已接受的字段形状。`turn_id`、起始 `bubble_index`、外部 `type` 的映射全部由调用者显式传入；模块不生成轮次身份，不承诺幂等落库或重新生成替换。聊天引擎应负责以 `turn_id` 管理整轮替换、重试预算、trace 持久化及最终 API 映射。

解析只接受完成后的字符串，不实现流式事件或损坏字节解码。部分标签与完整标签同时出现时，只保留完整标签，避免不完整内容绕过校验。传错配置会抛出 `ValueError`；模型格式错误通过结果表达。

## 模板与历史

- 新生成的 `first_mes`、`alternate_greetings` 和 `mes_example` 中角色轮次，使用相同策略自动转换。`<START>` 与 `{{user}}` 示例保留；原有声音示例不再被误包为括号动作。模板转换无需模型调用。
- 系统提示和 post-history 改为短消息正向目标，明确只输出标签、每轮条数、长度、一次最多一个问题和候选媒体限制。post-history 是指令，不能把指令本身当作角色气泡包裹。
- AstrBot 复用同一系统提示，因此新生成的 `begin_dialogs` 仅转换 assistant 项，user 项与列表交替结构保留。没有导入或部署到线上。
- `history_backfill` 消费已校验的 `Bubble`，将语音转为 `<bubble>[语音: 服务端字幕]</bubble>`，表情转为对应描述，文本保留；保持轮内顺序，不依赖客户端播放结果，不保存媒体 URL。不自动修改近期窗口，也不应将回填文本再次交给媒体 ID 解析器。

## 验证与停止点

`uv run pytest` 覆盖标准输入、无标签、过长、全动作、空白、媒体拒绝、超额裁剪、恢复、回填及模板边界。`uv run pytest server/tests/test_bubbles.py -k 200 -s -q` 打印 200 条合成输出的非空率、容错数量、动作残留率和未知编号丢弃数；非空率分母包括刻意空白/不安全样本，安全返回空不计成功。测试均为脚本造句和虚构编号，不调用任何真实模型。

本轮不做真实模型验证、体验/UAT、消息落库、客户端、群聊、中途打断、线上服务、真实数据重生成或迁移。后续接 #15/#18、客户端与真实聊天前，还需独立审查、契约协调与 Andrew 的设计/体验验收；本 PR 的代码自测不等于这些关卡已通过。
