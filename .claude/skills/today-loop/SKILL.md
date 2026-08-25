---
name: today-loop
description: 一次审核启动后，Claude 连续完成多个低风险 plan，自检、独立陪审、返工、记账，只在真正需要人工时停。用户写自然语言任务到 todays-task.md，跑一次 /today-loop，审 Run Contract 和一行 /goal 指令后离开。
---

# `/today-loop` · live skill（plan05 Phase 3 装入母本）

> **状态**：plan05 Phase 3 已装入母本 `Mc-Expert-repo/.claude/skills/today-loop/`（2026-07-20），四账号 junction 共享生效。装 live 前预演报告 `phase3-dry-run.md` + mc-expert 陪审 PASS（高置信）。
> **复用不重建**：本 skill 的控制流、台账 schema、状态机脚本直接复用 plan05 Phase 0+1 已 PASS 产物（run-contract.md / state-schema.md / today-loop-state.ps1 / 15 fixture）。run-contract.md / state-schema.md 已于 2026-07-23 并进母本 `references/` 自足；脚本与本 SKILL.md 同目录自足内聚，调用照母本 today-core §2.2 pwsh 惯例（`$env:USERPROFILE\.claude\skills\today-loop\...`）。

---

## 1. 用户路径（用户体验）

1. 用户在 repo 根 `todays-task.md` 写下自然语言任务（可多 plan）。
2. 用户跑一次 `/today-loop`。
3. Claude 整理出 **Run Contract**（本轮做什么、允许改哪里、何时必须停）+ 冻结 `contract.json`/`plans.json` + 一行 `/goal <完成条件>` 启动指令。
4. 用户审核 Contract 和 `/goal` 指令，确认后粘贴该指令（**必须带 condition，见 §2 step6**），可离开或弱在场。
5. Claude 自动跑多 plan 直到 COMPLETE / HALTED / WAIT_HUMAN，写通俗汇总。

目标不是"不受控一直跑"，是"普通过程不打扰用户，真正越界才停"。

---

## 2. 启动段（Kickoff，跑 `/today-loop` 的第一个 turn）

按序：

1. **读任务**：读 repo 根 `todays-task.md`（读完即清空，遵守 AGENTS.md temp 类约定——本文件非 temp.md 但同样不应留作长期真相源；任务被冻结进 `plans.json` 后即可清空原稿）。
2. **输入充分性自检**（拆 plan 前必做，借 chop kickoff-gate 最小子集，不搬整套门禁）：读完 `todays-task.md` 后、拆 plan 前，对原始任务逐项核"在不在场"，缺哪项标为缺口——
   - 终态：做完长什么样（描述状态，不描述动作）→ 写进每个 plan 的 `done_when`（§3 冻结字段）。
   - 参照物：有没有标准样板（做好的同类产物/模板/目标格式）→ 写进 `reference`（可选）。
   - 红线：不可违反的约束（数量/命名/合规/不可改原件）→ 进 contract 的 `forbidden_actions`/`allowed_paths`。
   - 验收：最后会挑的毛病（结果属性，非动作清单）→ 融进 `done_when`。
   缺口处置（按 chop 三层，收进呈 Contract 那一步，不另开拷问往返）：事实层缺口（只有用户知道、inspect 也得不到）→ 在 step6 呈 Contract 时一并列出、请用户确认时一并补；不在 kickoff 另开一次 prose 追问（守"普通过程不打扰用户"主线）。可 inspect 的（现状/文件清单）→ 不问，直接写进 plan 让执行期盘点。裁量层 → 收敛成封闭拍板点放进 step6 的 Contract 呈现。
   **铁律**：最小子集，只借上面 4 项自检，不把 chop 八项门禁/三层分类/批量铁律整套搬进来（守 codex-overengineering-reflex）。`done_when` 缺失/空串/纯空白会被脚本 `init` 直接 reject（`PLAN_DONE_WHEN_MISSING`），故自检的"终态"项是硬前提不是软纪律。
