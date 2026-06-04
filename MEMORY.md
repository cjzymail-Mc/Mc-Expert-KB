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
- [agent-teams](references/agent-teams.md) — Agent Teams 机制核实（2026-06-01，易过期）：teammate 可引 project-scope agent（mc-expert 无需转 user 级）+ mailbox/task list 自动对话 + Windows 走 in-process

## agents/ — KB 自带 subagent
- [planner](.claude/agents/planner.md) · [coder](.claude/agents/coder.md) — Stage 3 Agent Team spike 的两个 teammate（planner=opus 只读规划、coder=sonnet 实现）。同住被 junction 的 agents 文件夹 → 全局 user-scope 可用。见 `Mc-emoji/[feature-03]/sub-plan-stage3-agentteam-spike.md`。
- [mc-expert](.claude/agents/mc-expert.md) — 跨 repo 经验顾问/陪审（Stage 1 落地）。**物理母本**=repo 内 `.claude/agents/`（进 KB git、单一真相源）；**user-scope 发现**=3 账号 config 目录的 `agents/` 各 junction 指回此母本（yk `~/.claude` / mc `~/.claude-mc` / xh `~/.claude-xh`），2026-06-01 建立并实测 mc 账号从 repo 外 cwd 可发现。→ **任意账号、任意工作 repo 窗口都能 @mc-expert**（解锁 Stage 2 自动咨询）。`--add-dir` 仍只留给按需深挖源 repo。

## Stage 0 状态
- ✅ 去重 / principles / decisions×3（含互链）/ reflexes / repo-map / 溯源子索引
- ✅ 孤儿审计（6 大档）— 收割「少做」原则入 principles；候选 B（统一入口）已否决（仅 fangcaixia 成立，非普适，与 orchestrator-route 冲突）
- ✅ Mc-emoji 收割（2026-06-01）— C1「先查再下结论」入 reflexes；C2 权限事实入 references/cc-permissions；C3「协作≠控制」入 orchestrator-route
- ✅ **ROI 闸门 3/3 全通过**：orchestrator 切片 ✅ + Agent Teams（C3）✅ + PPT→HTML ✅（回放暴露两角色 nuance 缺口 → 补 decisions/ppt-html-route 封口）
- ⏳ GitHub private remote + 首 push（用户自行处理）

## Stage 1 状态
- ✅ 两决策点已定（2026-06-01）：① agent 位置 = repo 内 `.claude/agents/`（核实机制后定，非全局）；② 访问机制 = KB-only + 按需深挖
- ✅ `mc-expert.md` 落地（system prompt 编入：稳定层自足读法 + repo-map 按需深挖 + KB 补洞自检 + 固定输出结构 + 顾问≠替身 + 承接已决决策）
- ⏳ §4 验收（在本 repo 内开新 CC session，跑 3 个真实咨询：1 有先例 / 1 历史冲突 / 1 无先例，查引档路径对不对、置信度诚不诚实、低置信度是否正确升级）→ §5 ROI 闸门
