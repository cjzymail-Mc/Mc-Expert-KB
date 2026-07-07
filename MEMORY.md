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
- [kb-memory-boundary](decisions/kb-memory-boundary.md) — KB 特殊：memory 两层分治（内容层只人工策展、auto-memory=待审 inbox、入库走判据闸门）+ CLAUDE.md 定位=薄操作手册非内容副本。⚠️含消歧指针：**源 repo 的 memory↔auto-memory 分流尺 ≠ 本卡**，那把尺在 mc-update 第 2 步
- [autopilot-defer-perm-to-human-gate](decisions/autopilot-defer-perm-to-human-gate.md) — B 自主流程中途 rm/权限/敏感目录/对外命令一律后置人工门（halt=不执行+落盘+上报，**非阻塞式权限框**）；判据轴=「B 自主流程中途」非「无人值守」；源 2026-06-20 8h 死锁事故。已同步 `/free`·`/today`·team-task SKILL·agent-teams
- [self-compliance-probabilistic](decisions/self-compliance-probabilistic.md) — AI 规则 self-compliance=概率裁判，别为"提高激活率"建度量/监控；可靠性归冗余层两档（确定硬兜底 hook/人工门/熔断 + 概率软冗余 team/陪审，别混）；软自律扳机保留但不度量、不朝其爬山
- [scaffold-placement-via-claudemd](decisions/scaffold-placement-via-claudemd.md) — 过程文件「落点规约」必须烧进每个 repo 的 CLAUDE.md（每冷会话唯一自动加载层；skill 按需救不了/auto-memory 错位/hooks 过度工程）；bootstrap 默认模板只固化「计划/产物/复盘三大类去向」普适内核，不抄 production 域内结构（防候选 B 翻版）。落地于 mc-scaffold-audit skill

## references/ — 事实手册
- [cc-permissions](references/cc-permissions.md) — Claude Code 权限系统实测事实（方案 A + 6 反直觉事实 + **07-03 官方补强**：deny→ask→allow 官方确认/Windows 无沙箱→方案A唯一正解/受保护路径V1/模式辨别/CVE 黑名单必被绕）
- [agent-teams](references/agent-teams.md) — Agent Teams 机制核实（2026-06-01，易过期）：teammate 可引 project-scope agent（mc-expert 无需转 user 级）+ mailbox/task list 自动对话 + Windows 走 in-process + **solo vs 冷启动 team 判据 / 关键门派 mc-expert 陪审（2026-06）** + **idle-零正文：故障模型+兜底单一权威节（2026-06-18 实证）——显式 SendMessage 必要不充分（in-process 投递 flaky + 疑似 session 截断）、有产物角色落盘承重；旧 Q8「显式即解决/不需落盘」已订正为指针**
- [acceptance-ladder](references/acceptance-ladder.md) — 批量产线验收 = 五级首件递进阶梯（映射→内容→渲染→项目级→批量抽检；首件挑最难样本）〔Agent-4，2026-06-12〕
- [task-decomposition](references/task-decomposition.md) — 长链任务交底协议（信息三层 / 两段合同 plan 批准制 / 盘点先行+追问义务+拍板点封闭化 / 纠输入不纠输出）〔Agent-4，2026-06-10〕
- [loops-and-automation](references/loops-and-automation.md) — CC 自动化/Loops 架构（loop↔skill 正交 / 复用单位是 skill 非 agent / 五件套 / 台账=程序计数器 / 续命≠触发 / 原生优先 orchestrator 最后手段 / 写操作不无人值守）〔Mc-emoji 思考6，2026-06-12〕
- [cc-hooks-facts](references/cc-hooks-facts.md) — CC hook 机制事实（StopFailure=observ-only 交互式续不了/真续走 headless `--fallback-model` / UserPromptSubmit exit-2=全局变砖 landmine→launcher 防砖 / stdout 恒空 / settings 不热重载但脚本即时 / **07-03 补权限决策类 hook 拦截语义**：deny 拦 bypass·只收紧不放松·fail-open→exit2·覆写守卫范式）〔核 2026-07-02/07-03, CLI v2.1.193/159, 易过期〕

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

