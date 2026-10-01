# ADR-0003：啾信大脑形态（A 独立服务 vs C' AstrBot 插件）

> 创建日期：2026-09-26 ｜ 最后更新：2026-09-26 ｜ 版本：v0.1 ｜ 状态：提议

## 背景

M0 需要在实现生产级服务前验证两种大脑形态：A 是自己拥有会话、群聊导演、主动调度和投递账本的独立 Python 服务；C' 是通过 AstrBot 自定义平台适配器接入，再由插件承载群聊导演。两者都必须支持单聊、三人小群、导演选择、`[SKIP]`、轮数上限和一次定时主动消息。

本 ADR 只记录技术验证结论，不把状态改成“已接受”。Senior Reviewer 审查和 Andrew 批准仍是停止点。

## 试验边界

- 角色是 `Aster`、`Briar`、`Cato` 三个虚构角色；没有游戏原文、图片、音频或角色卡。
- 两个原型都通过同一个无依赖的 OpenAI-compatible `/v1/chat/completions` 客户端访问本地回环测试网关。
- A 原型由 `IndependentBrain` 持有会话、导演、定时器和投递账本。
- C' 原型由本地 AstrBot 形状运行时提供平台注册、入站事件、出站发送和宿主定时器；它不连接 NAS 上的 AstrBot。
- `ScriptedDirector` 只用于让试验可复现；它是未来模型导演/规则导演的替换点，不代表生产策略。

AstrBot 官方适配器文档显示，自定义适配器以 `register_platform_adapter` 注册，并负责将平台消息转换成 AstrBot 消息事件后提交给宿主；本原型只抽取这条边界，不复制上游实现：<https://docs-v3.astrbot.app/dev/plugin-platform-adapter.html>。

## 验收结果

运行：

```text
python -m unittest discover -s tests -v
Ran 3 tests in <1s
OK

python -m prototypes.run_demo --shape both
gateway_requests: 8
A: decisions=[aster, [SKIP], cato], messages=[aster, cato], skips=1, proactive=briar, ledger=[queued]
C': adapter_registered=True, decisions=[aster, [SKIP], cato], messages=[aster, cato], skips=1, proactive=briar, ledger=[queued]
```

两种形态都通过相同的行为验收：三轮上限生效，第二轮明确跳过，没有第四轮；主动消息在到期 tick 触发；模型请求进入同一个 OpenAI-compatible HTTP 网关。

## 比较

评分采用 0–5 分，权重为：必需能力 35%、试验证据 15%、集成成本 15%、成熟度 10%、维护健康 10%、扩展性 5%、许可/安全/运维适配 10%。分数用于暴露假设，不替代审查。

| 候选 | 必需能力 | 证据 | 集成成本 | 成熟度 | 维护 | 扩展性 | 许可/安全/运维 | 加权分 | 结论 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A 独立服务 | 5 | 4 | 3 | 2 | 4 | 5 | 5 | 83/100 | 推荐作为主形态 |
| C' AstrBot 插件 | 5 | 4 | 4 | 3 | 2 | 4 | 4 | 81/100 | 保留为可选桥接 |

### A 的观察

- 会话、成员身份、群轮次、`[SKIP]`、主动任务和投递账本都在同一个领域边界内，后续接消息真源、设备确认和多客户端同步时不需要把 AstrBot 会话模型反向改造成啾信成员模型。
- 代码量和部署组件会增加；需要自己补齐鉴权、持久化、推送、重试、管理面和运维。
- 失败边界更容易测试：模型网关、导演、调度器和投递账本可以分别替换，避免上游升级直接改变业务语义。

### C' 的观察

- 适配器注册、消息转换和宿主定时器复用现成能力，M0 起步快；这对保留微信单聊或做 AstrBot 侧通道有价值。
- 插件仍要自己保存跨角色成员路由、群轮次和投递账本；宿主的单会话/平台事件抽象不能直接提供啾信的成员真源。
- 上游 API、事件生命周期、会话隔离和版本升级会成为长期兼容成本；小群原型通过不等于数百角色和必达推送通过。

## 决策（提议）

**BUILD：以 A 独立服务作为啾信大脑主形态；BORROW：借鉴 AstrBot 的平台适配器边界，保留 C' 作为可选通道桥。**

理由是啾信的核心难点是数百角色的成员路由、服务端消息真源、设备投递账本和主动消息可靠性，而不是接入一个已有聊天平台。把这些状态放进独立服务能让数据模型直接对齐 PRD/架构草案；C' 的适配器仍可在后续作为 AstrBot/微信兼容层调用独立服务，不把线上 AstrBot 变成系统真源。

## 未覆盖与风险

- 本轮没有接真实模型、真实 AstrBot、Chronicle、FCM/ntfy 或 NAS；OpenAI-compatible 服务是回环测试网关，验证的是请求契约和编排路径，不是模型质量或生产延迟。
- `queued` 只证明原型产生了投递账本记录；M1 仍需实现持久化账本、客户端确认、幂等重试和断网补齐。
- ADR 仍为“提议”；未经 Senior Reviewer 审查与 Andrew 批准，不得改成“已接受”。

## 后续

1. Senior Reviewer 独立复核原型代码、运行日志和评分假设。
2. 若批准 A，M1 以 `docs/openapi-draft.yaml` 为接口草稿，先落地角色注册表、单聊、投递账本和设备确认。
3. 另开任务实现 AstrBot/微信桥接，只允许调用独立服务接口，不复制业务状态。
