# Mc-Expert KB — 索引

> 中央知识库（薄）。稳定层 = 人工策展快照，可修正、不污染源 repo。
> 易变 domain 细节不在此，留各源 repo（见 repo-map）。建于 2026-06-01（Stage 0）。

> **当前客户端入口（2026-10-30）**：用户改用 claude-glm；共享资产与知识母本仍在本 repo，现有 junction 保留。入口与项目记忆消费规则见 [.claude/claude-glm-entry.md](.claude/claude-glm-entry.md)。下方早期账号部署说明是历史记录；当前调用 `/KB-update`、`/mc-update`、`/reflect` 无需原生 Claude。

## 核心文档
- [principles.md](principles.md) — 用户决策偏好卡（确定性 Python > LLM / 稳定 > 新颖 / 文档诚实 / 入库判据 / 交互风格·人工门最小化+需求冻结基线 / 环境约束）
- [reflexes.md](reflexes.md) — 跨 repo 硬反射（Office 路径·目标机折算 / inspect-first / skills-first / 先查再下结论·阳性对照 / done_when 阳性对照 + **验收范围禁缩窄/指标禁替换（09-18）** / 3-fail 熔断 + COM 2 次例外 / 不编辑产物 / Excel checkpoint·机器可读真相走确定性 diff / **MAX_PATH 深路径（09-18）** / `-LiteralPath`+Glob`[` / junction / **junction 判定须 `lstat()`（10-21）** / python3 stub），每条挂命中 repo
- [repo-map.md](repo-map.md) — 源 repo 地图 + 决策溯源子索引

## decisions/ — 跨 repo 已决决策（不重判，互链）
- [orchestrator-route](decisions/orchestrator-route.md) — 保留 Python orchestrator，瘦成 ~769 行薄 dispatcher，不归零；协作≠控制
- [per-agent-memory-no](decisions/per-agent-memory-no.md) — 不引入约定式 per-agent memory（CC 上下文隔离≠记忆隔离）
- [acceptance-guardrails](decisions/acceptance-guardrails.md) — 自动闭环三护栏（外部真相/重试硬上限/编排权留主 Claude）
- [ppt-html-route](decisions/ppt-html-route.md) — COM 两角色：HTML 只杀视觉创作，加密 I/O 底座永久保留
- [kb-memory-boundary](decisions/kb-memory-boundary.md) — KB 特殊：memory 两层分治（内容层只人工策展、auto-memory=待审 inbox、入库走判据闸门）+ CLAUDE.md 定位=薄操作手册非内容副本。⚠️含消歧指针：**源 repo 的 memory↔auto-memory 分流尺 ≠ 本卡**，那把尺在 mc-update 第 2 步。**2026-07-20 补**：候选晋升是**两段式**（inbox 可即时写 / 内容层禁直 Edit / 别把"走 /KB-update"误解成"当场跑完"）
- [autopilot-defer-perm-to-human-gate](decisions/autopilot-defer-perm-to-human-gate.md) — B 自主流程中途 rm/权限/敏感目录/对外命令一律后置人工门（halt=不执行+落盘+上报，**非阻塞式权限框**）；判据轴=「B 自主流程中途」非「无人值守」；源 2026-06-20 8h 死锁事故。已同步 `/free`·`/today`·team-task SKILL·agent-teams
- [self-compliance-probabilistic](decisions/self-compliance-probabilistic.md) — AI 规则 self-compliance=概率裁判，别为"提高激活率"建度量/监控；可靠性归冗余层两档（确定硬兜底 hook/人工门/熔断 + 概率软冗余 team/陪审，别混）；软自律扳机保留但不度量、不朝其爬山
- [scaffold-placement-via-claudemd](decisions/scaffold-placement-via-claudemd.md) — 过程文件「落点规约」必须烧进每个 repo 的 CLAUDE.md（每冷会话唯一自动加载层；skill 按需救不了/auto-memory 错位/hooks 过度工程）；bootstrap 默认模板只固化「计划/产物/复盘三大类去向」普适内核，不抄 production 域内结构（防候选 B 翻版）。落地于 mc-scaffold-audit skill
- [dual-tool-single-source](decisions/dual-tool-single-source.md) — Claude/Codex 双工具：知识层（角色/skill/runbook/memory）**单一真源**，两工具各配 ~5 行薄 shim 指向真源；机制差异（auto-memory vs hooks/sandbox）= 入口适配非两套知识。「两套 skill」是伪命题（5 角色 shim 字节级一致）。2026-07-18 冻结 + today-loop PASS

## references/ — 事实手册
- [cc-permissions](references/cc-permissions.md) — Claude Code 权限系统实测事实（方案 A + 6 反直觉事实 + **07-03 官方补强**：deny→ask→allow 官方确认/Windows 无沙箱→方案A唯一正解/受保护路径V1/模式辨别/CVE 黑名单必被绕 + **07-19 补**：显式 `ask` 规则压过 `auto` mode 放行→rm 弹框根因是 ask 非 auto 没激活 + **07-23 订正**：glm-5.2 auto「实测可用」证据不足降为存疑/删 guard 主论证改为概率不替代确定性兜底）
- [agent-teams](references/agent-teams.md) — Agent Teams 机制核实（2026-06-01，易过期）：teammate 可引 project-scope agent（mc-expert 无需转 user 级）+ mailbox/task list 自动对话 + Windows 走 in-process + **solo vs 冷启动 team 判据 / 关键门派 mc-expert 陪审（2026-06）** + **idle-零正文：故障模型+兜底单一权威节（2026-06-18 实证）——显式 SendMessage 必要不充分（in-process 投递 flaky + 疑似 session 截断）、有产物角色落盘承重；旧 Q8「显式即解决/不需落盘」已订正为指针** + **09-18 补：同源陪审盲区+调用三规范（审落盘终稿/控制流五问/跨栈终签）+ T2→T3 拓扑校准（漏斗 7 run 实证：公式对脚本驱动串行批处理偏高 T2）**
- [acceptance-ladder](references/acceptance-ladder.md) — 批量产线验收 = 五级首件递进阶梯（映射→内容→渲染→项目级→批量抽检；首件挑最难样本）〔Agent-4，2026-06-12〕
- [task-decomposition](references/task-decomposition.md) — 长链任务交底协议（信息三层 / 两段合同 plan 批准制 / 盘点先行+追问义务+拍板点封闭化 / 纠输入不纠输出）〔Agent-4，2026-06-10〕
- [loops-and-automation](references/loops-and-automation.md) — CC 自动化/Loops 架构（loop↔skill 正交 / 复用单位是 skill 非 agent / 五件套 / 台账=程序计数器 / 续命≠触发 / 原生优先 orchestrator 最后手段 / 写操作不无人值守 / **§5 触发三轴含 `/goal` Stop-hook 续轮(续轮器≠验收器) + §7 判轴别用错 cross-link autopilot，2026-07-19 易过期** + **§8 自循环空转·信号轴熔断（无新外部信号迭代硬预算 2 轮 / 裁判验决赛不验训练赛，2026-09-18）**）〔Mc-emoji 思考6，2026-06-12〕
- [cc-hooks-facts](references/cc-hooks-facts.md) — CC hook 机制事实（StopFailure=observ-only 交互式续不了/真续走 headless `--fallback-model` / UserPromptSubmit exit-2=全局变砖 landmine→launcher 防砖 / stdout 恒空 / settings 不热重载但脚本即时 / **07-03 补权限决策类 hook 拦截语义**：deny 拦 bypass·只收紧不放松·fail-open→exit2·覆写守卫范式）〔核 2026-07-02/07-03, CLI v2.1.193/159, 易过期〕
- [cc-command-skill-resolution](references/cc-command-skill-resolution.md) — CC command/skill 同名解析（同名时 `/slash` 直达 skill、command 壳成死代码；升级删壳或错开命名 chop→chop-task；today 升 skill 实测推翻「留壳必要」陪审判断）〔Mc-emoji 2026-07-12，易过期〕
- [claude-codex-memory-difference](references/claude-codex-memory-difference.md) — Claude vs Codex 跨会话 memory 加载机制差异（Claude harness 原生强送达 MEMORY.md 索引 vs Codex 原生只载 AGENTS.md 指令链、local Memories 默认关不读 Claude auto-memory）+ 软指针(候选A)够用 + 别为理论完整提前上 hook 的 5 痛点门槛 + 易踩措辞坑。配 [[dual-tool-single-source]]。〔Mc-emoji 2026-07-19 三路实测，易过期〕
- [auto-memory-index-hook-convention](references/auto-memory-index-hook-convention.md) — auto-memory 的 MEMORY.md 索引钩子写法规范（钩子=相关性触发器非摘要 / 三类「源XXX」区分 / ★ 承重语义保留 / 订正卡保守保留 / 瘦身配召回阳性对照 / 实测 15854→14248）。配 [[kb-memory-boundary]]·[[claude-codex-memory-difference]]。〔Mc-emoji 2026-07-29 瘦身+陪审，核实 2026-08-05，易过期〕
- [cc-skill-authoring](references/cc-skill-authoring.md) — CC skill 编写机制事实（args 按 shell-style quoting 切位置参数、多词裸传静默截断 → caller 固定 `'<mode> "<task>"'`；`$ARGUMENTS`/`$0`/named placeholders 全文展开、说明文字字面量须 `\$` 转义）〔Mc-emoji feature-05 plan11 三组 probe，核实 2026-07-16，易过期〕
- [cc-model-window-assumption](references/cc-model-window-assumption.md) — CC 网关别名模型 ID 按假设 200K 窗口封顶 auto-compact（`AUTO_COMPACT_WINDOW=400K` 被砍半 → ~120K 就触发）；正解 `CLAUDE_CODE_MAX_CONTEXT_TOKENS`（v2.1.193 起）；本机 claude-glm **已配置**（行为复测待 JSONL 判据）；复测判据防假阳性〔Mc-emoji temp.md 2026-08-18，官方文档+JSONL 双坐实；核实 2026-09-18，易过期〕

