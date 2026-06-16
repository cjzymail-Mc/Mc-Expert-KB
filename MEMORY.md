# Mc-Expert KB — 索引

> 中央知识库（薄）。稳定层 = 人工策展快照，可修正、不污染源 repo。
> 易变 domain 细节不在此，留各源 repo（见 repo-map）。建于 2026-06-01（Stage 0）。

## 核心文档
- [principles.md](principles.md) — 用户决策偏好卡（确定性 Python > LLM / 稳定 > 新颖 / 文档诚实 / 入库判据 / 交互风格 / 环境约束）
- [reflexes.md](reflexes.md) — 跨 repo 硬反射（COM-only / Ldterm STOP / inspect-first / skills-first / UI-fix-first / 2-fail 熔断 / 不编辑产物 / Excel checkpoint / `-LiteralPath`），每条挂命中 repo
- [repo-map.md](repo-map.md) — 源 repo 地图 + 决策溯源子索引

## decisions/ — 跨 repo 已决决策（不重判，互链）
- [orchestrator-route](decisions/orchestrator-route.md) — 保留 Python orchestrator，瘦成 ~769 行薄 dispatcher，不归零；协作≠控制
- [per-agent-memory-no](decisions/per-agent-memory-no.md) — 不引入约定式 per-agent memory（CC 上下文隔离≠记忆隔离）
- [acceptance-guardrails](decisions/acceptance-guardrails.md) — 自动闭环三护栏（外部真相/重试硬上限/编排权留主 Claude）
- [ppt-html-route](decisions/ppt-html-route.md) — COM 两角色：HTML 只杀视觉创作，加密 I/O 底座永久保留
- [kb-memory-boundary](decisions/kb-memory-boundary.md) — KB 特殊：memory 两层分治（内容层只人工策展、auto-memory=待审 inbox、入库走判据闸门）+ CLAUDE.md 定位=薄操作手册非内容副本

## references/ — 事实手册
- [cc-permissions](references/cc-permissions.md) — Claude Code 权限系统实测事实（方案 A + 5 个反直觉事实）
- [agent-teams](references/agent-teams.md) — Agent Teams 机制核实（2026-06-01，易过期）：teammate 可引 project-scope agent（mc-expert 无需转 user 级）+ mailbox/task list 自动对话 + Windows 走 in-process + **solo vs 冷启动 team 判据 / 关键门派 mc-expert 陪审（2026-06）**
- [acceptance-ladder](references/acceptance-ladder.md) — 批量产线验收 = 五级首件递进阶梯（映射→内容→渲染→项目级→批量抽检；首件挑最难样本）〔Agent-4，2026-06-12〕
- [task-decomposition](references/task-decomposition.md) — 长链任务交底协议（信息三层 / 两段合同 plan 批准制 / 盘点先行+追问义务+拍板点封闭化 / 纠输入不纠输出）〔Agent-4，2026-06-10〕
- [loops-and-automation](references/loops-and-automation.md) — CC 自动化/Loops 架构（loop↔skill 正交 / 复用单位是 skill 非 agent / 五件套 / 台账=程序计数器 / 续命≠触发 / 原生优先 orchestrator 最后手段 / 写操作不无人值守）〔Mc-emoji 思考6，2026-06-12〕

## agents/ — KB 自带 subagent
- [planner](.claude/agents/planner.md) · [coder](.claude/agents/coder.md) — Stage 3 Agent Team spike 的两个 teammate（planner=opus 只读规划、coder=sonnet 实现）。同住被 junction 的 agents 文件夹 → 全局 user-scope 可用。见 `Mc-emoji/[feature-03]/sub-plan-stage3-agentteam-spike.md`。
- [mc-expert](.claude/agents/mc-expert.md) — 跨 repo 经验顾问/陪审（Stage 1 落地）。**物理母本**=repo 内 `.claude/agents/`（进 KB git、单一真相源）；**user-scope 发现**=3 账号 config 目录的 `agents/` 各 junction 指回此母本（yk `~/.claude` / mc `~/.claude-mc` / xh `~/.claude-xh`），2026-06-01 建立并实测 mc 账号从 repo 外 cwd 可发现。→ **任意账号、任意工作 repo 窗口都能 @mc-expert**（解锁 Stage 2 自动咨询）。`--add-dir` 仍只留给按需深挖源 repo。

## Stage 0 状态
- ✅ 去重 / principles / decisions×3（含互链）/ reflexes / repo-map / 溯源子索引
- ✅ 孤儿审计（6 大档）— 收割「少做」原则入 principles；候选 B（统一入口）已否决（仅 fangcaixia 成立，非普适，与 orchestrator-route 冲突）
- ✅ Mc-emoji 收割（2026-06-01）— C1「先查再下结论」入 reflexes；C2 权限事实入 references/cc-permissions；C3「协作≠控制」入 orchestrator-route
- ✅ **ROI 闸门 3/3 全通过**：orchestrator 切片 ✅ + Agent Teams（C3）✅ + PPT→HTML ✅（回放暴露两角色 nuance 缺口 → 补 decisions/ppt-html-route 封口）
- ⏳ GitHub private remote + 首 push（用户自行处理）

