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