## agents/ — KB 自带 subagent
- [planner](.claude/agents/planner.md) · [coder](.claude/agents/coder.md) — Stage 3 Agent Team spike 的两个 teammate（planner=opus 规划+只读取证（有 Bash、无 Edit/Write，2026-08-19 一手实测）、coder=sonnet 实现）。同住被 junction 的 agents 文件夹 → 全局 user-scope 可用。见 `Mc-emoji/[feature-03]/sub-plan-stage3-agentteam-spike.md`。
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

## 2026-07-07 收割轮（探索期引用入 principles + hook 改动评估）

> 手上候选（非主动巡检）：① 任务背景1 = 上轮 mc-expert 陪审拍板的 A 方案（探索期规范入 KB）；② 任务2 = 用户 deploy 后问 hook 改动要不要 update。

- ✅ **E `principles`「架构与控制」簇 append「探索期乱得便宜/引用不许伸手」**：建探索脚本/拆 skill 时文件可随手放、但簇内禁伸手引兄弟目录/禁写死私料（病根=引用耦合非位置，别读成"要整洁"）。**只交叉引用 mc-scaffold §B.3（规约）+ 源 memory（行为），不复制正文**。源 = Mc-emoji `feedback_place_files_for_future_extraction`（plan09 / 07-04 hybrid 剥离，用户点名"真正有价值的经验"）。过闸：KB grep 零命中（新对照价值）× 轻量引用（维护成本极低）× 情景性故入 principles 非 reflexes（reflexes 要双 repo 命中、本条只 Mc-emoji 踩一次）。不升 user 级 CLAUDE.md 常驻（会撞 mc-scaffold「只放指针、别烧进冷启动 CLAUDE.md」旧决定）。
- ⚠️ **「张冠李戴待办 memory」经核实无可落点**：上轮叙述称"有条待办 memory 写'下轮给 principles 补一行'、被误当给探索期、实为给双层呈现"——grep 全 Workshop + 两处 memory（Mc-emoji auto-memory / glm user-memory）均无此待办；双层呈现 07-03 轮已 ✅ append（见上段 D）。故无待办可修正，**不凭空编**（守文档诚实 + verify-before-asserting）。
- ⏸ **任务2 hook 改动不入 KB**（domain 实施细节 + glm 账号状态变更，非跨 repo 普适经验）：capture_launcher 注释 3→4 账号（机制已在 cc-hooks-facts）/ guard-overwrite 保护清单硬编码→通配 `*\.claude*\` 覆盖 4 账号（已在 .ps1 注释自解释 + cc-hooks-facts 有守卫范式指针）/ stopfailure 撤销 glm 排除门（glm 部署决策；cc-hooks-facts 的"observ-only 机制事实"不变、无需订正）。**留痕建议**：glm 门撤销如要记，更新 Mc-emoji inbox `stopfailure-hook-fix`（非 KB 内容层）。
- 未提交：用户手工 push。

## 2026-07-14 收割轮（主动巡检 · 四路扫描）

> 主动巡检：Mc-emoji(07-07后) / Wu Prj(06-26后) / Agent-3·3rd-ppt(06-02后) / Hot-Fix(侦察) 四路，3 read-only agent + 主 Claude 扫 Hot-Fix。Mc-emoji 主料=feature-06-codex-workshop(domain)，Wu Prj 主料=deck/chart 产线域(domain)，Agent-3·3rd-ppt 确认无新料，Hot-Fix=暂存盘(重构repo-for-codex 是 Claude/Codex 共享 FAB 探索、plan07 多方案未收敛)。

- ✅ **① reflexes append「Grep 工具默认跳 hidden 目录」**：ripgrep 跳 `.`开头目录+尊重 .gitignore，下阴性结论前须显式指定 path / `rg --hidden`（`--no-ignore` 只绕 gitignore 不绕 hidden）。**「即使想核实工具也会骗你」= verify-before-asserting/阳性对照的工具层补丁**。源 Mc-emoji plan06 07-12 两次翻车。
- ✅ **② references 新建 `cc-command-skill-resolution`**：同名 command+skill 时 /slash 直达 skill、壳成死代码；升级删壳或错开命名(chop→chop-task)；today 升 skill 实测推翻 mc-expert 陪审 Q4「留壳必要」。CC 机制族(cc-permissions/cc-hooks-facts 同族)，标易过期。
- ✅ **③ agent-teams append「单发 subagent 掉线重试预算 max1-then-degrade」**：非 team 的一次性 spawn 陪审/补审 subagent 返回 Connection closed/零正文 = 同根 in-process 投递 flaky → 最多重试1次再降级(冷启动 general-purpose 补审/pending 交用户)，别连试≥2 空耗。idle-零正文权威节的单发分支补丁。源 Wu Prj 06-29 连掉3次空耗1/3任务。
- ⏸ **不入/留管道**：④ autopilot 边界(概率裁判reviewer≠确定性后置，与 self-compliance-probabilistic 重叠、落点需陪审) / ⑤ 陪审分两道·价值不对称(实例偏deck域) / ⑥ 主线漂移(已pin feature-05，留/reflect) / ⑦ C2 skill经验勿塞repo memory(尚在fuel、单repo) / ⑧ H1 FAB多AI共享repo方法论(mc-expert 07-13已裁定暂不入库：单用例+未实测+plan07/FAB多方案未收敛)。
- ⏸ **域内/已覆盖不入**：Mc-emoji codex实验domain(plan07-13/.ai/中立控制面/过度工程=已被「少做」覆盖) / Wu Prj deck-chart域技法 / Agent-3·3rd-ppt四月旧文07-01重触碰 / 账号配置/项目状态。
- 未提交：用户手工 push。

## 2026-07-19 收割轮（Mc-emoji · 手上有候选，非全量巡检）

> 来源 = Mc-emoji 本会话 temp.md 提案（claude-glm harness 核实 today-loop-for-claude 议题一手产出 + mc-expert 陪审）。feature-05 plan11（2026-07-16）早坐实同结论，但 KB 中央层未吸收，仍补。单点实测（claude-glm 单 provider/单探针）→ 写入标降级 + 易过期，plan11 不依赖路径（易搬移）。

- ✅ **A `loops-and-automation` §5 补第三条触发轴**：原只有「手动 / `/loop` 自动」两条 → 升级成三条（手动 / `/loop` 时间驱动 / **`/goal` 事件驱动 Stop-hook 续轮**）。4 个关键区分：①本质=session 级 prompt-based Stop hook（官方文档+本机"两 turn 强制接力"探针双坐实）②只续单 session、跨 session 靠状态台账（区别 Codex Goal 的 sqlite 持久）③**续轮器≠验收器**（evaluator 只看对话不读文件不跑测试，业务 PASS 须确定性自检+陪审先浮证据）④风险=条件未满足会"压过当 turn 指令"强续（today-loop 须加"前置门通过 AND 无 awaiting_human"谓词）。标易过期 + 2026-07-19/CLI v2.1.207。
- ✅ **B `loops-and-automation` §7 显式 cross-link 判轴**：在「Pro OAuth 跑不了无人值守定时」后加「判轴别用错」——「无人值守」是规范/环境轴，不是「自主流程中途权限后置」判轴（见 [[decisions/autopilot-defer-perm-to-human-gate]]，判据轴=是否 B 自主流程中途）。点明 today-loop 评估曾误用"无人值守→NOT_IN_SCOPE"推翻本可做需求。
- ⏸ **提案 3 不入**：新建 decision 卡 `goal-is-turn-relay-not-cross-session`——机制事实已进 references（提案 A），「today-loop 怎么用 /goal / 跨 plan 接力区分两段」是项目专属留 feature-05（呼应普适 vs 项目专属判据，[[decisions/kb-memory-boundary]]/06-26 收割）。
- ⏸ **不顺带处理游离判据 md**：`references/today完整版loop判据.md`（及引用的 `收尾loop判据.md`）= git 未跟踪中文文件名草稿，不在巡检台账已入清单，本轮只补已入库 `loops-and-automation.md`，纳入与否另开轮次（防 scope 蔓延）。
- 未提交：用户手工 push。

## 2026-07-20 收割轮（主动巡检 · Mc-emoji + Agent-3 双工具主题簇）

> 主动巡检：Mc-emoji(07-19后) / Agent-3(07-14后) 双富矿，Wu Prj·3rd-ppt·Hot-Fix 确认无新料。**07-19~20 两 repo 同步做 Codex 适配，产出一整簇 Claude↔Codex 双工具机制对照**——KB 知识层此前对 Codex 零覆盖（现有提及全是间接对照/域内标注/skill 实现，已 grep 核实）。用户挑 T1/T2/T7/T9/T12 五条。

- ✅ **T1 新建 `decisions/dual-tool-single-source`**：Claude/Codex 知识层单一真源 + 两工具各 ~5 行薄 shim；机制差异=入口适配非两套知识。「两套 skill」伪命题（5 角色 shim 字节级一致）。源 Agent-3 `plan-skill-unification`（07-18 冻结 + today-loop PASS）。过闸：KB grep 双工具零命中（真空白）× 跨 repo 普适（任何 Claude+Codex repo）× 呼应 principles 稳定/少做。
- ✅ **T2 新建 `references/claude-codex-memory-difference`**：Claude harness 原生强送达 MEMORY.md 索引 vs Codex 原生只载 AGENTS.md 指令链（local Memories 默认关、不读 Claude auto-memory）+ 软指针候选 A 够用 + **别为理论完整提前上 hook 的 5 痛点门槛** + 易踩措辞坑。源 Mc-emoji `X-Claude与Codex-Memory加载机制区别`（581 行，KB 收普适内核、项目特定落点 main-plan §4/T4 留源）。三路实测定级 PARTIAL（单点不外推）。配 T1（T1 讲知识单源、T2 讲读 memory 机制差异）。
- ✅ **T7 append `principles` 文档诚实簇「视觉模型输出可能是幻觉，必须交叉验证」**：视觉判断的阳性对照——①文件名推断不算证据 ②数字/编号对源核对 ③警惕自相矛盾，标准流程=**先哈希定归属→视觉定内容→源文字交叉验证→才采信**；分工=判归属用 SHA256、判内容才用视觉。源 Agent-3 `feedback_vision_subagent_codex_exec`+`feedback_pptx_image_residual_sha256`（07-16 PPTX 图片残留）。**落 principles 非 reflexes**：源单 repo 不满足 reflexes 双 repo 命中，但方法论（别把模型输出当真相）是普适判断纪律，与「机器自检≠人工验收」同族。
- ✅ **T9 append `cc-permissions`「auto mode vs 显式 ask 规则优先级」**：官网原文 "Explicit ask rules still force a prompt" + 本机 4 探针矩阵坐实（glm-5.2+auto on：rm/rmdir 在 ask 列表→弹框、mkdir/Write 不在→静默）→ **rm 弹框根因是 ask 规则非 auto 没激活**（别误诊断方向）；附第三方模型 glm-5.2 auto 实测可用（官网未列、降为参考备注）。源 Mc-emoji `X-顽疾复盘-B模式中途rm反复犯` §7。auto 版本门槛细节留源。
- ✅ **T12 append `kb-memory-boundary`「候选晋升两段式」**：源 Mc-emoji `temp.md`(07-20 事故复盘——差点直 Edit KB 内容层被拦)。正解=两段式（候选先进 KB inbox 即时暂存、用户择时跑 /KB-update 收割）；边界=inbox 可写 / 内容层禁直 Edit；通病=源 repo 会话"想固化"冲动下跳过 inbox 直奔写盘。呼应 self-compliance「规则在场却不激活」。
- ⏸ **不入（域内/已覆盖/单 repo）**：T3 Codex PreToolUse hook 协议 / T4 Codex sandbox COM 阻断 / T5 auto_review 部分等价 / T6 Codex memory-inbox 边界（前 4 条同 Codex 机制对照族，用户本轮只收 T1/T2 双工具内核，Codex 机制细节板板块留待 KB 定位"是否扩 Codex 面"再批量收）/ T8 视觉子进程机制层（与具体模型绑定，方法论层已收 T7）/ T10 /goal 续轮 MSYS 路径转换坑（续轮主料已覆盖，MSYS 坑 borderline）/ T11 判反复模式分两症状（borderline）/ Mc-emoji 候选5 Codex 过度工程反射(单 repo 待第二 repo)·6 追加式产物目录(工程范式)·7 B模式rm(KB decision 已覆盖)·11-13(项目特定) / Agent-3 候选F temp.md三连(需核实跨repo)·G 标签型空填区(acceptance-ladder 特化)。
- **Codex 机制板块判断**：T3/T4/T5/T6/T8 同属"Codex 端机制事实"，KB 现定位偏 Claude-centric。用户本轮未收 = 暂不系统性补 Codex 对照面；若未来 KB 定位转"双工具"，这批可批量收（届时 T2 已铺好 memory 差异基础）。
- 未提交：用户手工 push。

## 2026-07-23 收割轮（本 repo inbox 3 条 + KB-update 命令修正）

> **修命令在先**：跑 /KB-update 时主 Claude 第一反应去扫源 repo，漏了**本 repo 自己的 `.claude/auto-memory/` inbox**（待审收件箱才是巡检第一站）。用户当场点破 → 修 `.claude/commands/KB-update.md` 前置步：step 1 改成「先扫本 repo inbox」、补纪律「inbox 里凡还没晋升的本轮都要重新过闸门、别只看新不新」、源 repo 扫描降为 inbox 之后的补充。然后才按新 step 1 处理 inbox 3 条。

- ✅ **C1 `cc-permissions` §6 glm-5.2 auto 证据强度订正**（就地改写，hits 第 8 步「references 实证推翻就订正」）：原 07-19 写「glm-5.2 实测可用[参考备注]」是探针不锋利的过度断言——mkdir/Write 静默在方案 A 全 allow 配置下本就该静默、**无法区分 allow 放行 vs auto 放行**（阴性结论没做阳性对照，违 reflexes）；rm 判断生效未测；官网白名单不覆盖第三方（不证伪）。两边都不能一锤定音 → 订正为「证据不足」。**删 guard 主论证改为不依赖「glm 不支持 auto」**：即使 auto 激活、对 glm rm 判断未测 = 概率分类器不替代确定性兜底（链 self-compliance-probabilistic）。源 = 原 inbox `cc-permissions-glm-auto-evidence-insufficient.md`（07-20/21，mc-expert 陪审高置信；晋升后已删，正文见 cc-permissions §6）。
- ✅ **C2 `reflexes` 追加第 5 类扳机「治标优先于重构」**：用户因工具行为打扰而问「要不要重构/删守卫/换机制」= 停，先问治标能不能解眼前痛；只有治标失败或用户明示要重构才进架构评估。「别打扰我」是症状诉求、非拆安全网授权。实例 2026-07-20 B 模式被弹窗打扰问该不该删 guard。**诚实标注单 repo 起源、待第二 repo 命中**（不满足 reflexes 双 repo 严格判据，但跨 repo 普适交互模式 + 与现有四扳机同套路）。源 = 原 inbox `reflex-candidate-治标优先于重构.md`（07-21，mc-expert 陪审提炼；晋升后已删，正文见 reflexes 扳机簇）。
- ✅ **C3 `principles` 交互风格追加「人工门最小化 / 倾向深度授权」**（用户核心取向，原话）：人工门越少越好（盯屏太累）、默认倾向自主推进、攒到里程碑再找用户、未来常用 B 模式。守门判据=「防不可逆事故」还是「增加摩擦求稳」；4 红线人工门仍保留（链 autopilot-defer-perm-to-human-gate）。与文档诚实「不确定停下来商量」不冲突（兜底 vs 默认推进方向）。**落 principles 非 reflexes**：用户取向非机械反射、单 repo 表述。源 = 原 inbox `reflex-candidate-人工门最小化倾向深度授权.md`（07-23，用户明确表述；晋升后已删，正文见 principles 交互风格节）。
- ⏸ **today完整版loop判据.md 继续 defer**（07-19 已 defer）：git 未跟踪中文草稿、不在巡检台账已入清单，本轮主线 inbox 3 条，防 scope 蔓延。
- 未提交：用户手工 push。

## 2026-08-05 收割轮（仅本 repo inbox · 用户限定「只收割 kb-inbox」）

> 用户限定**只收割本 repo `.claude/auto-memory/` inbox**，不跑源 repo 巡检（场景=最简形态，只过 inbox 候选闸门）。inbox 5 条候选（排除 pin/ raw-signal lane）→ 三重闸门 → 用户拍板收 ①③④、②⑤ 不收。

- ✅ **① reflexes append「判 done_when / 验收项达标前：按字面判据跑阳性对照」**：自己正要写「D#/验收项达标」签注=停，先①标尺核对（拎 done_when 字面原文判据，不取二手结论）②阳性对照（构造会失败的输入真跑）。与「阴性结论需阳性对照」**互补不重**（那条管探针失灵→假阴性，本条管标尺用错+没跑负例→假 PASS）。源 = inbox `proposal-done-when-sign-needs-positive-control`（Mc-emoji double-workflow 首次验收：Claude 静态判 D3 达标、codex 独立复跑负例才抓出缺槽位仍 save+exit 0 假 PASS；mc-expert 陪审高置信 GO）。**诚实标注单 repo 起源、待第二 repo 命中**（判据同 07-23 C2「治标优先」先例：跨 repo 普适判断纪律 + 单 repo 起源先入 reflexes）。
- ✅ **③ `pipeline-self-check-loop/SKILL.md` append 第 5 条「被测链路含 AI 时：证据防 probe 后篡改」**：被测链路含 AI+工具时「产生了证据文件」≠可信（模型可 probe 后覆写退化内容、runner 只看「有新文件」表面 PASS）。两硬动作：证据通道对模型不可见（hidden+随机名+不进对话）/ 外部 schema 门+链路阳性与语义分离。与 reflexes「阳性对照」互补（指针不复述）。源 = inbox `proposal-pipeline-self-check-ai-proof-evidence`（Mc-emoji feature-05 plan11 + feature-06 plan14 双 feature 命中、Codex 产；mc-expert 陪审高置信 GO）。**⚠️ 落 skill 非 KB 内容层**——属 user-scope skill 母本维护（随 repo 版本化、该进 git）；`.agents/skills/` 不镜像此 skill（双工具 shim 只覆盖 double-workflow 相关 skill），无漂移风险。
- ✅ **④ 新建 `references/auto-memory-index-hook-convention`**：MEMORY.md 索引钩子写法规范（钩子=相关性触发器非摘要 / 三类「源XXX」区分纯溯源删·频次避坑留 / ★ 承重语义保留 / 订正卡保守保留 / 瘦身配召回阳性对照 / 实测 15854→14248 省≈460 token）。源 = inbox `auto-memory-index-hook-writing-convention`（Mc-emoji 2026-07-29 瘦身+陪审）。去重闸：references/ 零覆盖、kb-memory-boundary 讲分治边界不讲钩子写法=正交不重。标核实 2026-08-05 + 易过期（钩子注入机制随 CC 版本演进，链 [[claude-codex-memory-difference]]）。
- ⏸ **② 陪审 prompt 禁喂已采信结论 → 不收（留 Mc-emoji auto-memory）**：只在 Mc-emoji double-workflow 验收命中 1 次、reflexes 双 repo 门槛硬不过；本质是 [[self-compliance-probabilistic]] 的调用层补丁（软冗余非确定兜底），留项目层更合身。源 inbox `proposal-jury-prompt-no-feeding-conclusions` 保留在 inbox 待 Mc-emoji 侧处理。
- ⏸ **⑤ feedback_ppt_selfcheck → 不收**：已被 `pipeline-self-check-loop` skill 2b 视觉自检充分覆盖 + 单 repo + 低频，维持现状（已在 inbox MEMORY.md 记录）。
- **边界克制**：本轮不扫源 repo（用户限定）；references/ 两个游离中文草稿（收尾loop判据 / today完整版loop判据）维持 defer（07-19/07-23 既有决定，防 scope 蔓延）。
- 未提交：用户手工 push。

## 2026-08-25 收割轮（inbox 索引补账 + 双候选晋升 + 1 移送 · mc-expert 独立陪审）

> 场景 = 用户「检查 kb-inbox」→ 发现 inbox MEMORY.md 索引漏登 2 条实际文件（proposal-claude-skill-args / proposal-planner-acceptance）→ 先补账，再按推荐走 /KB-update 收割 2 条 + 移送 1 条。**mc-expert 独立陪审（本会话重判、未采信提案内记录的前轮陪审）**：三条全 GO-with-changes，6 处修正全部采纳（假引「严禁 COM」删除 / 「执行机 vs 目标机」表述统一为「产物最终落地机器」 / 「CLI 版本见源 repo」假指针改如实标注 / 移送三必改 / 悬空指针 / 护栏判据）。

- ✅ **① reflexes「Office 文件路径」节末 append 元规则**：反射前提 = 产物/脚本**最终落地执行**的那台机器；分发场景按目标机加密状态折算（目标机加密 = 命中既有「条件性回退」，别拿开发机明文判「默认 Python」）。源 = inbox `proposal-kb-reflex-needs-target-machine-premise`（Agent-3 Info Classifier 2026-08-14 双环境生产证伪：本机明文、面向同事的 skill 跑在加密机，用户原话「绝对表述必须附前提」；分支细节项目专属、留源 repo AGENTS.md §3.1）。
- ✅ **①-附属 principles 环境硬约束同步一句**（维持该节 gist+指针双层 parity，防 L44 变成无前提绝对表述）：「分发场景按目标机折算」+ 指 reflexes 元规则。
- ✅ **② 新建 `references/cc-skill-authoring`**：args 切分 + 占位符展开机制事实（裸多词静默截断 / caller 固定 quoted 写法 / `$ARGUMENTS` 全文展开、字面量 `\$` 转义 / 缺参=空可作 fail-loud）。源 = inbox `proposal-claude-skill-args-quoting-and-literals`（Mc-emoji feature-05 plan11 三组 probe 2026-07-16 + 官方文档明文背书）。第二层标注「官方文档+probe 双坐实」、CLI 版本如实标「未随 probe 记录（claude-glm 分发）」。
- ✅ **③ 移送 `proposal-jury-prompt-no-feeding-conclusions` → Mc-emoji/.claude/auto-memory/**（兑现 08-05 已决「不收中央」欠账）：整文件移送 + frontmatter 改造（moved + KB 溯源）+ **对侧 MEMORY.md 索引登记**（防孤儿）+ 删 KB inbox 原件 + 修 `proposal-planner-acceptance` frontmatter 悬空指针（原硬引 KB inbox 路径 → 改指 Mc-emoji 新路径）。Mc-emoji origin（`.codex/memory-inbox/2026-07-16-*`）回写 accepted。
- ✅ **inbox 索引补账**：MEMORY.md（inbox 版 + 会话记忆版）补登漏掉的 2 条，恢复索引与事实一致。
- ⏸ **不晋升（维持留置）**：`proposal-planner-acceptance-scope-no-narrowing`（前置=第二不同领域 repo 命中 + 判据轴去 pptx 特化，未满足）；`proposal-team-task-funnel-risk-routing-pilot`（观察期，需 ≥3 跨形状真实 run）；`feedback_ppt_selfcheck`（已被 skill 覆盖，备查）。
- **⚖️ 护栏判据（mc-expert 陪审要求写死，防「补前提」变绕闸话术）**：对既有节**只补隐含前提 / 收窄适用范围** = 维护性订正，**不受双 repo 闸门**（先例：2026-06-15 环境翻转整节改写同为单事件驱动）；**新增扳机/动作** = 新反射，仍须双 repo 命中（或 L28/L29 式「单 repo 起源+诚实标注」例外，已两个、从严开第三个）。本轮①按此判据归前者入的库。
- **诚实计数**：①的跨 repo 实证 = **1**（Agent-3；project-archive-starter 是同 repo 内第二工件，不算跨 repo）——不满足双 repo，按上护栏归「既有节前提订正」入库，非新反射卡。
- **留观（陪审提出、下轮巡检核）**：`cc-command-skill-resolution` 也含「CLI 版本见源 repo」句式，若源同样未记版本 = 同类假指针，下轮顺带核、不扩本轮 scope。
- 未提交：用户手工 push。

## 2026-09-04 收割轮（熔断阈值统一 2→3 · 2026-09-18 补账）

> 该轮由 Wu Prj team-task 施工会话（经用户终裁授权）同步落地 KB，当时未留收割轮叙事；09-18 巡检发现后补账。源 = Hot-Fix `2026-09-04 team-task-retrospective` §9（5 份 jsonl 逐段核对的两 run 机制复盘 + Codex 独立评估 §8）。**改动已随 2026-09-17 前的分主题 commit 入库**（4b7d142 熔断 2→3 全链清扫 + e8ce925 review-contract-v2 §3.3 + cfcd2d8/80b3406 team-task·team-workflow + f7b4a8d 实验环境无加密前提注记），本节只补叙事账。

- ✅ **reflexes「控制与失败」簇重构**：旧「连续失败 2 次熔断」拆两条——「任务/方案第 3 次连续失败熔断」（同一稳定 `failure_key`，前两次取证/陪审/换路线，第 3 次停机交人工；换建议/agent/session 不重置计数）+「COM 单文件连续超时 2 次即 CUTOVER（基础设施例外）」不混算。〔Wu Prj，2026-09-04 用户拍板〕
- ✅ **同口径散点全链同步**：acceptance-guardrails 护栏② / self-compliance-probabilistic 硬兜底行 / autopilot-defer-perm 互链 / agent-teams Q4+solo 条 / task-decomposition 两段合同 / today完整版loop判据 §2/§3 / principles 人工门条追加「前两次失败优先取证、陪审并尝试可回滚替代路线」+ `autopilot_failcount.ps1`·`codex-failcount.ps1` 计数脚本改 3。
- ⚠️ **教训（09-18 补账时发现）**：本 MEMORY.md 索引行当时漏同步（reflexes 钩子仍写「2-fail 熔断」直到 09-18 才改）——**索引钩子是同口径散点之一，改簇内容时进全链清扫清单**。

## 2026-09-18 收割轮（主动巡检 · 六源 + 3 新 repo 首扫 · 裁决 ①a/②b）

> 触发 = 用户主动巡检。四路 Explore 侦察（Mc-emoji / Agent-3 / Wu Prj+3rd-ppt / monday-com+fangcaixia×2）+ 主 Claude 直扫 inbox/Hot-Fix + 台账大修（monday-com·fangcaixia×2·Fund-2026·紧急备份 4 新行登记、xiaoduo 行移除、Wu Prj 更名订正、全源基线刷 09-17）。用户拍板：**①a（planner 前置双轴认定满足）/ ②b（funnel 部分晋升）/ A 组全做 / B1-B5 全收 / C 收 C1 C4**。mc-expert 独立陪审（ENHANCED_FINAL，9 处源档直读 + settings.json 一手实测）= **GO-with-changes**，必改 3 + 建议级全纳。

- ✅ **B1 reflexes append「判 done / 定验收范围前：范围禁缩窄成已过子集、验收指标禁替换成可自证代理」**（L30，done_when 阳性对照的姊妹条，判据轴去 pptx 特化）。命中账本 = Mc-emoji×2（feature-08 origin 三次用户纠正 + feature-09 docx 复发，planner done_when 逐条核对 5×FAIL 硬现场）+ Agent-3 goal-replacement（跨 repo）+ fangcaixia review1 cousin；monday-com B-002 = 判别例不计入（正确拒绝）。**口径纪律（陪审确认）**：按「事件」收、不按「分布」收——思考14 的「三轮 P11 漏判分布」账目被 mxp 指出三处口径自相矛盾（planner 自认表格凭记忆现编），凡依赖「谁抓到几次」的表述不入 KB。裁决 a 推理 = repo 轴（Agent-3）+ 领域轴（pptx→docx）各有实票；陪审判定推理无漏洞且实际更稳（Agent-3 一票本身近乎跨领域）。inbox 提案回写 applied（含 applied_at）+ Mc-emoji origin 回写 accepted。
- ✅ **B2 `loops-and-automation` 新 §8「自循环空转：信号轴熔断」**：无新外部信号迭代硬预算默认 2 轮（明确归因陪审 Q4 建议、不当实证规律表述）；熔断判据 = 停在人工门后无新信号 release / 6+2+0 ledger / 答案文件在盘上没人消费；裁判验决赛不验训练赛（dev 母本连续 PASS 再冻结 + SHA256 字节级一致当日实效）；reflexes 3-fail 条补姊妹轴反向指针。〔Agent-3 中期评估 + Mc-emoji 思考14 同核〕
- ✅ **B3 新建 `references/cc-model-window-assumption`**：未知/网关别名模型 ID → 200K 假设窗口封顶 auto-compact（400K 砍半 → ~120K 触发）；正解 `CLAUDE_CODE_MAX_CONTEXT_TOKENS`（v2.1.193 起）。**「本机已配置」而非「已落地」**（陪审 P1 必改：配置在位 ≠ 行为复测，JSONL 复测待下次长链会话按 §复测判据验）。
- ✅ **B4 agent-teams append「同源陪审盲区 + 调用三规范」**：同栈 GO vs 跨栈 7 阻断（**team-task 授权书 v1，思考14 为编年载体**——陪审订正归属）；三结构因（审概要非终稿 / 检查单窄 / 同源共享盲区，能力差距仅约 1/3）；三规范（审落盘终稿 / 控制流五问 / 高影响跨栈或人工终签）；mxp 验设计对不对、原生验接口写死没有 = 互补两层非替代。单 repo 起源诚实标注。
- ✅ **B5 reflexes append MAX_PATH 深路径条**：诊断签名 = shell 可见 ≠ venv python `open()` 可读（CRT IO 非 long-path-aware）；staging 绕行；`\\?\`+rglob 超时坑。诚实标注 = 同一事故（2026-08-17 KJX2026021）双 repo 档案、非两个独立命中。
- ✅ **C1 principles append「需求冻结成基线 md，弹问前先查基线」**：唯一权威 + 禁软化 + 变更仅显式授权记档 + 弹问前先做「问题↔基线条款」映射；用户原话×2 与需求基线-FROZEN.md 逐字核过；机制经 4 次显式授权变更行使验证（§5：09-07/11/14/15）。
- ✅ **C4 拆两半（源 repo 中期评估 §8.7 预注册）**：① reflexes「Checkpoint 走 Excel」补适用边界（管签字载体格式不管门的存在性；机器可读真相走确定性 diff 不设人眼逐格签字门）= 维护性订正不受双 repo 闸；② acceptance-guardrails append「护栏①操作化：golden-answer 驱动验收 + 防背答案三铁律」（答案只进 diff 侧 / diff 与 build 分立 / 撤掉答案照跑；逐字 diff 只管数据投影层）。**两侧已双向互链**（陪审必改：原只有 guardrails→reflexes 单向）。
- ✅ **②b funnel 提案部分晋升**：跨 repo 内核「T2→T3 拓扑校准」append `agent-teams` solo-vs-team 节（7 run 实证、override 5+ 次、公式对脚本驱动串行批处理系统性偏高 T2——估的是协调复杂度不是失败面）；inbox 提案证据大更新（7+ 真实 run 全 PASS + 09-04 机制复盘）+ 剩余跨形状前置（team 拓扑 / 问卷或断线重入 / 跨域）+ B10 轻量校验随全量评估联动；**未全量晋升**。
- ✅ **A 组**：A1 = 上节 09-04 补账；A2 台账（巡检时已更）；A3 = inbox 两提案回写 + origin accepted。
- ⏸ **不收（留档/下轮候选）**：C2 披露≠合法降级（agent-teams 掉线条 append 实例）/ C3 approved_display_alias 审批字段后门 / C5 skill 分发生命周期 / C6 Wu Prj 6 条 feedback 打包 / C7 工作流收敛终局拍板（09-04 已拍，候选待整）/ C8 agent-teams experimental 校准注 / C9 Codex 板块（skill 生态对比、auto-review 边界、allow_implicit_invocation、chatgpt-app 共用 HOME——与本 repo `.agents` 未提交件对照去重后批量决策「是否扩 Codex 面」）。
- **陪审 GO-with-changes 全纳**：必改 3（B3 落地→配置+复测待验并连带索引钩子 / reflexes↔guardrails 反向互链 / B4 授权书归属 team-task）+ 建议级（B1 事故/复盘日期消歧 + 稳定指针补 inbox 提案 / origin 补 `applied_at` + review 消歧 / override 统一「5+」/ 3-fail 姊妹轴指针 / 「未知模式」句撤引号式转述 / funnel 指针写具体文件名）。**UNVERIFIED_SCOPE 留痕**：B5「305→102」数字未逐字复核（305 有 fangcaixia-07-30 台账实证）、B3 官方两 URL 未在线复核（按 temp.md 08-18 核实记录采信）、C4「未知模式」句未定位逐字原文（已降为转述）。
- 未提交：本轮 7 件内容层改动（6 改 + 1 新卡）用户手工 commit（可 /mc-commit 理批）。

## 2026-10-21 收割轮（team-workflow v0.3 会话顺手收 · 单条直入库）

> 来源 = Hot-Fix 会话 team-workflow v0.3 升级的 mc-expert 独立评审附产品（junction 检测工具坑，mc-expert 自述第一轮被 stat() 假阴性骗过）。策展人在场，三连问闸门当面对过（3/3：新对照价值 × 双 repo 事件源 × 一条 bullet 零维护），用户拍板「入」。未走 inbox 中转（策展人在场即闸门，先例=两段式判据的"用户择时"极端形态）。

- ✅ **reflexes「环境/工具」簇 append「判『是不是 junction』Python 必须 `lstat()`」**：`stat()`/`os.walk` 穿透 reparse point → 「双份拷贝需同步」假阴性（两侧 hash 相同=同一物理文件）；Glob 拿 junction 当 path 实测静默返空（同底层 Grep 未单测、按同族防范——**比提案稿更收紧的诚实标注**，本会话只实测过 Glob）；正解 `os.lstat()` / `Get-ChildItem -Force` 看 LinkType（junction 常挂子项级、根目录 LinkType 空≠没有）；跨 junction 找文件直接指定真源路径。与 junction 契约条（改前扫引用）为姊妹、同「工具盲区骗你」族。事件源双 repo：Mc-Expert-repo 2026-08-19（用户多次纠正「双侧同步」误判，原话「反复犯了无数次」）+ Hot-Fix 2026-10-21（mc-expert stat() 假阴性亲踩 + Glob 返空同会话实测）；检测语义细节为本次新沉淀、已诚实标注。Hot-Fix 项目侧记忆（userprofile-agents-junctions）同会话已补 lstat 注，两层不冲突。
- ⏸ **不入：team-workflow v0.3 升级本身**（`run <文档>` B 代起草=skill 操作面，活在 SKILL.md/relay.md + bak 链 + mc-expert 两轮评审记录；先例=06-18「team-task 体系重构 操作落地不入」）。v0.3 成熟度自注「待真实双窗口使用验证」。
- 未提交：reflexes.md + MEMORY.md 两处，连同同工作区 team-workflow v0.3 三文件（team-workflow SKILL.md / relay.md / team-task SKILL.md），用户手工 commit。

## 巡检台账（KB-update 前置扫描基线）

> 用途：KB-update「前置发现巡检」读此台账拿基线，只扫各源 repo **晚于"扫描截止"日期**的过程文件（忽略 office/pdf/ai 原材料）。事件驱动调起（大 feature 收尾 / 事故复盘 / 感觉攒够了），**非定时自跑**。每轮巡检后更新本表 + 上面"收割轮"叙事段。

| 源 repo | 扫描截止(基线) | 上次巡检 | 本轮结论摘要 |
|---|---|---|---|
| **本 repo inbox**（`.claude/auto-memory/`） | 2026-09-17 | 2026-09-17 | **09-17 巡检**（主动巡检·全源 6 路）：3 条全重过闸——①ppt_selfcheck 维持不收（已覆盖）；②funnel 提案证据已严重过时：Wu Prj `team-progress-012~018`=**7 个漏斗真实 run**（远超 ≥3 前置但全同域同形、T2→T3 override 5+ 次留痕）+09-04 retrospective B1-B7 审计/B10 挂账 → 提案待更新+晋升裁决交用户；③planner-acceptance 新命中账本（Mc-emoji feature-09 docx=同repo跨域 / Agent-3 goal-replacement=跨repo同pptx域 / fangcaixia09-08 负例子集化 cousin / monday-com B-002=判别非命中）+ **文件自身口径冲突**（frontmatter「第二个不同领域 repo」 vs 收割检查清单「第二个不同领域长链任务」）→ **09-18 裁决：①a（planner 前置认定满足）②b（funnel 部分晋升）；A 组全做 / B1-B5 全收 / C 收 C1 C4**，收割记录见「2026-09-18 收割轮」叙事。〔历史〕**08-25 收割轮**（用户「检查 kb-inbox」触发，非全量巡检）：先补 inbox MEMORY.md 索引漏账 2 条（proposal-claude-skill-args / proposal-planner-acceptance）；再收 ①(Office 路径目标机元规则→reflexes append + principles 同步)+②(skill args 机制→references/cc-skill-authoring 新建)；移送 ③(陪审禁喂结论→Mc-emoji auto-memory，含对侧索引+origin 回写)；留置 planner-acceptance(双 repo 前置未满足)+team-task 漏斗(观察期)+ppt_selfcheck(已覆盖)。①② 晋升后已删、③ 移送后已删。mc-expert 三 GO-with-changes 全纳（含「补前提 vs 新例外」护栏判据，见收割轮叙事）。**纪律**：inbox 里凡还没晋升的每轮都要重新过闸门、别只看新不新。〔历史〕**08-05 复扫**：收 done_when 阳性对照+pipeline 防篡改+索引钩子写法，不收陪审禁喂结论+ppt 自检 |
| `3rd-ppt-prj` | 2026-09-17 | 2026-09-17 | **09-17 复扫**：基线后实质新增 1——`AGENTS.md` §8「temp.md 强制三连」读侧消费状态机（与 KB ec86c81 写侧门同族反向）+ §9 guard-overwrite 07-22 退场记录；候选挂 Codex 板块对照。〔历史〕Stage 0 已深挖；**07-20 复扫**：晚于 07-14 仅`.git/FETCH_HEAD`(元数据)，过程文件≤06-16，确认无新料。〔历史〕**07-14 复扫**仅 STATE 06-02 触碰(噪声)，过程文件≤06-02 |
| `[Agent-3 Claude+Codex] Info Classifier` | 2026-09-17 | 2026-09-17 | **09-17 复扫**：基线后 ~110 md（08-11~25），主矿=triple-workflow run `a481ca6c` 10 轮 rc+三轮复盘。强候选：自循环空转账目（6 建门+2 语义推测+0 消费人工信号；答案文件在盘上 6+2 轮无人读）/goal-replacement 同核命中（08-14 重大事故复盘：用程序门 PASS 代替效果验收）/「披露≠合法降级」（独立复核 spawn 3 败→codex-glm 自审 PASS_NO_CHANGE 冒充补审）/approved_display_alias 审批字段不验证批准事实=后门/MAX_PATH>260 反射（venv python 可读性≠shell）/golden-answer 防背答案三铁律+用户原话×2（标准答案是映射基准非签字对象）。域内留原地：KJX 修复族/L 层实现/双分类误判。〔历史〕**07-20 富矿**：07-15~20 双主线=①Codex 端机制适配(hooks/sandbox/auto_review/视觉子进程)②双工具单一真源+project-archive-starter 重建治理。收 T1(单一真源决策)+T7(视觉防幻觉,落 principles)。已否域内(染色/槽位/mapping/移植技法)。**07-14 复扫**(历史)：07-01 一簇 feature/skill 重触碰(域内)，无新 auto-memory，确认无新料 |
| `[Agent-4 Claude] Wu Prj`（目录已由 `[Agent-4] Wu Prj` 更名） | 2026-09-17 | 2026-09-17 | **09-17 复扫**：260 新 md（171 progress=执行日志略）。主料=①`team-progress-012~018` **7 个漏斗真实 run**（funnel 提案证据流，全 MEDIUM/GLM/常设授权；T2 公式建议被 T3 纠偏条 override 5+ 次=提示矩阵对脚本驱动串行形状可能系统性偏高）；②`需求基线-FROZEN.md`（09-04 用户原话「为什么需要我拍板…按标准要求执行即可」+冻结基线机制）；③15 条 auto-memory（跨 repo 6 条：counts-disk-truth / declared-change-grep-verify / primary-source-personal-read / verifier-evidence-source-guard / trace-merge-by-file / write-truncation-verify 带 Write 尾部静默截断机制事实）；④09-11 skill 生态对比（Codex 板块；⚠️ 本 repo 未提交 `.agents/skills/_mc-common/codex-runtime-bindings.md` 已吸收大半、晋升前先对照去重）。planner 缩窄零命中（done_when 全规范用法）。〔历史〕**07-20 复扫**：晚于 07-14 的文件=**0 个**（最新停 07-01 的 `.lock`，过程文件全 ≤06-30）。⚠️ **基线滞后提示**：07-14 基线切在该 repo 沉默期之后，06-29/06-30 最后一批 feedback（marker_prefix / deck_split_browextract / keygate_mc_expert_jury）按时间窗本应在更早轮覆盖——若日后怀疑漏收，可回查 06-28~06-30 窗口。本轮无新增可入。**07-14 复扫**(历史)：新增集中 deck/chart 产线域(域内不入)，收单发subagent掉线重试max1(append agent-teams)；〔历史〕富矿但本轮新增多为域内（deck/工艺单/竞品报告产线）。已入：task-decomposition / acceptance-ladder / 加密节D2 / python3D3 / 机器自检≠人工验收 / 沉淀分两轨 / solo-vs-team+陪审 / team残留config / autopilot-defer-perm-to-human-gate / **普适vs项目专属测试(06-26)**。已否：逐品类loop化、CLAUDE三层、派生层、复用核口径、deck域内(genre-skill/deliver-split)。借调 mc-emoji `feedback_kb_universal_vs_project_specific` 原出处 |
| `Mc-emoji` | 2026-09-17 | 2026-09-17 | **09-17 复扫**：~100 md，最新=feature-09（无 feature-10），主矿=`Mc未来思考14：实战 II`（3746 行 double→triple→team-task 编年史）+temp.md(08-18 交接卡)。强候选：`CLAUDE_CODE_MAX_CONTEXT_TOKENS`（陌生模型 ID 按 200K 假设窗口封顶 auto-compact，v2.1.193 起、2.1.215 实测）/同源陪审盲区+三调用规范（同栈 mc-expert GO、跨栈 Codex 抓 7 阻断；审落盘终稿/控制流五问/跨栈终签）/skill 分发 5 部分生命周期（移植指南 v1.2）/09-04 终局拍板（team-task=未来主入口、全部开 auto、停止升级）/feature-09=planner 缩窄第二命中（同 repo、pptx→docx）/Agent Teams「默认自主交流」实为单机观察官方仍 experimental。留原地：Office probe/账号切换器/思考13/emoji.md。〔历史〕**07-23 复扫**：本轮 3 条候选(C1/C2/C3)原档均标 Mc-emoji 源(07-20~23 /reflect 会话 + feature-07)，但**候选已先落本 repo inbox**、经 inbox 路径晋升(见上"本 repo inbox"行)，故 Mc-emoji 源 repo 本轮不再单独深扫——inbox 已是这些料的中转站。**07-20 收**(历史)：主料=feature-06 闭口+feature-07 codex-memory 路由，双工具机制对照大爆发。收 T2/T9/T12。已否：候选5/6/7/10/11/12/13/8/3。〔历史〕07-19 收 loops §5/§7；07-14 收 Grep跳hidden+CC同名解析；07-03 权限守卫升级+reflect签字桌；07-02 feature-05 富矿。已入：loops-and-automation / orchestrator-route分层 / mc-expert路径订正 / 普适vs项目专属测试。已否：F4 Reviewer别造轮子 / reviewer-scope / prefer-autonomy / Clash·WSL·Codex环境域内 |
| `Hot-Fix` | 2026-09-17 | 2026-09-17 | **09-17 复扫**：主料=09-04 `team-task-retrospective`（5 份 jsonl 逐段核对的两 run 机制复盘；funnel 提案证据前两票+B1-B7 审计+B10 缓议挂账+09-04 用户终裁族：默认 B+T4-AUTO+MEDIUM 不弹问/失败预算 3/基础设施例外/addendum 链——其 KB 侧同步已随 4b7d142/e8ce925 等 commit 入库、收割叙事 09-18 补账）；08-31 chatgpt-app vs codex 机制对比→挂 Codex 板块。〔历史〕暂存盘。**07-20 侦察**：晚于 07-14 唯一新增=`auto-compact bug.png`(图片原材料，非 md)，非排除 .md 全 ≤07-13(重构repo-for-codex 那批)。仍暂存未收敛，无新增可入。H1 FAB 多 AI 共享 repo 方法论维持暂不入 |
| `monday-com` | 2026-09-17 | 2026-09-17 | **09-17 首扫**（活跃 repo，至 09-16）。候选：`Mc思考01` L1192-1338（chop↔double 接线三摩擦 + glm-token 耗尽→codex 原生 spawn agent 接手、「triple workflow 已无实际价值」）/08-19 incident 复盘（测试全绿仍事故 8 缺口表+责任权重）/`B-002-验收陪审要点`（风险模式→锋利负例断言九项；reflexes L28 的跨 repo web 域应用候选）/AGENTS.md 防循环硬停门含防重置条款+temp 原子三步。域内：sync-main·commit-push-pr（绑特定 origin）/feature-01 状态 |
| `fangcaixia-PC-repo-07-30` / `-09-08` | 2026-09-17 | 2026-09-17 | **09-17 首扫**（生产机快照×2）。07-30：triple-workflow 真实 run 实证（tester 接力合同样本/双 worker token 防伪状态机/doctor 防绕过链「Do not bypass doctor」/MAX_PATH 305 字符 ENOENT×4 实证）；09-08：detail-auto 冻结合同+两轮 mc-expert 终审实证（P1 抓「负例只证明已过子集」=planner 缩窄 cousin；review2 GO 确认关闭）+工作记录教训总结（域内为主）。域内：KJX 修复族/视觉 route-probe |
| `Fund-2026` | 2026-09-17 | 2026-09-17 | 在途 repo（当日活跃：mc-portfolio / debug/菜单6 系列 / reports）。按需不深扫 |
| `紧急备份-repo` / `------- History留档-double-workflow -------` | — | 2026-09-17 | 归档快照（07-22 Mc-emoji pre-slim / 08-02 monday-com 阶段1），不扫。`xiaoduo-Excel task` 目录已不存在（原「按需」行移除） |

## Stage 1 状态
- ✅ 两决策点已定（2026-06-01）：① agent 位置 = repo 内 `.claude/agents/`（核实机制后定，非全局）；② 访问机制 = KB-only + 按需深挖
- ✅ `mc-expert.md` 落地（system prompt 编入：稳定层自足读法 + repo-map 按需深挖 + KB 补洞自检 + 固定输出结构 + 顾问≠替身 + 承接已决决策）
- ⏳ §4 验收（在本 repo 内开新 CC session，跑 3 个真实咨询：1 有先例 / 1 历史冲突 / 1 无先例，查引档路径对不对、置信度诚不诚实、低置信度是否正确升级）→ §5 ROI 闸门
