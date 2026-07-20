# loops-and-automation.md — CC 自动化 / Loops 架构（跨 repo）

> KB 事实手册 / 设计原则。源：Mc-emoji `[feature-03-take-a-nap]/Mc未来思考6：Boris-loops机制.md`（2026-06-12，多轮想透 Boris「写 Loops」方法论 + 落到本机 DLP 环境的边界）。
> 用途：任何「自动化 / loop / 跨会话自驱 / 编排」讨论起手先读，避免把节拍器当编排引擎、或把外部脚本当主干。

## 1. loop 与 skill 正交（核心，别混成一层）

| | loop | skill |
|---|---|---|
| 是什么 | 控制流（代码 / 命令内流程） | 知识（进 Claude 上下文的文字） |
| 管什么 | 何时问 / 问几次 / 何时停 | 被问到时凭什么答得对 |
| 性质 | **确定性**（写死的保证） | **概率性**（越丰富越准） |
| 会成长吗 | 不会，固定卡尺 | 会，越多案例越准 |

- **不建「自动决策」统一 skill**（junk-drawer 反模式）：决策永远跟领域走，入**所属领域 skill**；汇总成大杂烩会无领域锚点 + 规则打架 + 稀释当前任务真正需要的几条。
- **硬停止层是地板，永远保留**：skill 再准也是概率性、到不了 100%；让人工干预下降的是「skill 变准（软判断错得少）」+「loop 硬停（错了确定性兜住）」**两个独立机制**，后者不成长、也不该被前者替代。DLP+COM 环境抹掉硬停 = 把没兜底的错误自动执行 = 踩红线。

## 2. 复用单位是 skill，不是 agent（F3 并入）

能跨工作流复用的是**反射模式（skill）**，不是 agent 本身。agent = 带身份+决策权+绑产物形态/pipeline 脚本路径的角色 → **留项目级**；只有**不绑产物形态**的（PM 只产 brief / Researcher 只产 research_pack）能原样升用户级。实测共性矩阵：Archivist/developer/step1-3 仅 0–25% 通用，强行升用户级会在别的 repo 找不到 metadata.yaml/脚本路径而卡死。〔Mc-emoji 思考1，2026-05-26〕

## 3. loop 五件套（任何自动化先按这五条填一遍，缺哪条即隐患）

① 触发（间隔/事件）② 作用域边界 ③ 动作预算（限次数/时长/改文件数）④ 停止条件（何时停下升级给人）⑤ 报告路径。

## 4. 状态台账 = 程序计数器（无脑节拍器 → 跨天工作流引擎）

`/loop` 本身**无记忆**，每 tick 只把同一句话原样再喂一遍；它靠**每次重读状态文件**知道"上次干到哪"。给每个项目×步骤建状态格，loop 的"算下一个问题"退化为确定性扫描：**找第一个非 done 的格 = 下一步**，不靠 Claude "想"。→ 所以状态台账是 loop 的灵魂；补台账是 loop 化的**前置地基**。

## 5. 续命 ≠ 触发；"不盯梢/跨天自驱" 90% 不靠 loop

- **续命**（干到哪了、下次怎么接）= 状态文件，任何会话能续接（team-progress 归档 + 台账 + mapping JSON 已是这个）。
- **触发**（谁踩下一脚）= 三条轴：
  1. **手动**（人敲入口）
  2. **时间驱动** = `/loop`（cron 定时，每 tick 把同一句话再喂一遍）
  3. **事件驱动** = **`/goal` 型 Stop-hook 续轮**（每 turn 末由评估模型判定条件是否满足，未满足自动开下一 turn）。**⚠️ 易过期 + 单点实测**：机制可用 / 长跑稳定性待验，核实 2026-07-19 / CLI v2.1.207（claude-glm 单 provider 单探针，**别拔成"已验证可靠"**）。