3. **解析 plan**：把自然语言任务拆成有序、低风险、可回滚的 plan 列表，标注依赖。单轮默认 ≤ 3 plan（受 `contract.budgets.max_plans` 约束）。每个 plan 必须带 step2 自检出的 `done_when`（结果状态）+ `reference`（可选）。
4. **冻结输入**：生成 `contract.json`（目标、`allowed_paths`、`read_only_paths`、`forbidden_actions`、`human_gates`、`budgets`、`terminal_evidence`）和 `plans.json`（每个 plan 含 `id/title/depends_on/done_when/reference`）。所有路径 **repo-relative**，禁止绝对路径。
5. **初始化台账**：调脚本 `init`，把 contract/plans 的 SHA-256 写进 `state.json.frozen_inputs`（脚本对 `done_when` 做非空 fail-fast 校验）。
6. **呈给用户审**：用大白话复述 Contract（做什么 / 允许改哪 / 何时停 / 失败预算=2），附一行 **`/goal <完成条件>`** 指令。**停下等用户确认**——这是 kickoff 唯一的人工门。**若 step2 自检标出事实层缺口，在此 Contract 呈现时一并列出**，请用户确认时一并补。

kickoff 不得直接进 SELECT；必须等用户粘贴启动指令。

> **`/goal` 指令必须带 condition**（2026-07-23 按 /goal 官方文档重写，源首次实战裸输 `/goal` 报 "No goal set" + plan §16.1 一手核实官方 evaluator 行为）。`/goal` 是 Claude Code v2.1.139+ 内建 slash command（官方 `code.claude.com/docs/en/goal`），裸输只回提示语不启动；必须带**可判定的完成条件**。
>
> **condition 是自然语言，不是 `state=`/`status=` 字段协议**（官方原文通篇 0 处字段语法）。`/goal` 的 evaluator（默认 Haiku 小模型）**不读文件、不跑命令、不调用工具**——官方原文："It does not call tools, so it can only judge what Claude has already surfaced in the conversation." 故 evaluator 只看**对话里 Claude 复述了什么**，看不到 state.json 的字段。模板示例：
> ```
> /goal 所有 plan 已 passed（run 进入 complete），或 run 已进入 halted / wait_human 终态；该 status 已在本 turn §3.0 恢复句中复述
> ```
> **硬前提（condition 成立的必要条件）**：condition 能被 evaluator 判准，依赖 §3.0 每 turn 把 run status 复述进对话（恢复句）。不复述 → evaluator 看不到 status → 判不准 → 可能误判早停或永远判不满足。所以 §3.0 复述不是可选的韧性动作，是 condition 生效的前提。
> condition 必须含**前置门谓词**——只有"所有 plan passed"或"命中终态（halted/wait_human）"才判满足，**禁止写成会让 evaluator 在中间状态误判"已完成"的条件**（呼应 memory `today-loop-codex-exclusive-not-thin-adapter` 2026-07-20 补丁段第 3 条：防 `/goal` 压过人工验收门）。启动后 harness 每 turn 结束喂 evaluator 判 condition，不满足自动续轮，用户无需每 turn 回车。

---

## 3. 控制流（每个 `/goal` turn）

```
SELECT → PREFLIGHT → BUILD → SELF_CHECK → JURY → CHECKPOINT
```

### 3.0a 自主轴：autopilot 贯穿多 plan（深度授权 = today 全托管）

> 2026-07-23 加（plan 自主轴）。**today-loop 的核心目标：运行中途全程无弹窗**。任务进 today-loop 前**风险已由用户人工评估**（用户筛过、认定适合深度授权），故运行中本不该有需要中途拦的决策——以下纪律把这根 mode 在 today-loop 层显式贯穿一次。

today-loop 把 mode 钉死 autopilot，所以 today-core §1.1 门3 / §1.2 途中决策 / §2.1 收尾决策 / §2.2 两连败**四面全部走 autopilot 分支**，且这根 mode 贯穿多 plan（每个 plan 内部 + plan 之间都同纪律）。铁律：

