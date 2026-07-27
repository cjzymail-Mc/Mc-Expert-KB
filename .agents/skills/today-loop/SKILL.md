---
name: today-loop
description: "在 Codex Goal 内按一次性 Run Contract 自动顺序执行多个低风险 plan，使用持久台账处理依赖、跨-plan checkpoint、独立陪审、两连败和 COMPLETE/HALTED/WAIT_HUMAN 终态。用于用户显式要求多-plan 无人值守推进；仅手工 $today-loop 触发。"
---

# `$today-loop`

把 P3 已验通的 `$today + Goal` 当单-plan 发动机；本 skill 只负责自动选择下一个 plan、持久记账和总终态，不复制 `$today` 或 Claude `today-core` 正文。

## 0. PRE-GO 任务准备与硬门

### 0.1 PRE-GO：拆解并冻结输入

在普通非 Goal 会话先完成任务准备；此阶段不执行 plan。拆 plan 前逐项核对：

1. **终态**：全部完成后是什么结果状态，不写操作步骤。
2. **参照物**：是否有模板、同类成品、格式规范或目标样例。
3. **红线**：不可改原件、禁止动作、范围、数量、命名与合规要求。
4. **验收**：用户最终按哪些结果属性判断完成。

能从 repo 只读检查得到的事实自行检查；有项目默认值的裁量写入草案并在审核摘要中标明；只有用户知道且会改变范围或完成标准的缺口，集中到 PRE-GO 审核一次问清。不要把普通实现细节升级成用户问题。

拆分时默认最多 **2 个 plan**，并受 contract `max_plans` 硬预算限制；只有用户在 PRE-GO 明确批准更高预算时才使用更大值。每个 plan 是一个可独立验收的结果，不按文件数拆，也不机械拆成“调研/设计/实现/测试/汇报”。依赖只表达“前项结果是后项输入”；首件验证与后续批量可在用户明确需要时拆成两个 plan。

每个冻结 plan 必须有：`id/title/depends_on/done_when`，可选 `reference`。`done_when` 描述“做完是什么状态”，不得写成动作清单；`reference` 是 repo-relative 参照路径或样例描述。

PRE-GO 写盘只允许在本轮明确指定的 repo-local run 准备目录内创建：

- `contract.json`
- `plans.json`
- `authorization-pack.json`

PRE-GO 禁止写 `state.json`、`events.jsonl`、reset/finalizer 记录和实际任务产物。`allowed_paths` 只是待批准的执行期授权范围；只有 active Goal + 下述三令牌校验通过后，才允许 `init`、运行台账写入和任务执行。将三份冻结草案用大白话呈给用户一次性审核，审核通过后再给出 Goal 启动入口。

### 0.2 active Goal 必读与硬门

1. 读 `AGENTS.md` 启动链、`STATE.md`、`$env:USERPROFILE/.agents/skills/_mc-common/codex-runtime-bindings.md`。
2. 读 [references/run-contract.md](references/run-contract.md)，校验 Run Contract 与它引用的 authorization pack，并计算 pack SHA-256。
3. 读 `$env:USERPROFILE/.agents/skills/today/SKILL.md`，把它作为每个 plan 的执行合同；不要假设存在 skill-to-skill RPC。
4. 调权威 Goal 状态工具。只有 active Goal 且初始 objective 同时含**恰好一个** `TODAY_LOOP_MODE=2`、**恰好一个** `TODAY_MODE=2` 与**恰好一个**匹配 pack 的 `UNATTENDED_AUTH_SHA256=<64位小写哈希>`，才能写 run/reset/任务文件。
5. `/goal` 创建后会立即执行；禁止“两条消息：先只创建 Goal、再显式开工”。Goal 不 active、令牌缺失/重复/冲突、授权哈希不符或工具不可用：零运行台账/任务写入，回报 `CONTRACT_INVALID`、`AUTHORIZATION_INVALID` 或 `BLOCKED_REVIEWER_UNAVAILABLE` 后停止。

P3 已证明长时续接与 compaction recovery；不要为了启动本 skill 重跑 P3 历史 fixture。

