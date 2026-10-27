# today 完整版 loop 判据（/today-loop · 单一指针）

> **定位**：`/today-loop`（完整版 loop 独立入口）的**判据单一来源**。Run Contract（一次性授权包）、状态机迁移、每阶段 PASS / REWORK / WAIT_HUMAN 判据、compact 韧性、台账 schema 校验、第 3 次失败熔断守卫的归属——**改判据只改这一处**。
>
> **与姊妹文件的关系**：本文件是「完整版 loop（多 plan、跨 turn、跨 session、`/goal` 续轮）」的判据；`收尾loop判据.md` 是「单 plan 收尾三段（mc-update→pin→session-new）里的 pin 补漏层」判据。两者正交：完整版 loop 的 CHECKPOINT 阶段**仍引用 `收尾loop判据.md`** 做 pin 段，本文件不重复 pin 判据正文。
>
> **节奏认知（sediment-two-tracks）**：完整版 loop 判据 0 次独立验证（Phase 5 pilot 之前都是 fixture 演练、非真实跑）。本版只做"判据 + 台账模板 + fixture"轻量固化，**不产 live today-loop/today-core skill**（Phase 2/3 才动母本）。判据经 Pilot A–D 验证稳定后，本文件升完整 skill。
>
> **gap（文档诚实）**：本版 = Phase 1 契约固化版。判据本身的可执行性要等 Phase 3 接 today-loop 实现 + Phase 5 真实 pilot 才能证；当前只保证**设计自洽**（Phase 0 状态机探针 4/5 fixture 过 + 1 个文档清晰度缺口已在本文件补）。
>
> 源 plan：`Mc-emoji/[feature-05-loop-self-improvement]/plan11-Claude-today完整版loop升级评估与施工计划.md`（D1–D7 全拍板，D1 修订=只留 `/today-loop` 单入口）。
> Phase 0 产物：`Mc-emoji/[feature-05-loop-self-improvement]/output/plan11-phase0-probes/`（最终结论 `phase0-partial-findings.md` + 状态机探针 + 权限阳性对照设计 + 实验日志）。

---

## 0. 一句话总览

用户**一次** `/today-loop` 启动 + 粘一行短 goal（人工确认门）后，Claude 自动跨 turn / 跨 session 推进多个 plan，只在**三终态**或**显式验收门**停：

- 业务真相唯一来源 = **repo 本地台账 `today-loop-state.md`**（不靠 context 记忆当程序计数器）。
- 续轮器 = **`/goal`**（本质是 session 级 prompt-based Stop hook，Phase 0 实测坐实），它**只负责"再开下一 turn"，不负责判业务是否完成**。
- 阶段质量门 = **结构性自检（确定性）→ mc-expert 陪审（概率软冗余）**，两层缺一不可，自检无证据或陪审无 verdict 都不得 PASS。

---

## 1. Run Contract（一次性授权包 · 冻结字段）

进入完整 loop **只问一次**，之后不逐阶段重复问。授权包通过人工确认门后写入台账 `run_contract` 段；后续模型或 subagent **不能扩大它**——发现新路径、新外部系统、新增交付对象时直接 `WAIT_HUMAN`。

| 字段 | 内容 | 备注 |
|---|---|---|
| `run_id` | 唯一运行编号 | 如 `20260716-001` |
| `master_plan` | 本轮唯一主计划路径 | 单一真相源，SELECT 优先级 1 |
| `objective` | 总目标，一句话 | 用户自然语言改造而成 |
| `terminal_evidence` | 哪些可核实证据**同时**满足才算 COMPLETE | 必须是命令/文件/清单可核实的，不能写"任务做完" |
| `included_stages` | 明确包含的阶段/plan 列表或选择规则 | 范围外的 stage 一律不自主加入 |
| `allowed_paths` | 可读写目录 | 默认仅当前 repo 内；D6 pilot = Mc-emoji |
| `allowed_actions` | 可用命令/网络/agent/team/workflow 范围 | |
| `forbidden_actions` | 删除、无备份覆盖、push、对外交付、工作区外读写等 | 与 4 红线第 1/2 条对齐 |
| `decision_policy` | 默认 > 历史成功率最高 > 最易回滚 | tie-break 顺序，SELECT/BUILD 选用 |
| `human_gates` | 用户显式保留的素材/成品验收门 | 命中即 `WAIT_HUMAN`，全托管也不跳 |
| `budgets` | 最大阶段数、最大返修次数、第 3 次失败熔断、最长运行时间 | goal condition 里的 `stop after N turns` 与此对齐 |
| `finalizer_policy` | mc-update/pin/session-new 在 full-loop 下的调用语义 | 见 §6 CHECKPOINT，D3/D4 落地 |