- **中途零弹窗**：运行中（kickoff 之后、三终态之前）任何决策点——含**没有用户给定默认的拍板点、口径拿不准、要不要顺手改某处**——都**不弹 AskUserQuestion、不因 contract 的 human_gates 语义门自觉停**。先按共享 `review-contract-v2.md` 用 v2 六字段 envelope 调 `Task(mc-expert)`，固定 `REVIEW_PROFILE=HISTORY`，拿历史建议后**直接照办继续**；HISTORY 不抵扣命中增强触发器后的 fresh `ENHANCED_FINAL` 终审。
- **置信低/无先例也不升级用户**（today 深度授权语义，区别于 today-core normal 档的"无默认才停"）：mc-expert 给不回高置信，照样采纳它给的默认推荐（默认 > 成功率最高 > 最易回滚）继续，**不回头问用户**。把该裁决记进收尾「自主裁决」清单。
- **真硬依赖才转 WAIT_HUMAN**（四步顺序，codex 陪审第3点补强）：自主轴不等于"永不转 WAIT_HUMAN"。运行中遇到决策，按序尝试——
  1. 能 inspect / 盘点的自己查（现状、文件清单、现状参数）；
  2. contract 已给默认/约束的按 contract 走；
  3. 普通裁量（口径/方法/命名/范围内的取舍）自主按最高置信默认继续 + 攒收尾清单；
  4. **只有真硬依赖才转 WAIT_HUMAN**——判定三同时：①是只有用户掌握的专有事实（inspect 也得不到）；②无安全默认（任意默认都会猜造结果或改验收含义）；③阻断正确性（不解决就没法做出对的产物）。三同时调脚本 `wait-human` 写 handoff，让用户补这一个事实后新 session 续。
- **scope 收窄**（codex 陪审第2点①，不可被"可回滚"绕过）：顺手重构、扩 `allowed_paths`、改验收口径这类**扩大 scope 的动作 → 不执行、记进收尾建议**。需要扩 scope 才能完成的，转 WAIT_HUMAN（scope 扩张本质是"运行中新增权限硬依赖"，是真硬依赖四步中第4步的一种，run-contract 同样要求直接 `WAIT_HUMAN`）。mc-expert 是咨询证据、不是扩授权来源；"可回滚"不替代 contract scope。
- **唯一允许弹的窗 = kickoff**（§2 step6）。事实层缺口（只有用户知道、inspect 也得不到）一律收进 kickoff 呈 Contract 那一步一并列出、请用户一次性补；**中途不再为事实缺口弹任何窗**——能 inspect 的自己盘、有默认的按默认走，都攒到收尾。
- **自主 spawn subagent 是期望行为**（coder/mc-expert/Explorer），明确保留。
- **只有四类停**（与 today-core 一致）：脚本机械门（preflight 越界 / forbidden_action / human_gates 精确命中）、JURY 给 WAIT_HUMAN、四红线、两连败熔断（today-core §2.2 AUTOPILOT_STOP）。
- **`human_gates` 双重身份**（plan 升级C1，源实战频停根因）：
  - **脚本层**：preflight 只对 `ProposedAction` 字符串做**精确匹配**（`$s.human_gates -contains $ProposedAction`，today-loop-state.ps1 preflight-check）——只有提交的 action 名等于 human_gates 数组某项才机械转 WAIT_HUMAN（如 `delete`/`push` 这类动作名）。
  - **语义层**（`route-decision`/`batch-after-single-verify`/`scope-expansion` 这类概念）：**不在运行中途停下来问**，而是"这个决策我按最高置信选了 X"，记进收尾自主裁决清单。**语义门 = 留痕标记，不是中途阻塞**——脚本精确匹配不上语义概念（不会机械触发），故读到 contract 列了它，不代表"我在做这类决策就该停"。