## 2026-06-15 收割轮（换机 + Agent-4 富矿）
- ✅ **环境翻转**：新机器 Ldterm DLP 已解除 → reflexes 加密节大改写（默认 Python / 遇密文跳过+记录+报告 / COM 降为窄场景 + 条件性回退）+ principles 环境硬约束同步；旧 COM-only/`88 7D 1C` STOP 降级为历史，不删。
- ✅ **A 订正**：repo-map 路径基址 `D:\Downloads\Mc Claude Code Workshop\`；Agent-4 升独立节（2026-06 批量产线富矿，原仅挂"其他"）。
- ✅ **B2**：`references/acceptance-ladder`（五级首件验收阶梯）。
- ✅ **C1/C2/C3**：机器自检≠人工验收（principles）/ 沉淀分两轨（kb-memory-boundary）/ solo-vs-team + mc-expert 陪审（agent-teams）。
- ⏸ 故意不入：派生层vs策展层（与 kb-memory-boundary 重复）、复用核口径（太薄）、域内细节（替代身份/.rels/染色，留源 repo）、Mc-emoji 基建（归其 skill）。
- ✅ **Agent-4 深扫补收**（扫生成产物层，非 auto-memory）：D1 `references/task-decomposition`（《通用任务拆解指南》蒸馏，头号发现）+ D2 加密节补「预解密+COM 回污染」第二理由 + D3 `python3` stub 反射。故意不入：逐品类 loop 化路线（域内+已被沉淀分两轨覆盖）、CLAUDE.md 三层结构（已被 claude-md-three-layer-refactor skill 覆盖）。
- ✅ **team 材料审核**：大部分=单次执行日志（留源 repo）或已被 agent-teams 覆盖；仅补「崩溃 team 残留 config→换 team-name」一行入 agent-teams。
- ✅ **Mc-emoji 深扫补收**（思考6/思考1）：F1 `references/loops-and-automation`（CC 自动化/Loops 架构，含 F3 复用单位=skill 非 agent 并入）+ F2 orchestrator-route 加分层说明（薄 dispatcher=管线内执行器 vs 外层编排循环，止矛盾）。故意不入：F4 Reviewer 别造轮子（时效性强+自明，负 ROI）、/process-rd 域内细节。

## 巡检台账（mc-update-KB 前置扫描基线）

> 用途：mc-update-KB「前置发现巡检」读此台账拿基线，只扫各源 repo **晚于"扫描截止"日期**的过程文件（忽略 office/pdf/ai 原材料）。事件驱动调起（大 feature 收尾 / 事故复盘 / 感觉攒够了），**非定时自跑**。每轮巡检后更新本表 + 上面"收割轮"叙事段。

| 源 repo | 扫描截止(基线) | 上次巡检 | 本轮结论摘要 |
|---|---|---|---|
| `3rd-ppt-prj` | 2026-06-02 | 2026-06-15 | Stage 0 已深挖（含孤儿审计）；过程文件≤05-29，无新增可入 |
| `[Agent-3] Info Classifier` | 2026-06-02 | 2026-06-15 | Stage 0 已深挖；过程文件≤06-02，无新增可入 |
| `[Agent-4] Wu Prj` | 2026-06-15 | 2026-06-15 | 富矿。已入：task-decomposition / acceptance-ladder / 加密节D2 / python3D3 / C1机器自检≠人工验收 / C2沉淀分两轨 / C3 solo-vs-team+陪审 / team残留config。已否：逐品类loop化路线、CLAUDE三层、派生层、复用核口径 |
| `Mc-emoji` | 2026-06-15 | 2026-06-15 | 已入：loops-and-automation(含F3复用单位=skill) / orchestrator-route分层说明 / mc-expert路径订正+索引起手。已否：F4 Reviewer别造轮子 |
| `xiaoduo-Excel task` 等 | — | 未扫 | 按需 |

## Stage 1 状态
- ✅ 两决策点已定（2026-06-01）：① agent 位置 = repo 内 `.claude/agents/`（核实机制后定，非全局）；② 访问机制 = KB-only + 按需深挖
- ✅ `mc-expert.md` 落地（system prompt 编入：稳定层自足读法 + repo-map 按需深挖 + KB 补洞自检 + 固定输出结构 + 顾问≠替身 + 承接已决决策）
- ⏳ §4 验收（在本 repo 内开新 CC session，跑 3 个真实咨询：1 有先例 / 1 历史冲突 / 1 无先例，查引档路径对不对、置信度诚不诚实、低置信度是否正确升级）→ §5 ROI 闸门