### 1.1 启动前权限预检（kickoff 必做，禁止等用户离开后碰权限框）

用户离开前，lead 必须一次性列出本轮预计触发的：工作区外路径、新目录/敏感目录、shell 命令族、network/MCP、Agent Team / Dynamic Workflow 启动、可能触发 ask/deny 的删除/覆盖/push/外部交付动作。

- 能预授权的窄动作由用户当场授权；
- 不能授权的写入台账 `pending_human`，**本轮不执行**；
- **禁止等用户离开后才碰权限弹窗**（夜间死锁红线，见 §8.1）。

### 1.2 today-core caller contract（指针）

today-loop 的 BUILD 阶段调 today-core 执行本阶段（见 §2 状态机 `RUNNING:BUILD → 调 today-core`），其**入参 schema 单源**在：
`Mc-emoji/[feature-05-loop-self-improvement]/output/plan11-phase1-contracts/today-core-caller-contract.md`

字段：`{caller_id, mode ∈ {normal,autopilot}, task, run_contract?, caller_context?}`。**★ 关键**：`mode` 字段贯穿 core 内部 §2 执行段 **+ §3.1 收尾段**（全托管"第四面"，母本提示框漏标、抽 core 时最易割裂的坑）。core 自己不问 mode，由 caller 提前进 core（today 跑 §1 前置门拿到、today-loop 从 Run Contract 冻结）。改 schema 只改那份契约文档。

---

## 2. 状态机（source of truth = plan11 §6，本表是其判据化）

> **★ 关键守卫标注（Phase 0 §6 F3 发现的文档清晰度缺口，本条补齐）**：
> 下表是**无状态骨架**——`RUNNING:SELF_CHECK fail -> REWORK` 是通用迁移。现行规则规定：同一任务/方案前两次失败进入 REWORK，第 3 次失败立即 HALTED，不试第 4 次。**纯迁移表表达不了“基于 `consecutive_failures` 计数的有状态守卫”**。
>
> 所以读这张表时必须同步读 §3 的**第 3 次失败熔断守卫**：`consecutive_failures >= 3` 时，`SELF_CHECK fail` 改迁 `HALTED`（而非 `REWORK`），由 `autopilot_failcount.ps1` 确定性计数层兜底。**状态机表本身只表达无状态骨架，计数守卫不靠迁移表自足。**

| 当前态 | 事件 / 动作 | 下一态 | 守卫 / 备注 |
|---|---|---|---|
| `INIT` | 读主计划、冻结 Run Contract、检查前提和权限 | `RUNNING:SELECT` / `WAIT_HUMAN` | 前提/权限不过 → WAIT_HUMAN |
| `RUNNING:SELECT` | 选下一个未完成且依赖已满足的阶段 | `RUNNING:PREFLIGHT` / `COMPLETE` | 无 pending → COMPLETE；**每 turn 开头必回读台账 + 复述状态进对话**（§5 compact 韧性） |
| `RUNNING:PREFLIGHT` | 路径、权限、备份、成功标准预检 | `RUNNING:BUILD` / `WAIT_HUMAN` | 路径/动作不在 Run Contract → `out_of_scope` → WAIT_HUMAN（§7 权限越界） |
| `RUNNING:BUILD` | 调 today-core 执行本阶段 | `RUNNING:SELF_CHECK` / `REWORK` / `HALTED` | 命中红线 → HALTED |
| `RUNNING:SELF_CHECK` | 结构性 + 任务专属验收 | `RUNNING:JURY` / `REWORK` | **fail 时查 `consecutive_failures`：≥3 → HALTED（守卫），<3 → REWORK**（§3） |
| `RUNNING:JURY` | mc-expert 独立陪审 | `RUNNING:CHECKPOINT` / `REWORK` / `WAIT_HUMAN` | 无 verdict → WAIT_HUMAN（§8.2，不得冒充 PASS） |
| `REWORK` | 按 issue 清单返修，重新 Build | `RUNNING:SELF_CHECK` / `HALTED` | 前两次失败均可返修；计数到 3 即 HALTED |
| `RUNNING:CHECKPOINT` | 更新台账，跑 full-loop 版收尾固化 | `RUNNING:SELECT` | completed_stages 追加本阶段；重入幂等（§4） |
| `WAIT_HUMAN` | 落盘卡点/待判项，不再自动动作 | 终态，等用户恢复 | 走「不执行 + 落盘 + 上报」，**不弹阻塞框** |
| `HALTED` | 同一任务/方案第 3 次失败 / 红线 / 不可恢复错误 | 终态，等用户恢复 | 绝不试第 4 次 |
| `COMPLETE` | 总证据全过，生成最终报告 | 终态 | terminal_evidence 全满足 |

