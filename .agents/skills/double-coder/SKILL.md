---
name: double-coder
description: 让 Codex 在当前 Git repo 中担任双窗口接力 coder。用户显式调用 $double-coder 后按公共 JSON 配置创建 active Goal，采用深度授权 B 模式执行或恢复任务；可搭配 Claude 或 Codex 的 double-planner。
---

# `$double-coder`

先完整读取 repo 启动链和 `$env:USERPROFILE\.agents\double-session-common\protocol.md`，然后严格执行其中“coder 唯一流程”。公共核心缺失时 fail-loud；不得复制协议、回退 Claude skill 目录或手改 `.copilot-state.json`。

## Codex 机制适配

- 状态脚本固定为 `$env:USERPROFILE\.agents\double-session-common\double-session-state.ps1`，角色固定为 `coder`。
- 除 `status/stop` 外，启动或恢复调度前先调用状态脚本 `-Action Config`，解析唯一配置并计算 `coder_wait_ms = coder_interval_seconds * 1000`；配置读取或校验失败即停，不得使用 skill 内默认值。`max_budget_seconds` 由状态脚本在新 run/新 segment 时读取。
- 使用 active Goal 保持续轮。若已有无关 unfinished Goal，停止并报告，不得覆盖或先调用 `Init`。
- Goal objective 必须写明公共 coder 流程、每次先查 state、未轮到时按本次固化的 `coder_wait_ms` 原生等待、班次暂停或终态即结束；`running + turn=planner` 和 state 连续多轮不变都是正常监控状态，绝不能仅据此调用 `update_goal(blocked)` 或结束 Goal。不得用 shell 常驻循环、sleep、后台进程代替。
- 命中公共陪审扳机时，先完整读取 `$env:USERPROFILE\.agents\skills\_mc-common\codex-runtime-bindings.md` 与 `$env:USERPROFILE\.codex\agents\mc-expert.toml`，再用 native custom agent `mc-expert`、`fork_turns=none`、四字段合同做一次性只读陪审。无 native surface 或调用失败也不得 `WaitHuman`，须把证据交给 planner；不得用 `codex exec` 冒充。
- 自主接力中不得请求普通用户决策。普通可逆事项按公共协议默认顺序自走并记录；权限动作后置，真正人工硬门非阻塞停机。

## 启动 Goal

0. 解析 `状态/继续/返工/通过/取消/接管`（兼容 `status/resume/stop/takeover`）。既有本角色 session 的短命令内部使用当前批准编号；全新 session 必须显式 `resume <decision> <human_approval_id>`。裸“继续”不得猜 run 或 takeover；终态拒绝复活。全新 session 发现遗留 `wait_human` 时先显示三选一；只有用户本轮明确选择“取消旧任务并强制初始化”才调用 `ForceInit`。
1. 调 `Config` 并固化本次 `coder_wait_ms`；确认无冲突 Goal，固化 repo 绝对路径并生成唯一 `worker_token`。新 run 先调 `Init`（只传 `ExpectedRepo + WorkerToken`）取得 `run_id`；已有 run/人工恢复从 state 取得并固化 `run_id`。然后创建 active Goal，objective 携带三项绑定与 `coder_wait_ms`；后续每个状态动作都传 `ExpectedRepo / ExpectedRunId / WorkerToken`。
2. 未过期的 running 只恢复，`paused_budget` 原位开启下一班次；普通自动恢复遇同角色有效租约时报 `WORKER_ACTIVE`。token 丢失可等待过期后 `Recover`，或由用户显式 `takeover` 立即接管。
3. 立即进入“检查循环”。

## 检查循环

1. 调 `CheckBudget -Role coder`。
2. `done`：完成 Goal。`cancelled`：结束 Goal但不报业务 PASS。`wait_human`：停止 Goal并报告 reason 与允许的 resume decision。`paused_budget`：完成本班次 Goal，提示再次启动任一平台 coder。
3. `running + turn=planner`：按本次固化的 `coder_wait_ms` 原生等待后复查，不碰 `temp.md`；无论连续等待多少轮都不标记 Goal `blocked`，也不要求用户重新启动 coder。
4. `running + turn=coder`：完整执行公共协议的 coder 正常轮；安全交棒后若返回暂停，结束本班次 Goal。

coder 永久禁止 `WaitHuman`；失败必须按公共协议写完整证据，以 `HandoffKind failure + FailureKey` 交给 planner。只有 planner 可以最终 `Done`。