## 2026-06-18 收口轮（idle-零正文 实证 · 事件驱动非全量巡检）
- ✅ **agent-teams idle-零正文单一权威收口**：新增「故障模型 + 兜底策略」节（模式①投递 flaky=实测 / 模式②session 截断=疑似推断+判据 / 已排除 tmux + 漏发工具两套错诊断）；Q8 瘦成指针、Mailbox 注改指权威节、旧"不需落盘"口径订正。源 = Wu Prj `mc-debug07`（已加头部回链）。
- ✅ **mc-update-KB 补洞**（§3 step 8）：references 实证推翻处理范式（就地订正+下沉权威节）+ 单一权威收口"散点扫除 checklist"（rg 全揪逐处降指针）。mc-expert 陪审提出。
- ⏸ 故意不入：team-task 体系重构（B 模式深度授权→SKILL.md 权威 / team-task.md 瘦身 / team-task-api 归档 `skills-archived/`）= 操作落地，已活在 skill + team-task.md 自身，KB 无需再记。

## 2026-06-25 收割轮（B 模式权限后置 · 硬事故即时收割）
- ✅ **新 decision `autopilot-defer-perm-to-human-gate`**：B 自主流程中途权限命令一律后置人工门（halt=不执行+落盘+上报、非阻塞框）。源 = Wu Prj `feedback_autopilot_defer_perm_command_to_human_gate`（2026-06-20 8h 死锁事故，**孤儿滞留 5 天**才收割）。
- ✅ **跨入口同步**：`/free`（user-scope command，junction 全账号）+ `/today` 第 0 步（以其母版口径对齐）+ `team-task/SKILL.md` 红线#3 & 收尾 bullet + Mc-emoji CLAUDE.md 指针。mc-expert 陪审 GO-with-changes（4 项收紧已纳：行号订正 / 散点补 2 处 / 判据轴「B 自主流程中途」非「无人值守」/ 入库写「严重度豁免」非「频次≥3」）。
- ✅ **散点收口**（mc-update-KB 第 8 步）：`references/agent-teams.md`「高风险上报」降指针 + `references/cc-permissions.md` 第 6 条反向互链（交互式 vs B 自主流程分工）。
- ✅ **mc-update-KB 触发器补洞**：前置步加「③ 硬事故即时收割」——安全阀/事故类经验当场走①模式即时收割、别攒批（本决定孤儿滞留 5 天即此漏洞）。
- 完整施工 plan：`Mc-emoji/plan-B模式权限命令后置人工门-同步修订.md`。

## 2026-06-26 巡检轮（Wu Prj + Mc-emoji 双 repo 扫描）

- ✅ **principles 入库判据补「普适 vs 项目专属测试」**：收割前问「换个不同性质项目还成立吗？依赖某 repo 特殊前提=项目专属、留原地」+「与已入库决策方向冲突的候选格外警惕（多是两者各有适用条件）」+否决留痕。源 = Wu Prj→Mc-emoji `feedback_kb_universal_vs_project_specific`；实例 fangcaixia 候选 B 已在 repo-map 孤儿审计，本轮把*通用判据*沉淀。append 不另起条目。
- ⏸ **C1 延后（用户在开发中）**：StopFailure hook / API 错误恢复事实（observ-only、交互式 hook 不能自动续、headless 走 `--fallback-model`）。机制事实已稳定但周边方案未定型，用户要求开发完再纳入 → 已挂进巡检台账「待入候选」，下轮 `/KB-update` 收。源 = Mc-emoji `cc-stopfailure-hook-observ-only.md` + `API-Error-自动恢复-方案.md`（核于 2026-06-26, CLI v2.1.193）。
- ⏸ 故意暂不入（borderline 未挑）：C3 廉价可测先实测（与 reflexes「先查再下结论」部分重叠）、C4 B 模式循环内选型走 mc-expert（部分被 keygate_mc_expert_jury 覆盖，新点「两份驱动规范冲突开工先声明」）、C5「指针委托真相源不回灌公共管线层」脱节（抽象偏早、实例属 deck 域）。
- ❌ 不入：`feedback_destructive_delete_confirm`（已在 cc-permissions §6）/ `feedback_skill_vs_loop_orthogonal`（已在 loops-and-automation）/ `思考7 深度授权`（=autopilot 决策卡同一事故）/ `prefer-autonomy-fast-iteration`（已 operationalize）/ `feedback_reviewer_scope` / `feedback_agent_handoff_gate`（task-decomposition 覆盖）/ deck·工艺单域内细节。

## 2026-07-02 巡检轮（Mc-emoji feature-05 富矿 + 待入候选收割）

