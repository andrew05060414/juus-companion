# 架构草案

> 创建日期：2026-09-27 ｜ 最后更新：2026-09-27 ｜ 版本：v0.1（草案，待 M0 技术验证后定稿）
> 依据：Multica PX-404 技术设计（Engineer @ Arknights）与后续决策。

## 1. 总体

```text
 Android App（fork blyy）        iPhone PWA（P1）
        │ HTTPS + 短期令牌              │ HTTPS + Web Push
        └──────────── Cloudflare Tunnel ┘
                         ▼
        ┌──────── 啾信大脑（NAS，Python）────────┐
        │ 角色注册表：角色卡 + 世界书（按需加载）   │
        │ 导演：单聊路由、小群轮次、[SKIP]、防循环  │
        │ 主动调度：频率/上限/免打扰/角色自建提醒   │
        │ JUUs 动态：发帖、评论、@指挥官（P1）      │
        │ 消息真源 + 投递账本 + 同步接口           │
        └──┬───────────┬─────────────┬───────────┘
           │           │             │
       模型网关      记忆适配       推送路由
     （9router，    （Chronicle、   FCM（主）
    OpenAI 兼容）    Mnemosyne，    ntfy/UnifiedPush（兜底）
                     可选模块）      Web Push（iPhone）

 微信：现有 AstrBot + ClawBot 胡滕单聊，独立运行；可选通过适配器共享角色卡与记忆
```

## 2. 关键原则

1. **大脑是唯一真源**：角色、会话、消息、设备、推送尝试和确认都在服务端；客户端只是缓存。
2. **推送只负责唤醒**：通知里只放消息编号和通用提示；正文由客户端拉取。服务端在收到客户端"已落库"确认前保留待投递记录，按设备/消息幂等重试。
3. **导演是群聊的唯一调度者**：不依赖"平台把 A 的消息投给 B"；每条消息带 `turn_id`/`origin`，每群限制轮数、并发和冷却。
4. **角色数据与代码分离**：代码仓库只放流水线和模板；角色卡、世界书、原声索引在部署者本地生成，存放在 gitignore 的数据目录或私有存储。
5. **密钥不进客户端**：模型网关、AstrBot、Chronicle 的凭据只在服务端。

## 3. 待定：大脑形态（M0 技术验证决定，见 ADR-0003）

| 方案 | 说明 | 优点 | 风险 |
|---|---|---|---|
| **A. 独立大脑服务** | 自研 Python 服务，AstrBot/Chronicle 通过 HTTP 调用 | 领域模型干净（成员、设备、账本），不受上游升级影响；开源后可独立部署 | 人设管理、定时任务、工具调用等需自己实现 |
| **C'. AstrBot 插件形态** | 自定义平台适配器（`register_platform_adapter`）+ 导演插件，复用 AstrBot 人设、定时任务、记忆、Chronicle 插件 | 复用多、起步快；开源后可直接进入 AstrBot 插件生态 | 数百角色的人设路由、投递账本放在哪、AstrBot 会话模型与"群成员"模型不一致 |

验证方法：用 3 个角色的小群，分别做最小原型，比较效果、代码量、数百角色时的可维护性，产出 ADR-0003。

## 4. 技术选型（暂定）

- 服务端与流水线：Python 3.12；Web 框架与存储在 M0 骨架任务中确定（倾向 FastAPI + SQLite/PostgreSQL）。
- Android：Kotlin + Jetpack Compose（继承 blyy），Room 本地缓存，FCM + UnifiedPush。
- PWA：TypeScript，IndexedDB，Web Push。
- 部署：NAS 上 Docker Compose；公网入口 Cloudflare Tunnel，管理面仅 Tailscale。

## 5. 数据流水线（人设）

```text
上游公开解包数据（AzurLaneTools/AzurLaneData、Fernando2603/AzurLaneData、Fernando2603/AzurLane）
   → 本地缓存（gitignore）
   → 按角色抽取：啾信私聊、JUUs 帖子与评论、语音台词、剧情片段、档案
   → LLM 生成 SillyTavern 角色卡 + 世界书（三层：母港通用 / 阵营 / 角色专属）
   → 自动质检（口癖、称呼、禁忌、与官设冲突）
   → 抽样人工审（首批 8 个全审）
   → 导出：啾信大脑格式 / AstrBot 人格格式
```