### 2.1 SELECT：谁决定"下一 plan"（优先级）

1. 主计划显式写的依赖与下一步。
2. 台账中 `next_stage`。
3. `STATE.md` 当前主线指向。
4. 都没有：planner 提出候选，mc-expert 陪审，按 `decision_policy` 选最易回滚项。

候选意味着**扩大 Run Contract** → 不能自主加入 → `WAIT_HUMAN`。

### 2.2 PREFLIGHT：每 plan 开工前的机械三问

1. 成功标准能否被命令/文件/清单核实？不能则先补验收契约。
2. 所需路径与动作都在 Run Contract `allowed_paths` / `allowed_actions` 内吗？不在则停（`out_of_scope`）。
3. 覆写型操作是否已有备份/幂等策略？没有则先补，不能补则停。

---

## 3. 第 3 次失败熔断守卫（有状态，靠 `autopilot_failcount.ps1` 兜底）

> 这是 §2 状态机表**表达不了**的部分（Phase 0 §6 F3 抓到的文档清晰度缺口）。状态机表是无状态骨架，“同一任务/方案第 3 次失败熔断”是基于计数的有状态守卫，必须单列。

**为什么用脚本而非自记**：阈值计数不能靠 Claude 自己记——context 压缩会丢计数、"再试一次"倾向会越过阈值。确定性交给计数文件 + 固定脚本，Claude 只负责"认这次成/败"。

**脚本**（复用 today 母本 §3.2 既有层，不新造）：
```
pwsh -File "$env:USERPROFILE\.claude\commands\autopilot_failcount.ps1" -Mode <reset|fail|status>
```

**判据**：
- 完整 loop 开跑 **先 `-Mode reset` 清零**（`consecutive_failures = 0`）。
- 每个 `RUNNING:SELF_CHECK` 判定后：这步**确实失败** → 跑 `-Mode fail`；**确实成功** → 跑 `-Mode reset`（成功即断 streak）。成/败是语义判断，不是每个微动作都记。
- 脚本累计达 3 时输出 `AUTOPILOT_STOP`（带 🛑）并退出码 2。
- **见到 `AUTOPILOT_STOP` 或退出码 2，立即 HALTED，把现状 + 卡点交用户，不得再试第 4 次**——要不要继续不由 loop 判断。

**与状态机表的关系（一句话）**：状态机表 `SELF_CHECK fail -> REWORK` 是“`consecutive_failures < 3`”时的迁移；`≥ 3` 时改迁 `HALTED`，这个分支由本守卫的计数结果决定，迁移表本身不重复表达。

**阳性对照**：旧 Phase 0 曾对 2/2 阈值做过实测，该旧阈值已被 2026-09-04 用户决策取代，不再作为现行放行证据。当前必须重新验证 `autopilot_failcount.ps1` 的 1/3、2/3 均继续，3/3 输出 `AUTOPILOT_STOP` 且退出码 2，并确认绝不试第 4 次。

---

## 4. 台账 schema（`today-loop-state.md` · 唯一运行状态）