- ✅ **收尾在途 decision `self-compliance-probabilistic`**（上轮已写卡+加索引、未提交）：本轮补收割叙事 + 台账。AI 规则 self-compliance=概率裁判，别为"提高激活率"建度量/监控；可靠性归冗余层两档（确定硬兜底 vs 概率软冗余，别混）。源 = feature-05 续19。
- ✅ **新 reference `cc-hooks-facts`**：台账里那条明确「待入·用户开发中」的候选（StopFailure/API 错误恢复）现已开发完（hook 上线实战）→ 连同 UserPromptSubmit exit-2 变砖 landmine 合成一份 CC hook 机制事实。标核实日期/CLI 版本/易过期；实现细节留源 repo。
- ✅ **reflexes 扩「先查再下结论」**：泛化到一切事实性断言 + 绑 4 个可见动作扳机（含"理论上应该/我记得"信号词即停）；新增**「阴性结论需阳性对照」**反射。源 = feature-05 `feedback_verify_before_asserting` + `feedback_negative_needs_positive_control`（dogfood 实证）。
- ✅ **principles 推广「先备份 .bak」**：从 config 文件推广到任何会覆写持久产物的操作（miner/pipeline 重跑）+ 执行体标注的风险警示要采纳。源 = `feedback_backup_before_regenerate`。
- ✅ **task-decomposition append「机械词触发先对齐」**：prompt 出现 扫描/读取/分析/盘点 → 先对齐再动手（盘点先行的机械化前哨）。源 = `feedback_scan_verb_align_first`。
- ✅ **.gitignore 边界订正**（用户拍板）：`.claude/commands/` + `.claude/hooks/` = user-scope junction 母本，与 skills/agents 同等级 → 随 repo 版本化上 GitHub，不忽略。落地 4 个新文件（pin.md / stopfailure-autocontinue.ps1 / capture_launcher.py / BACKLOG-待修.md）。
- ⏸ 不入（域内/项目状态，留源 repo）：`capture-wordlist-recall-blindspot`(feature-05 域) / `wuprj-loops-never-ran-for-real`(项目状态) / `mc-emoji-uses-both-3account-junctions`(junction 基建) / `chartjs-bake-overlay-route-validated`(deck 域，ppt-html-route 已覆盖) / `stopfailure-hook-fix`(实现细节，机制子集已并入 cc-hooks-facts) / `feedback_reserve_annotation_block`(交互偏好，窄+低频) / `l4-fuel-gate2-already-met` / `user-language-chinese-only`。
- 未提交：用户手工 push。

## 2026-07-03 巡检轮（Mc-emoji 权限守卫升级 + reflect 管线签字桌收割）

> 主动巡检：仅 Mc-emoji 有 07-02→07-03 新料，其余源 repo 静默（3rd-ppt STATE 触碰=噪声、Agent-3/Wu Prj 无新增）。主料 = 权限守卫升级 plan（3 subagent 核官方文档）+ reflect 管线签字桌 + 4 条 07-03 auto-memory。

- ✅ **A1 `cc-permissions` 官方补强**（append）：deny→ask→allow 从实测推断→**官方明文**；**Windows 无沙箱→方案 A+hook 是唯一正解**；受保护路径机制 + **本机 V1 实测 user-scope `.claude` 未被覆盖**；模式辨别（dontAsk/auto 17%假阴性/acceptEdits 更松）；CVE 黑名单必被绕→靠 hook AST 分层。核实 2026-07-03 / CLI v2.1.159 / 易过期。
- ✅ **A2 `cc-hooks-facts` 补权限决策类 hook 拦截语义**（append，现卡无此对照点）：hook deny 拦 bypass / 只收紧不放松 / 多 hook 取最严 deny>defer>ask>allow / **fail-open→强制拦截须 exit 2（与 StopFailure observ-only 相反）** / 覆写守卫 protect-files 范式 + guard-overwrite.ps1 母本指针。
- ✅ **B `reflexes` 扳机①注释补「交付宣称」**：说『能用/双击即用/搞定』前先目标环境实测。源 = reflect 签字桌 #4 用户已签字点名"下轮 /KB-update 补"（默认=补注释、不单列新扳机）。
- ✅ **C `loops-and-automation` §7 补硬约束轴**：**Pro 订阅 OAuth 技术上跑不了无人值守定时**（400 organization disabled），真定时须 API Key。标易过期（Anthropic 政策）；另 3 层环境调试细节留源。
- ✅ **D `principles` 交互风格补「双层呈现」**：文档严谨技术语 / 汇报大白话，但拍板点仍给全候选+默认+赌注。源 = `plain-language-reports-rigorous-docs`（已活在 Mc-emoji CLAUDE.md，本轮升为跨 repo 偏好）。
- ⏸ 不入：`commit-push-at-milestone`（太薄，精神已被 prefer-autonomy 覆盖）/ `deploy-guard-hook-new-machine-steps`（换机部署 runbook，已在 SKILL-rm-permission）/ `headless-probe` command / Mc未来思考9（源 chat，已蒸馏进 loops-and-automation+plans）/ guard-delete 四闸实现细节（域内，留源）。
- **边界克制**：guard-delete 四重闸门/包装器正则表/reparse 检查 = 实现细节留源 repo，KB 只收官方机制事实 + 分层防御原则。
- 未提交：用户手工 push。

