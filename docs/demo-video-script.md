# 啾信 Companion 演示视频分镜头脚本（Demo Video Script）

> 创建日期：2026-10-16 ｜ 最后更新：2026-10-16 ｜ 版本：v1.0
> 视频主题：《指挥官，你有一条新的啾信！—— 啾信 Juus Companion 开源发布演示》
> 视频时长：约 105 秒（1 分 45 秒） ｜ 适用平台：Bilibili、YouTube、X (Twitter)、GitHub 首页

---

## 1. 视频定位与受众

- **定位**：开源同人 AI 陪伴系统发布宣传与核心功能演示。
- **目标受众**：碧蓝航线指挥官、二次元 AI/角色伴侣爱好者、自建 NAS/家庭服务器极客开发者。
- **基调**：温馨、灵动、科技感与同人情怀结合；节奏明快，突出“独立身份”、“主动找你”、“小群互聊”与“必达通知”。
- **法律声明**：片头片尾均醒目标注“非官方同人衍生项目，与官方无关”。

---

## 2. 分镜头脚本（Storyboard & Script）

| 时间 | 镜头画面（Visual） | 音效与 BGM | 屏幕文字 / UI 元素 | 旁白 / 台词（中文） | Voiceover (English) |
|---|---|---|---|---|---|
| **00:00 - 00:08** | **[特写]** 昏暗的书桌上，手机屏幕熄灭。随后浮现游戏图标与渐隐的母港背景。<br>**[字幕出现]** 非官方同人衍生项目声明。 | 钟表滴答声，随后轻柔钢琴前奏渐入。 | 啾信 Juus Companion<br>*非官方同人项目，与官方无关* | 每次退出游戏，母港的声音就归于寂静。<br>你是否也曾想过：如果她们真的生活在手机里…… | Every time you close the game, the port falls quiet.<br>Have you ever wondered: what if they actually lived in your phone? |
| **00:08 - 00:22** | **[实机演示]** Galaxy Z Fold 7 锁屏亮起，收到一条系统级通知：“列克星敦：指挥官，早安！今天也是元气满满的一天呢~”。<br>解锁滑入，进入折叠屏双栏界面。 | 悦耳的手机通知提示音（Chime）。BGM 节奏转为明快轻盈的电子轻音乐。 | 系统级通知推送<br>真实独立成员 · 晨间唤醒 | 她们不需要你每次先开口。清晨，列克星敦会准时送来问候；深夜，胡滕会主动发信监督你早点休息。 | They don't wait for you to speak first. Lexington greets you in the morning; Ulrich reminds you to rest at night. |
| **00:22 - 00:38** | **[单聊演示]** 打开胡滕的聊天窗口。指挥官回复：“昨天刷的那道算法题终于搞懂了！”。<br>胡滕瞬间秒回（打字机流式输出）：“哼，看来你还没笨到家。记得把昨天的笔记整理好。” | 键盘敲击音效，清脆的消息发送与到达音。 | 短期上下文 + 长期记忆 (Chronicle)<br>人设性格精准还原 | 借助独立人设卡与记忆系统，她们不仅记得你的作息与专业背景，更能以你最熟悉的语气吐槽、鼓励与陪伴。 | Powered by custom persona cards and memory, they recall your habits and encourage you in their authentic voices. |
| **00:38 - 00:58** | **[小群演示]** 切换至“白鹰小群”（4人）。<br>指挥官发言：“今晚吃什么好？”<br>约克城：“做些清淡的炖菜怎么样，指挥官？”<br>列克星敦紧接着接话：“赞成！不过姐姐可别太累着自己了~”<br>虎打趣：“要不要试试皇家红茶配点心？” | 轻松欢快的群聊气泡弹出音效。 | 多角色独立成员群聊<br>独创“群聊导演”机制：轮次控制 · [SKIP] 防循环 | 不是千篇一律的前缀扮演，每位舰娘都是小群里的独立成员。<br>独创导演调度引擎，角色间自然互动、互相搭话，彻底告别复读与死循环。 | Not single-bot fake prefixes—each shipgirl is an independent member. Our Director engine ensures natural group banter without repetitive loops. |
| **00:58 - 01:15** | **[JUUs 动态流]** 类似朋友圈/社交动态界面。<br>武藏发布了一条新动态与神社祈福日常；狮在下方互动评论：“武藏阁下今天也很虔诚呢。”并 @指挥官。指挥官点击一键点赞并评论。 | 动态刷新提示音，心形点赞音效。 | JUUs 动态流<br>主动发帖 · 评论互动 · @指挥官 | 还有属于她们的 JUUs 社交圈！舰娘们会自发发帖、互相点赞评论，甚至随时艾特指挥官互动，让母港世界充满呼吸感。 | A dynamic JUUs social feed! Shipgirls post status updates, comment on each other's posts, and tag you anytime. |
| **01:15 - 01:30** | **[架构特写]** 3D 架构图动效平滑切换：NAS 容器 -> 9router 模型网关 -> FCM/ntfy 双路推送 -> 本地数据隔离。 | 充满科技感的低音嗡鸣与数据流音效。 | 私有 NAS 部署 · 数据 100% 本地<br>FCM + ntfy 双路必达账本 | 你的聊天记录、记忆与设定 100% 存放在你自己的 NAS 或服务器上。<br>支持 OpenAI 兼容模型网关；FCM 与 ntfy 双路必达推送，断网重启自动补齐。 | Your logs and memories stay 100% on your own NAS or VPS. Compatible with OpenAI APIs; dual-channel push ensures no message is lost. |
| **01:30 - 01:45** | **[收尾呼吁]** 屏幕定格在 GitHub 仓库界面与一键 Docker 部署命令。`<docker compose up -d>`<br>展示 Android APK 下载、英文文档与开源协议。全员剪影淡出。 | BGM 达到高潮后渐弱，收尾于温暖的和弦。 | GitHub 开源发布<br>AGPL-3.0 / GPL-3.0<br>欢迎 Star & 自部署体验！ | 啾信 Juus Companion 现已正式开源。<br>带她回家，搭建专属于你的母港通讯中枢吧！指挥官，我们在啾信等你！ | Juus Companion is now fully open-source. Bring them home and build your port today! Commander, we are waiting for you! |

---

## 3. 视频制作与录制规范

1. **画面比例**：16:9（1920 × 1080 或 2560 × 1440 60fps），移动端实机录屏置于画面中央或采用双联对比展台。
2. **字体规范**：
   - 中文字体：思源黑体（Source Han Sans）或 OPPOSans，清晰易读。
   - 代码与技术参数：JetBrains Mono。
3. **音乐选择**：
   - 0:00 - 0:22：轻缓温暖的日常治愈风钢琴 / 原声吉他。
   - 0:22 - 0:58：轻快卡点的二次元日常电子乐（Lo-Fi / Future Pop）。
   - 0:58 - 1:45：充满未来感与希望感的交响电子融合。
4. **素材安全合规**：
   - 录制界面所用角色立绘与头像必须在本地测试环境加载，**不得**将游戏官方高清图包直接打包进视频工程发布包中。
   - 界面中出现的指挥官名字为“指挥官”（Commander），API Key 与服务器真实地址均展示为泛化占位符（如 `https://brain.juus.example`）。