### 4.1 落点

`<repo>/.claude/today-loop-state.md`（首轮 pilot 用 repo 本地单文件）。

- 跟 repo 走，不依赖单一 session；
- 不污染业务 `STATE.md`（`STATE.md` 只在主线/里程碑变化时更新，不充当 run-time 日志）；
- 人能直接读，后续窄 Stop hook 也能用正则读 `status`；
- **只有真实 run 启动时才创建，不预建空 runtime 目录**。

### 4.2 最小 schema（YAML front-matter + 正文四块）

```yaml
---
run_id: 20260716-001
status: INIT  # INIT | RUNNING:SELECT | RUNNING:PREFLIGHT | RUNNING:BUILD | RUNNING:SELF_CHECK | RUNNING:JURY | REWORK | RUNNING:CHECKPOINT | WAIT_HUMAN | HALTED | COMPLETE
master_plan: "..."
current_stage: "..."
next_stage: "..."
stage_attempt: 0
consecutive_failures: 0
completed_stages: []
pending_human: []
last_evidence: []
last_jury_verdict: ""
last_checkpoint_at: ""
schema_version: 1
---
```

正文只保留四块：
1. **冻结的 Run Contract 摘要**（从 §1 授权包摘 key 字段，不全抄）。
2. **当前阶段与下一步**（current_stage / next_stage + 一句说明）。
3. **自主裁决清单**（每条：决策点 / 候选 / 选了哪个 / 依据 / 置信度——全托管放权的对价是留痕浮到台账）。
4. **append-only 阶段日志**（只追加，不改历史条目）：时间、输入、产物路径、检查结果、陪审 verdict、状态迁移。

### 4.3 写入纪律

- 状态迁移前**先写证据**，再改 `status` / `current_stage`。
- 同一阶段重入时**先查 `completed_stages` 和产物证据**；已 PASS 就不重复执行（重入幂等，§4.4）。
- 不把大段 agent 回传塞进台账，只存**产物路径 + 摘要 + verdict**。
- 每次改台账后**立即回读关键字段**，防半写/格式漂移（与 §5 schema 校验配套）。

### 4.4 重入幂等判据

台账重入（compact 后 / session resume / goal 续轮）时，按以下顺序判定，**已 PASS 的阶段绝不重复执行**：

1. 读 `status`：若已是三终态（`COMPLETE` / `WAIT_HUMAN` / `HALTED`），loop 结束，不动。
2. 读 `current_stage` + `completed_stages`：若 `current_stage` 已在 `completed_stages`，说明上轮已 PASS 但未推进 → 直接进 SELECT 选下一阶段，不重跑。
3. 若 `current_stage` 不在 `completed_stages`：看 `last_evidence` 判断上轮 BUILD 是否已产出未验收的产物 → 有则直接进 SELF_CHECK，无则从 BUILD 重来（重算 `stage_attempt`）。
4. `stage_attempt` / `consecutive_failures` 保留上次值（不因重入清零，否则第 3 次失败熔断守卫失效）。

---

## 5. ★ compact 韧性（Phase 0 §9 发现的真隐患，本条是其判据化）

> **隐患**：auto-compact 是 Claude Code 内建默认行为（接近上下文上限自动摘要老对话，不需配置）。`/goal` evaluator **只看对话已浮出的证据、不调工具不读台账文件**（官方 `/goal` 文档原话）。若关键状态（当前阶段 / 上轮 verdict / Run Contract 边界）被 compact 压成模糊摘要，evaluator 可能误判完成（早停）或卡住。

**对策三层**（plan §12 风险表 + Phase 1/3/5 待办）：

1. **状态写文件台账**（`today-loop-state.md`，文件不被 compact）——§4 已落。
2. **★ 每 turn SELECT 开头必回读台账 + 把当前阶段 / 上轮 verdict / Run Contract 摘要复述进对话**——让 compact 压掉老对话后，新对话仍有新鲜证据，evaluator 有据可判。**本条是判据**，Phase 3 SELECT 阶段落实现侧。
3. **Phase 5 Pilot B 夜间故意造一次 compact**（跑足多轮撑满上下文）做韧性阳性对照——验 compact 后 goal 不误判、台账恢复正常。若 compact 后状态丢失/误判，回 Phase 1/3 加固。

