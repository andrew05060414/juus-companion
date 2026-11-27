# 3 位主力角色本地单聊原型

> 创建日期：2026-11-27 ｜ 最后更新：2026-11-27 ｜ 版本：v0.1

## 定位

本原型用于验证 Andrew 在 2026-11-26 明确的方向：不再沿 SillyTavern 酒馆风味角色卡和批量 881 张卡管线推进，先用贝尔法斯特、企业、胡滕 3 位主力角色验证“去酒馆腔、活人感、微信短句节奏”的单聊手感。

它只是本地闭环原型，不部署 NAS，不写线上服务，不导入游戏原文或生成角色卡。3 位角色的人设提示和示例均为仓库内手写的合成写作约束，不是游戏台词或角色卡导出物。

## 启动

Windows 仓库根目录：

```powershell
.\start-native-chat.ps1
```

等价命令：

```powershell
uv run python -m prototypes.native_chat.run --host 127.0.0.1 --port 8765 --open
```

打开后访问终端打印的本地地址，默认是 `http://127.0.0.1:8765/`。页面包含：

- 3 位主力角色切换；
- 手机消息气泡流与连续多句发送；
- 发送后已读、时间戳与分气泡显示；
- Gemini 4 Carbon / Sonnet 两个逻辑模型 lane；
- “对比”按钮，用同一条输入分别调用两个后端 lane；
- 只读日常上下文槽位开关。

## 真实模型后端配置

原型只依赖 OpenAI 兼容 `chat.completions`，仓库不硬编码地址或密钥。在本地 `.env` 配置：

```dotenv
JUUS_MODEL_BASE_URL=http://your-local-gateway.example.invalid/v1
JUUS_MODEL_API_KEY=replace-with-a-local-secret
JUUS_GEMINI_MODEL=gemini-4-carbon
JUUS_SONNET_MODEL=sonnet
```

如果本机已经配置 9router，原型也会读取现有环境变量 `NINEROUTER_URL`、`NINEROUTER_KEY` 和 `NINEROUTER_SONNET_MODEL` 作为共享后端 fallback；`JUUS_*` 配置优先。

也可以给两个 lane 分别配置网关与密钥：

```dotenv
JUUS_GEMINI_BASE_URL=http://gateway-a.example.invalid/v1
JUUS_GEMINI_API_KEY=replace-with-a-local-secret
JUUS_SONNET_BASE_URL=http://gateway-b.example.invalid/v1
JUUS_SONNET_API_KEY=replace-with-a-local-secret
```

未配置真实后端时，启动脚本会用明确标注为“演示兜底”的确定性本地回复，便于检查界面和气泡流；这不作为模型手感验收。需要强制缺少配置就失败时运行：

```powershell
uv run python -m prototypes.native_chat.run --no-demo-fallback
```

## 输出约束

提示词和后处理共同约束输出：

- 1 到 4 个 `<bubble>`；
- 每条尽量是 36 个汉字以内的短消息；
- 禁止星号动作旁白、括号动作、舞台指示、第三人称叙述；
- 禁止大段自我介绍、世界观背书和无边界长独白；
- 每次最多一个自然问题；
- 后处理会移除星号动作、模板宏和显式旁白行，再由现有 bubble parser 切分。

## 批量角色卡管线冻结

`pipeline` 的注册表、导出器和既有测试底座保留，但批量 SillyTavern 角色卡运行入口默认冻结：

- `pipeline/run.py` / `pipeline/run.py run`（包括默认试点名单和 `--batch`）返回退出码 2；
- `pipeline/run.py reconcile --re-export` 返回退出码 2；
- 只有明确复审旧管线时才可临时设置 `JUUS_ALLOW_LEGACY_TAVERN_BATCH=1`。

这防止后续无意继续跑 881 张卡的酒馆风味批量管线，同时不删除仍有参考价值的消息、注册表和导出底座。

## 定向验证

```powershell
uv run pytest tests/test_native_chat.py -q
uv run ruff check prototypes/native_chat tests/test_native_chat.py pipeline/cli.py
```