## 巡检台账（KB-update 前置扫描基线）

> 用途：KB-update「前置发现巡检」读此台账拿基线，只扫各源 repo **晚于"扫描截止"日期**的过程文件（忽略 office/pdf/ai 原材料）。事件驱动调起（大 feature 收尾 / 事故复盘 / 感觉攒够了），**非定时自跑**。每轮巡检后更新本表 + 上面"收割轮"叙事段。

| 源 repo | 扫描截止(基线) | 上次巡检 | 本轮结论摘要 |
|---|---|---|---|
| `3rd-ppt-prj` | 2026-06-02 | 2026-06-15 | Stage 0 已深挖（含孤儿审计）；过程文件≤05-29，无新增可入 |
| `[Agent-3] Info Classifier` | 2026-06-02 | 2026-06-15 | Stage 0 已深挖；过程文件≤06-02，无新增可入 |
| `[Agent-4] Wu Prj` | 2026-06-26 | 2026-06-26 | 富矿但本轮新增多为域内（deck/工艺单/竞品报告产线）。已入：task-decomposition / acceptance-ladder / 加密节D2 / python3D3 / 机器自检≠人工验收 / 沉淀分两轨 / solo-vs-team+陪审 / team残留config / autopilot-defer-perm-to-human-gate / **普适vs项目专属测试(06-26)**。已否：逐品类loop化、CLAUDE三层、派生层、复用核口径、deck域内(genre-skill/deliver-split)。借调 mc-emoji `feedback_kb_universal_vs_project_specific` 原出处 |
| `Mc-emoji` | 2026-07-03 | 2026-07-03 | **07-03 收权限守卫升级 + reflect 签字桌**：A1 cc-permissions 官方补强(Windows无沙箱/受保护路径V1实测/模式辨别/CVE) / A2 cc-hooks-facts 补权限决策类 hook 拦截语义(deny拦bypass/fail-open→exit2/覆写守卫) / B reflexes 扳机①补交付宣称 / C loops §7 补 Pro OAuth 不能无人值守→须API Key / D principles 补双层呈现。已否：commit-push-at-milestone / deploy-guard换机runbook / headless-probe / 思考9源chat / guard四闸实现细节。〔历史〕**07-02 收 feature-05 富矿**：cc-hooks-facts(待入候选 StopFailure/API 已开发完→收，+UserPromptSubmit exit-2 landmine) / reflexes 扩「先查再下结论」泛化+阳性对照 / principles 推广备份 / task-decomposition 机械词触发 / self-compliance-probabilistic 收尾。已否：capture-wordlist / wuprj-loops-never-ran / junctions基建 / chartjs-deck域 / stopfailure-hook-fix实现细节 / reserve_annotation_block / l4-fuel / user-language。〔历史〕已入：loops-and-automation / orchestrator-route分层 / mc-expert路径订正 / 普适vs项目专属测试(06-26,源在此)。已否：F4 Reviewer别造轮子 / reviewer-scope / prefer-autonomy / Clash·WSL·Codex环境域内 |
| `xiaoduo-Excel task` 等 | — | 未扫 | 按需 |

## Stage 1 状态
- ✅ 两决策点已定（2026-06-01）：① agent 位置 = repo 内 `.claude/agents/`（核实机制后定，非全局）；② 访问机制 = KB-only + 按需深挖
- ✅ `mc-expert.md` 落地（system prompt 编入：稳定层自足读法 + repo-map 按需深挖 + KB 补洞自检 + 固定输出结构 + 顾问≠替身 + 承接已决决策）
- ⏳ §4 验收（在本 repo 内开新 CC session，跑 3 个真实咨询：1 有先例 / 1 历史冲突 / 1 无先例，查引档路径对不对、置信度诚不诚实、低置信度是否正确升级）→ §5 ROI 闸门