**判据（每 turn 必做的"复述进对话"最小集）**：
- 当前 `run_id` + `status` + `current_stage`；
- 上轮 `last_jury_verdict`（或 SELF_CHECK 结果）；
- Run Contract 的 `objective` + `allowed_paths` 一行摘要 + `human_gates`（防 compact 后忘了边界）；
- `consecutive_failures` 当前值（防 compact 后丢三次失败计数——与 §3 计数守卫互为冗余：脚本计数 + 对话复述双保险）。

**另注独立 bug**：GitHub issue #66144 反映 auto-compact 偶发"到 100% 不触发"——与 compact 韧性是两个独立问题，Phase 5 pilot 时一并盯。

---

## 6. CHECKPOINT：完整 loop 里的收尾三段（仍引 `收尾loop判据.md`）

CHECKPOINT 阶段跑 `mc-update → pin → session-new`，但调整 caller 语义（D3/D4 落地）：

### mc-update
- 继续执行频次闸 + 去重闸。
- **项目 repo 内候选**：经两道闸 + mc-expert 后可按深度授权落地，全部浮到自主裁决清单。
- **user-scope skill / 中央 KB / 其他 repo / `~/.claude`**：只落 proposal / `pending_human`，**不在无人值守过程中触发工作区外权限框**（D4 边界）。

### pin
- 完全复用 `收尾loop判据.md`（PIN/DROP 判据、方案 a 去重、掉线降级、陪审 spawn 五要素）；无迹象静默跳。
- 当前 pilot 在 Mc-emoji 内可正常落中央 sink；推广到别的 repo 前，必须单独解决工作区外写权限，不可假设已授权。

### session-new（D3：新增 full-loop checkpoint 调用语义）
- **每 plan PASS**：仍跑第 0 步主线回顾，但已有 master plan 时**只更新台账 / 状态指针，不重复新建同义 plan**。
- **context 明显接近上限 / HALTED / WAIT_HUMAN / 总任务 COMPLETE**：才跑现有完整 handoff 语义，生成冷启动自足 plan。
- 手工 `/session-new` 行为保持不变。

---

## 7. 权限越界判据（PREFLIGHT `out_of_scope` → WAIT_HUMAN）

> Phase 0 §7 阳性对照设计的判据化。状态机迁移路径已由 Phase 0 探针 F4 验证存在；本条定义"什么算一次越界"。

**判越界（PREFLIGHT 命中即 `out_of_scope` → WAIT_HUMAN）**：stage 的目标路径 / 动作 / 交付对象**任一**不在 Run Contract 的 `allowed_paths` / `allowed_actions` / `included_stages` 内。

**阳性判据（探针有效的证据，对照"通过"必须同时满足）**：
1. today-loop **没有**对那条未授权路径发起任何实际读写命令（不发 Read/Edit/Write/Bash 碰它）。
2. 台账 `status` 迁到 `WAIT_HUMAN`，`pending_human` 记录了那条越界路径 + 原因。
3. **没有**阻塞式权限框被触发（§8.1：走「不发命令 + 落盘 + 上报」，不是「发了命令等用户点拒绝」）。

**阴性判据（对照失败 = 探针无效，"零越权"结论全作废、回炉）**：
- today-loop 对未授权路径**发起了**命令（哪怕被 guard hook 拦下）——说明 PREFLIGHT 没在命令前拦住；
- `status` 没迁 WAIT_HUMAN、继续往下跑；
- 弹了权限框（说明是"先发命令再被拦"，不是"PREFLIGHT 主动判停"）。

**运行时执行**：Phase 3 today-loop 实现后先跑本阳性对照，过了才进 Phase 5；Phase 5 Pilot D 故障注入剧本含"未授权路径 → WAIT_HUMAN，确认不弹死等框"。

---

## 8. 安全模型

### 8.1 四条红线不变（命中即停）