- **`/goal` 关键区分**（与 `/loop` 别混）：
  - **本质** = session 级 **prompt-based Stop hook**（官方文档 + 本机"两 turn 强制接力"探针双坐实：模型原文自承"Stop hook 正在阻止此操作……hook 持续触发……完成第二段以解除阻塞"）。
  - **只管单 session 内续轮**；**跨 session**（断电 / 换天）续接仍靠**状态台账 + 手敲入口**，不是 `/goal`（区别于 Codex Goal 的 sqlite 跨 session 持久）。
  - **`/goal` 是续轮器不是验收器**：evaluator **只看对话已浮出的证据、不读台账文件、不跑测试**（官方文档原话）→ 业务 PASS 必须先由确定性自检 + 陪审把证据浮到对话，goal 条件只认台账三终态（COMPLETE/WAIT_HUMAN/HALTED）+ run budget。
  - **风险**：goal 条件未满足时会"**压过当 turn 指令**"强续（实测模型自承"虽用户让停，hook 持续触发"）→ today-loop 类场景必须给 goal 条件加"前置门通过 AND 无 awaiting_human"谓词，防跳过用户验收门。
- 真实需求拆开：「不想盯梢」「跨天推进」都靠**状态台账+固化 runbook**，不要 loop；loop 只多给「我不在场也转」一条——而这恰是写操作环境最不该要的。

## 6. 原生优先，外部 orchestrator 是最后手段

Boris 的「写 Loops」= 抽象层上移：**不写 orchestrator.py 调 Claude（低一级），而是把 runbook 写成自然语言 slash command，Claude 自己当驱动器**循环 + spawn subagent（每步新 subagent=新上下文，干完即丢，lead 主上下文不被撑爆）+ 原生 hook 做硬质量门 + 台账续命 + `/loop` 只管"再来一次"。**外部 orchestrator.py 仅在"跨 tick 累计计数（恰好 N 次硬停）"这一种确定性需求时才上**，否则是过度工程。
> 与 [[../decisions/orchestrator-route]] 分层：那条「保留薄 dispatcher」指 3rd-ppt 的**确定性 PPT 生产管线执行器**（管线内部）；本条指**外层任务编排循环**（哪个项目/哪步/派谁）。两者不矛盾，别混。

## 7. 环境打折（诚实边界，本机 ≠ Boris）

Boris 敢全自动无监督靠 CI + code-review 安全网 + 团队 PR 洪流。单人实验 repo + DLP+COM 底座：
- **含写操作的 loop 不无人值守**（包进脚本的 `Remove-Item` 静默执行、误碰密文 Office 二进制）；只读/幂等 loop（inspect 盘点 / 核验产物明文 magic / 扫 settings 完整性）才安全。
- **不为用 loop 开 bypassPermissions**（违方案 A；ask 门拦不住包进脚本的删除）。
- 成熟度门：只跑通 1 次的流程别 loop 化（判断逻辑还没稳到能写死=放大错误，呼应 [[../decisions/kb-memory-boundary]] 沉淀分两轨）。
- **Pro 订阅 OAuth 账号技术上跑不了无人值守定时**（硬约束轴，区别于上面"不该无人值守"的规范轴）：Task Scheduler/schtasks 派生 `claude -p` 用个人 Pro 订阅 token（`subscriptionType:pro`）→ `400 This organization has been disabled`；**同账号同模型交互式派生 ✅、定时派生 ❌**，唯一差别 = 被识别成自动化服务。真无人值守定时**必须用 API Key 账号**（`ANTHROPIC_API_KEY`，为自动化设计、不撞组织禁用）。**⚠️ 易过期**：属 Anthropic 账号策略，可能随政策变，用前复核。〔Mc-emoji feature-05 乙-2a，2026-07-03 实测；另 3 层 stdin 挂死 / MSYS 路径改写 / 代理不继承 = 环境调试细节留源 repo〕
- **⚠️ 判轴别用错**：「无人值守」是**规范轴/环境轴**（该不该无人值守、技术上跑不跑得了定时），**不是**「自主流程中途权限命令该不该后置」的判轴——后者见 [[../decisions/autopilot-defer-perm-to-human-gate]]，判据轴 = **是否处于 B 自主流程中途**（不是用户在不在场）。两轴常被混用（如实测 today-loop 评估时误用"无人值守→NOT_IN_SCOPE"，推翻了本可做的需求），**混了会错杀需求**——评估自动化场景时先问自己在用哪条轴。〔2026-07-19 claude-glm 核实 today-loop 议题翻车〕

**原档指针**：`Mc-emoji/[feature-03-take-a-nap]/Mc未来思考6：Boris-loops机制.md`（全文含 /process-rd 命令实现、claude -p headless 机制、5 件套逐条对照）；思考1（agent≠skill 共性矩阵）。相关：[[agent-teams]]、[[task-decomposition]]、[[../decisions/orchestrator-route]]。