> **auto-mode 承接（2026-07-23，§17）**：当前 Claude 已转 auto-mode——常规操作（读写改文件、跑脚本、调 subagent、commit、跑 fixture）默认静默放行；销毁性操作的中途拦截 = auto-mode classifier **概率层** + 四红线 halt 纪律（`feedback-no-rm-midflight`：B 模式中途不主动发 rm，攒收尾人工门），**无确定性硬门**（用户已知接受的权衡）。但因 contract `forbidden_actions` 已封掉 `delete/push/external-delivery`，且任务进 today-loop 前风险已人工评估——运行中本不该有需要中途拦的销毁性操作。故"中途全程无弹窗"是 **auto-mode 静默常规操作 + 用户预评估消化销毁性风险**两层前提保证下的合理预期，不是赌 classifier 不误判（§17.2）。**销毁性删除一律不中途自主发**（`feedback-no-rm-midflight`，auto-mode 下唯一剩下的防线）。

收尾汇报（自主裁决清单）= today-core §1.4 规范：每条「决策点 / 候选 / 选了哪个 / 依据(默认|成功率|易回滚) / 置信度」，显眼附在交付汇报，供用户一次性批量复盘。

> ⚠️ **诚实标注（非硬保证）**：以上是**行为纪律层**（软纪律）+ auto-mode 常规静默，不保证改完运行中一次窗都不弹——模型保守弹问是训练偏好、不是规则没写。真正的兜底是用户侧 contract 纪律（human_gates 只放机械动作名）+ 弱在场纠偏。

### 3.0 每轮恢复句（turn 开头必做）

每个 `/goal` turn 开头先调脚本 `show`，并在对话复述：

`run_id | run status | current plan | last verdict | consecutive failures | objective | allowed paths | human gates`

随后才允许 `select`。已 `passed` 的 plan 禁止重跑；有 `running` 恢复它；有未验收证据从 SELF_CHECK/JURY 续。**不凭聊天记忆猜阶段。**

> **复述句是 `/goal` condition 生效的硬前提**（2026-07-23 加，呼应 §2 step6）：`/goal` 的 evaluator 不读 state.json、只看对话——所以本 turn 必须把 `run status` 复述进对话，evaluator 才判得准 condition 是否满足（complete/halted/wait_human）。漏复述 = condition 判不准 = 可能误判早停或永不满足。

### 3.1 SELECT

调脚本 `select`：返回 active plan / 下一个 eligible plan / all-pass。一个 turn 最多 start 一个 plan。

### 3.2 PREFLIGHT（机械门，硬约束）

start 后调脚本 `preflight-check`，提交 repo-relative `TargetPath` 与 `ProposedAction`。脚本机械核对：

- target 在 `allowed_paths` 内、不在 `read_only_paths` 内
- 解析祖先 junction/symlink 真实目标，逃出 repo 即拒绝
- `ProposedAction` 不在 `forbidden_actions`
- 不命中 `human_gates`

没有 `preflight_passed` event 不得 advance 到 BUILD。越界由脚本直接转 `WAIT_HUMAN`，**不弹阻塞权限框**。

### 3.3 BUILD

调 `today-core`，caller context 固定 `caller_id=today-loop`。执行当前 plan 的实际工作。

### 3.4 SELF_CHECK

给出结构证据（产物存在、内容核验、首字节 magic 等）。证据不足不算 PASS。

### 3.5 JURY（独立 reviewer）

派 `mc-expert` 做独立 reviewer，输出 `PASS | REWORK | WAIT_HUMAN`：

- `PASS`：调脚本 `review-pass`（校验 verdict 文件、plan id 匹配、reviewer ≠ executor）→ 进 CHECKPOINT。
- `REWORK`：调脚本 `fail`（第一次）→ 自动返工一次。
- `WAIT_HUMAN`：调脚本 `wait-human`。
- reviewer 尚在跑或短轮询无结果 = `PENDING`（调 `pending-review`），**不计失败**；hard deadline 后仍无有效 verdict 才 `WAIT_HUMAN`。

执行者不能自己给自己盖章。