1. 销毁性 / 不可逆操作（多文件删除、无备份覆盖）。
2. 对外交付物 / Ldterm 明文合规。
3. 同一任务/方案第 3 次失败熔断（§3 计数守卫）。
4. 推翻 KB `decisions/` 已封决策。

**命中后走**：不执行 → 落盘证据与待人工项 → 状态改 `WAIT_HUMAN` / `HALTED` → 结束 goal。**禁止靠会死等的权限框表达"我停了"**（夜间死锁：弹了会死等缺席用户 + 死锁后台 agent）。

### 8.2 完整 loop 专属硬线

- Run Contract 之外的路径 / 动作 / 交付对象 = 范围扩张，必须停（§7）。
- **陪审无 verdict = 不得 PASS**（mc-expert 零正文 / 连接中断：重试 1 次；仍失败 → WAIT_HUMAN，阶段不能在没有 verdict 时冒充 PASS）。
- **自检无证据 = 不得 PASS**（没有 evidence 的"已完成"不能送陪审）。
- **台账写入失败或 schema 读不回 = 不得继续下一阶段**（§9 schema 校验）。
- team / workflow 子执行体不能改台账、不能替 lead 扩大 scope。
- 不因 `/goal` evaluator 说"完成"就越过业务检查；**业务台账终态优先**于 goal evaluator 判断。

### 8.3 权限策略

继续使用方案 A（几乎全通 + 删除/覆盖守卫）。**不切 `bypassPermissions`**。Claude 原生 auto mode 虽适合长任务，但它是概率 classifier，不作为本 plan 前提。

---

## 9. ★ 台账 schema 校验步骤（Phase 0 §8.2 留的待补条，本条补齐）

> §8.2 规定"台账 schema 读不回 = 不得继续下一阶段"。本条定义"怎么校验、读不回怎么办"。

**每次读台账后、做状态迁移前，必跑这 4 步校验**（fail-loud，校验不过不得继续）：

1. **YAML front-matter 可解析**：`status` / `run_id` / `current_stage` / `consecutive_failures` / `completed_stages` 五个必填字段都在且类型对（`status` 是枚举值之一、`completed_stages` 是列表、`consecutive_failures` 是非负整数）。
2. **`status` 是合法态**：落在 §2 状态机表的合法状态集合内（防半写残留如 `RUNNING:` 空尾）。
3. **`current_stage` 与 `completed_stages` 一致**：若 `current_stage ∈ completed_stages` 且 `status` 不是三终态，说明台账自相矛盾（上轮已 PASS 却没推进）→ 进 SELECT 推进，不重跑（§4.4 重入幂等）。
4. **回读校验**：改完台账立即重读一次关键字段，确认写入成功（防半写 / 格式漂移）。

**校验不过的处理**：
- 可自愈（如仅 `next_stage` 空）→ SELECT 按 §2.1 优先级重算，补上后继续；
- 不可自愈（如 `status` 非法、YAML 解析失败）→ `WAIT_HUMAN`，落盘原始残留 + 报错信息，不硬继续。

**Phase 6 加固位**：状态台账格式漂移多次出现 → 加一个只校验 schema 的小脚本（非外层 orchestrator，只校验不控制流）。

---

## 10. 每阶段 PASS / REWORK / WAIT_HUMAN 判据汇总

> 一张速查表。每阶段的"进/退"判据，供 today-loop 实现侧和 mc-expert 陪审对齐口径。

| 阶段 | PASS（进下一） | REWORK（返修） | WAIT_HUMAN / HALTED（停） |
|---|---|---|---|
| SELECT | 有 pending 且依赖满足 → PREFLIGHT | — | 候选扩大 Run Contract → WAIT_HUMAN |
| PREFLIGHT | 路径/权限/备份/成功标准全过 → BUILD | — | `out_of_scope` / 无法补备份 → WAIT_HUMAN（§7） |
| BUILD | 产物产出 → SELF_CHECK | — | 命中红线 → HALTED |
| SELF_CHECK | 结构性 + 任务专属 + 范围三检全过、有证据 → JURY | 第 1/2 次 fail 且 `consecutive_failures < 3` → REWORK | `consecutive_failures ≥ 3` → HALTED（§3）；无证据不得 PASS（§8.2） |
| JURY | mc-expert 给 PASS 且证据齐 → CHECKPOINT | mc-expert 给 REWORK 且 `consecutive_failures < 3` → REWORK | mc-expert 给 WAIT_HUMAN / 命中 human_gate / 无 verdict（重试 1 次仍空）→ WAIT_HUMAN（§8.2） |
| CHECKPOINT | 台账更新 + 收尾三段跑完 → SELECT | — | schema 校验不过且不可自愈 → WAIT_HUMAN（§9） |

