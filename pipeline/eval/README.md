# 单聊评测器

`chat_eval.py` 读取运行者本地的 SillyTavern V2/V3 角色卡和可选 Lorebook，生成固定场景的模型回复，并把模型名与提示词方案从 `blind.jsonl` 中隐藏。真实角色卡、世界书和回复必须放在仓库的 gitignore `data/` 下。

## 先做 dry-run

```powershell
python pipeline/eval/chat_eval.py `
  --dry-run `
  --character-card data/private/hutten.json `
  --models cc-pro,cc-normal,cc-lite `
  --plans all `
  --scenarios all
```

包含 50 轮场景时，调用数会明显增加；命令会先打印预算。

## 9router 实测

价格必须从当前部署清单显式传入，不能从模型别名猜测。API key 只从环境变量读取：

```powershell
python pipeline/eval/chat_eval.py `
  --live --confirm-spend --max-calls 500 `
  --base-url $env:NINEROUTER_URL `
  --models cc-pro,cc-normal,cc-lite,model-four `
  --model-price cc-pro=5:25 `
  --character-card data/private/hutten.json `
  --lorebook data/private/hutten-lorebook.json `
  --out-dir data/eval/ninerouter-run
```

不要把 `--model-price` 示例中的数字当成当前价格；它只是命令格式示例。`run.json` 在价格未知时会把 `external_cost_usd` 记为 `null`，但仍记录 token 用量。

## 本机 Ollama 冒烟

Qwen 等思考模型在 Ollama 原生接口上可显式关闭思考，避免短 `num_predict` 只返回思考而没有正文。这条路径只用于本机 smoke，不替代 9router：

```powershell
python pipeline/eval/chat_eval.py `
  --live --confirm-spend --max-calls 24 --ollama-native `
  --base-url http://127.0.0.1:11434 `
  --extra-body-json '{"think":false}' `
  --models qwen3.5:9b `
  --plans all `
  --scenarios daily_chat,emotional_support,memory_recall,proactive_opening,ooc_injection,multi_short_messages `
  --character-card data/private/hutten.json `
  --out-dir data/eval/ollama-smoke
```

## 输出

- `blind.jsonl`：给人工盲评的回复，不含模型 ID 和方案名。
- `blind.md`：按场景分组的可直接阅读盲评材料，不含模型 ID 和方案名。
- `mapping.private.json`：本地映射，不能上传公开仓库。
- `results.private.jsonl`：每轮回复、usage、延迟和可计算成本。
- `judge.private.jsonl`：可选的 LLM 裁判原始结果，只作参考。
- `run.json`：运行参数、调用数和费用状态。

## 回归模式

更换 `chat-primary` / `chat-fallback` 模型，或合并修改 PromptAssembler、三套预设或 `mobile-chat` 约束的 PR 前，先用上一版建立基线，再用同一张卡、同一份世界书、同一套采样、方案和场景运行新版。每次比较只用一个旧模型和一个新模型；主路由和备用路由分别比较。

适用范围：角色卡或世界书内容一旦变化（包括卡模板改动后重新生成的卡），基线校验会拒绝对比，所以本模式不覆盖卡模板改动；那类改动请用上面的盲评流程人工比较新旧卡。

基线兼容：`run.json` 的 `regression_inputs`（场景、角色卡、世界书的摘要和采样参数）是基线能否复用的唯一依据。字段缺失或任何一项不同都直接报错，不做迁移或猜测；旧版评测器的产物、以及场景集更新之前建立的基线，都需要用当前评测器重跑。

用虚构卡从零跑通（与 CI 中 pytest 的离线测试相同，不调用模型）：

```sh
uv run python pipeline/eval/chat_eval.py --offline-fixture \
  --character-card pipeline/eval/fixtures/regression_card.json --models fixture-old \
  --plans mobile_chat --out-dir data/eval/persona-baseline &&
uv run python pipeline/eval/chat_eval.py --offline-fixture \
  --character-card pipeline/eval/fixtures/regression_card.json --models fixture-new \
  --plans mobile_chat --baseline data/eval/persona-baseline --out-dir data/eval/persona-current
```

预期输出 `regression_report=data/eval/persona-current/regression.md`。报告按场景和方案列出旧值、新值、变化和阈值；虚构夹具的 11 个默认场景应无红项。称呼场景读取 `data.extensions.appellation_user`；口癖场景可在本地卡的 `data.extensions.catchphrases` 写入词组数组。没配置的指标显示「不适用」，不隐式补词。年龄硬闸场景独立使用虚构的 16 岁外观角色，拒绝在网关前执行，既不发送给聊天模型，也不发送给裁判；这是评测器内的测试接缝，不是 #17/#18 的生产年龄硬闸。

可用 `--regression-config data/eval/thresholds.json` 部分覆盖阈值，例如 `{"bubble_length_distribution":0.35}`。值须在 0 到 1 之间，超过才标 🔴：

| 指标 | 默认阈值 | 标红条件 |
| --- | ---: | --- |
| `appellation_hit_rate` | 0% | 含正确称呼的回复比例下降 |
| `catchphrase_hit_rate` | 25% | 含口癖的回复比例上升或下降 |
| `catchphrase_repeat_rate` | 0% | 同轮口癖总命中超过一次的回复比例上升（互相包含的口癖变体按最长的算一次） |
| `bubble_count_distribution` | 25% | 每轮气泡条数分布的总变差距离超阈值（0、1、2、3、4、>4 条） |
| `bubble_length_distribution` | 25% | 每条原始气泡的长度分布总变差距离超阈值（≤10、11–20、21–40、>40 字符） |
| `boilerplate_hit_rate` | 0% | AI 腔或客服套话的词表命中比例上升 |
| `user_speech_rate` | 0% | 含用户代言标记的回复比例上升 |

气泡以完整标签为准，无完整标签时按非空行计量；统计原始输出，不先拆短或截断。词表和代言匹配只是线索，不理解语义。年龄硬闸只要有失败就标红，不可调。

本地实测沿用上面的 live 花费确认和调用数上限；可选 `--judge-model eval-judge`（或部署配置中该路由对应的模型 ID）。每个场景和方案的旧、新回复随机标成 A/B，裁判只能给出参考偏好；裁判会收到卡上配置的称呼和口癖；回复包在代码块里或带说明文字也能解析。判错、请求失败或超时只记为「无有效结果」并在 `judge.private.jsonl` 留下 `error`，不会中断运行或改变确定性标红；该文件同时记录每次裁判调用的 `usage` 和延迟，`run.json` 的费用只统计候选模型。红项和裁判意见都不自动决定通过或失败，最终由 Andrew 阅读报告后决定。真实卡、样本与所有运行产物只留本地 `data/`，PR 仅贴统计和脱敏样例。