> **判 PASS 必须核对 `done_when`**（2026-07-23 加，源 plan 拆解轴）：reviewer 判 PASS 时，必须核对 plan 的 `done_when`（结果状态）是否满足——`done_when` 是 plan 级客观尺度，**缺它不得判 PASS**。`done_when` 描述"做完长什么样"（如"X 文件存在且首字节为 50 4B"），不是动作清单；透传在 `state.json.plans[].done_when`，reviewer 从 state 读。

### 3.6 CHECKPOINT

调脚本 `pass`（要求 reviewer PASS + 实际存在的 evidence 文件）→ plan=`passed`，连续失败清零，回 SELECT 接下一个。每个 plan 只做 checkpoint；切 context、HALTED、WAIT_HUMAN、COMPLETE 时才写完整 handoff。

---

## 4. 三终态（只有这三态允许 `/goal` 结束）

| 终态 | 条件 | 动作 |
|---|---|---|
| `COMPLETE` | 所有 plan `passed`，逐项确认 `terminal_evidence` 是 run dir 内实际存在文件（含 handoff） | 调 `complete`；写通俗汇总 |
| `WAIT_HUMAN` | 权限越界 / 显式人工门 / 无有效 reviewer verdict / schema 不可自愈 | 调 `wait-human`；写 handoff 说明：发生什么、已完成什么、为什么不能自续、用户下一步只需做什么 |
| `HALTED` | 两连败 / 四红线 / 不可恢复错误 | 调 `redline`（红线）或 `fail` 第二次；写 handoff |

checkpoint 不是 Goal 终态。

---

## 5. 失败与红线

- 第一次失败 → REWORK（自动返工一次）。
- 第二次连续失败 → HALTED，**禁止第三次**（脚本在状态机层拒绝）。
- 四红线（销毁性/对外明文/连失 2 次/推翻 KB 已封决策）命中即 `redline` → HALTED，落盘上报，不计普通失败。

---

## 6. 状态机脚本接口（复用 Phase 1 `today-loop-state.ps1`，与本 SKILL.md 同目录）

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\skills\today-loop\today-loop-state.ps1" `
  -Action <verb> -RunDir <run-dir> [其他参数]