**陪审 spawn 五要素**（mc-expert 不继承 lead 历史，prompt 必带）：
1. 总主线和 Run Contract 摘要。
2. 当前阶段目标与成功标准。
3. 实际改动 / 产物路径。
4. 结构性 + 任务专属自检结果。
5. 自主裁决清单 + 明确要求判断 `PASS / REWORK / WAIT_HUMAN`，并**检查"是否偏离项目主线"**（7-12 扳机，补 mc-expert 盲区）。

---

## 11. kickoff 判据（§7.1 定稿，交互模式）

> 用户定稿：**不走 headless `-p`**，要交互、能看着跑。靠 `@文件` 把长内容移出命令行，绕开 bash 粘贴换行坑（Phase 0 E4 实测坐实）。

**kickoff 流程**（`/today-loop` 唯一入口）：
1. 用户在 `todays-task.md` 写自然语言任务描述。
2. 用户敲 `/today-loop`。
3. today-loop（Claude）做四件事：
   - 把自然语言改造成 **Run Contract**（§1 字段）。
   - **改写 `todays-task.md`** 成结构化（Run Contract 摘要 + 台账指针 + 阶段清单）。
   - 初始化 `today-loop-state.md` 台账（`status=RUNNING:SELECT`，先 `autopilot_failcount -Mode reset`）。
   - 给用户**一行短的 goal 指令**（长内容全在文件里）。
4. **人工确认门**：用户审核 Run Contract + goal 指令 → 口头说"执行"或直接粘该行。
5. 用户粘该行短 goal（交互）→ loop 启动。

**goal 指令模板**：
```text
/goal 按 @todays-task.md 的 Run Contract 推进，每 turn 回读 today-loop-state.md 台账，直到 status 进入 COMPLETE/WAIT_HUMAN/HALTED，或 stop after N turns
```

**goal condition 要点**（evaluator 只看对话、不读文件）：
- 终态认台账三态（COMPLETE / WAIT_HUMAN / HALTED）；
- 每 turn SELECT 回读台账 + 复述状态进对话（§5 compact 韧性）；
- 带 run budget（`stop after N turns`）；
- 业务 PASS 必须附确定性自检 + mc-expert verdict 浮到对话。

**机制边界（不糊弄）**：交互会话里 `/goal` 是 TUI 斜杠命令，Claude 无法用工具替用户"按下"它——所以"人工确认门"这一步用户最少要粘那一行短 goal（内容靠 `@文件` 不用粘长文本）。这是交互模式固有约束，用户已知情接受。

---

## 12. 演进意图（防把首跑期严格门冻成永久税）

- **陪审退出阀**：pin 识别陪审是 feature-05 补漏层首跑期姿态；完整 loop 的 JURY 陪审同理——Pilot A–D 验证 JURY 判据靠谱后，用户可拍板对低风险阶段走 speed-mode（结构性自检过即推进，省陪审成本）。对照 `feedback_speed_mode_after_proven_rounds`。
- **判据升 skill**：判据经 Pilot A–D 稳定后，本文件升级为完整 `skills/today-loop/SKILL.md` + `skills/today-core/SKILL.md`，届时 today-loop 入口引 skill 指针、改判据仍只改本处（Phase 2/3 落）。
- **Stop hook 叠加**：Phase 0 §4.2 坐实 `/goal` 本身就是 Stop hook。若 pilot 证明需要**确定性**完成判断（不依赖 evaluator），是在 `/goal` 之上**叠加**一个 project-scoped、marker-gated 的脚本型 Stop hook（读台账三终态、`status=RUNNING` 才阻止 stop），不是替代 `/goal`。Phase 6 按真实早停频率决定是否上。