## 1. 初始化

Run Contract 和 plan list 必须是 repo 内文件，schema 见 reference。运行：

```powershell
pwsh -NoProfile -File (Join-Path $env:USERPROFILE '.agents\skills\today-loop\scripts\today-loop-state.ps1') `
  -Action init -RunDir '<repo内run目录>' -PlanFile '<plans.json>' -ContractFile '<contract.json>'
```

`state.json` 已存在时禁止重新 init；先 `-Action show` 回读续接。每个 turn 的第一项动作都是 show/select，不凭对话记忆猜当前 plan。

## 2. 每个 Goal turn

1. `show`：读取 run 状态；`complete/halted/wait_human` 走终态，不执行 plan。
2. `select`：若已有 running plan 就续它；否则取第一个依赖已 PASS 的 `rework/pending` plan。
3. `start`：把选中 plan 标为 running。一个 turn 最多启动一个 plan。
4. **PREFLIGHT**：核对 active plan 的目标、allowed_paths、禁止动作、预算、human_gates 与 authorization pack。正常路径只用已批准命令类别；越界不申请权限。可延后项写 `pending-human` 后继续独立工作，硬依赖转 `wait-human`。
5. **DISPATCH**：按已读取的 `$today` 合同执行 active plan，显式声明 `caller_id=today-loop`；task 取 state 中 active plan 的 `title + done_when + reference + depends_on`，不取根 `todays-task.md`。SELF_CHECK 证据必须对应 `done_when` 的结果状态，不能用“动作已执行”替代结果成立。
6. `$today` 实际 reset 后立即 `record-reset`；重复记录失败即停。PASS plan 的单-plan finalizer 完成后立即 `record-finalizer`；总 loop 不再追加第二次 finalizer。REWORK/HALTED/WAIT_HUMAN 可在完整 finalizer 前终止，按共同 binding 只做必要 handoff。
7. 独立陪审按共同 binding 路由。reviewer 判 PASS 前必须明确回答当前 `done_when` 是否满足及对应证据；不得用动作完成代替结果完成。native child 的 `No agents completed yet`/active wait timeout 只记 `PENDING`，每 20–30 秒轮询且同一 checkpoint 只保留一个 active reviewer；达到 600 秒 hard deadline 或其他终态 transport failure 才计一次失败。仅当冻结合同与 authorization pack 明确批准时，可 fresh 切换到只读 isolated subprocess；两次终态失败才 `wait-human`。
8. verdict：
   - PASS：带 evidence 调 `pass`，本 turn 结束，让 Goal 自动续轮。
   - REWORK：调 `fail`；第一次回到 rework，第二次脚本写 HALTED、输出 `AUTOPILOT_STOP` 并退出 2；不得第三次。
   - WAIT_HUMAN/四红线：调 `wait-human`，不继续选 plan。
9. 所有 plan PASS 后调 `complete`；只有 state=`complete` 才允许把 Goal 标 complete。

## 3. Goal 与终态

- `running`：本 turn checkpoint 后正常结束，Goal objective 未完成，等待自动续轮。
- `complete`：读取最终 state/events，确认无 running/pending/rework 后标 Goal complete。
- `halted`/`wait_human`：零写入重复回读并报告；仅按当前 Goal 产品合同允许的 blocked 阈值处理，不能为了结束 Goal 篡改台账或继续第三次。

## 4. 所有权与边界

- `$today-loop`：SELECT、依赖、跨-plan checkpoint、总终态。
- `$today`：单-plan BUILD、自检、陪审、reset 和 finalizer。
- 台账脚本：计数与状态迁移；模型不得手改 `state.json/events.jsonl`。
- 首件只允许 repo 内、低风险、可回滚、顺序 plan；禁止 push、对外交付、外部母本/全局 config/hook/正式 memory 写入。Computer Use、Office GUI 与第三方交互动作不得在无人值守 Goal 内发起。
- 不承诺 Scheduled、崩溃恢复、网络中断同 run 恢复或 Claude 适配。