```

> 路径写法照母本 today-core §2.2 pwsh 惯例（`$env:USERPROFILE\.claude\...`，四账号 junction 解析到同一物理脚本，换账号/换机都通）。脚本与本 SKILL.md 同目录自足内聚。

14 个 action（参数见脚本 param 块）：

| Action | 关键参数 | 用途 |
|---|---|---|
| `init` | PlanFile, ContractFile | 初始化 run，冻结 hash |
| `show` | — | 只读恢复句（不改状态） |
| `recover` | — | event-first 重放，从中断恢复 |
| `select` | — | 选下一个 eligible plan |
| `start` | PlanId | plan=running, attempts+1 |
| `preflight-check` | PlanId, TargetPath, ProposedAction | 机械边界门 |
| `advance` | PlanId, From | preflight→build→self_check→jury |
| `pending-review` | PlanId | reviewer 未返回=PENDING |
| `review-pass` | PlanId, Evidence | 校验 reviewer PASS 文件→checkpoint |
| `pass` | PlanId, Evidence | plan=passed，回 select |
| `fail` | PlanId, Reason | 第一次=rework；第二次=halted |
| `wait-human` | PlanId, Reason | 进 WAIT_HUMAN |
| `redline` | Reason | 红线→halted，清 current_plan |
| `complete` | — | 全 plan passed + 终态证据齐全→complete |

**写入纪律**：`state.json` 只由此脚本写，模型不得手改。每次迁移先 append `events.jsonl`（带连续 seq + 完整 state_after），再原子替换 state。event-first 可重放；缺号/坏行/state 超前一律 fail closed。

---

## 7. 上下文压缩 / 跨 session 恢复

> 2026-07-23 重写（plan 自主轴升级B）：auto-compact 优先，禁运行中途走 temp 接力。

- **auto-compact 优先**：context 接近上限时，依赖 Claude Code 内建 auto-compact（接近上限自动摘要老对话，不需配置）自动压缩续轮。台账自包含——compact 后每个 turn 开头照 §3.0 调 `show` 读 contract + 台账恢复（running plan 按 phase 续、rework 重新 start、passed 跳过），**不凭 compact 后的记忆猜阶段**。
- **禁止运行中途走 temp 接力**：kickoff 之后、三终态之前的运行中途，**不得走 temp-command 写 temp.md 让用户开新 session 接力**——那会打断「一次审核启动后无人值守连续跑」的定位（§3.0a 自主轴）。context 压力靠 auto-compact 化解，不靠人工接力。
- **三终态才写 handoff**（合法的跨 session 冷启动入口）：COMPLETE / HALTED / WAIT_HUMAN 时写完整 handoff 让新 session 接，这是允许的；区别于「运行中途 temp 接力」。
- 每个可变动作前脚本重算 frozen hash；contract/plans 漂移即拒绝。
- context 压缩或新 turn 只读 contract + 台账即可恢复：running plan 按 `phase` 续；rework 重新 start；passed 跳过。
- HALTED/WAIT_HUMAN 的 handoff 足以让新 session 冷启动。
- **跨 session 恢复仅在真实 pilot（Phase 5）PASS 后才宣称支持**；候选阶段不承诺。
- ⚠️ **已知风险**（Phase 5 Pilot B 未验）：auto-compact 是内建默认行为，但「glm-5.2 跑 today-loop 长 loop 真触发 compact 且 /goal evaluator 不在中间状态误判早停」尚未运行时阳性对照。对策（呼应 §3.0 复述前提）：每个 turn 开头把恢复句复述进对话，防 compact 后 evaluator 丢上下文误判。Pilot B 验通前不强求单轮长 session 连续多 plan，靠 `max_plans` 控单轮 plan 数兜底。
- **auto-compact 确认不触发时的降级**：若实测 auto-compact 偶发不触发（已知 issue），run 转 WAIT_HUMAN 终态写 handoff，**不硬撑、不留 temp 接力退路**。

---

## 8. 边界与禁区（承 plan05 §4）

**不做**：不改 settings/hook、不自动 push、不对外交付、不操作 Office 图形界面、不改 feature06 封盘文件、不在无人值守中修改正式 memory 或其他 repo。

**四红线**：销毁性/不可逆、对外明文合规、连失 2 次、推翻 KB `decisions/` 已封决策——命中即 halt 落盘。

---

## 9. 冷启动入口（新 session 执行 today-loop 前读）

0. **环境前置（kickoff 前核，2026-07-25 加）**：目标 repo **必须是 git 仓库**。状态机脚本 `RepoRoot`（`today-loop-state.ps1`）硬依赖 `git rev-parse --show-toplevel` 定位 repo 根——非 git repo 跑 `init` 直接 `REPO_ROOT_NOT_FOUND`，整个 loop 起不来。
   - **非 git repo 怎么办**：与用户对齐后 `git init`（用户拍板）。**纯文件归档类 repo 要 git init，必须先把全部源资料/二进制加入 `.gitignore`**——git 只追踪过程文件（md/py/json/脚本等），源资料（Office/PDF/图片/3D 等，常含 DLP 受控资产）严禁进版本库。Wu Prj 实证：`git init` + 全源资料扩展名 ignore（`.xlsx .pdf .png .pptx .ai .3dm ...`）后，git 只追踪 ~494 个过程文件、零源资料进库。
   - 注意：用户可能对"工作电脑 git init 会不会外泄"有顾虑——git 是本地版本控制，**不 push 就不联网外泄**，与 DLP 透明加密是两套独立机制、不冲突；但若误 `git add .` 后 push 明文源资料才外泄，故 ignore 规则必须先写好。

1. repo `AGENTS.md` 启动链 + `STATE.md`。
2. plan05 §0、§4、§5、§6、§7。
3. Run Contract / state schema 判据：见同目录 `references/run-contract.md`、`references/state-schema.md`（2026-07-23 并进母本自足，feature07 output 原件已冻结留档）。
4. Phase 1 fixture 证据：`fixtures/_runs/20260720-081817450/`（15/15 PASS）。
