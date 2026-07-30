---
name: double-planner
description: 让 Codex 在当前 Git repo 中担任双窗口接力 planner。用户显式调用 $double-planner 后按公共 JSON 配置创建 active Goal 并审核 coder 的真实成果；可搭配 Claude 或 Codex 的 double-coder。
---

# `$double-planner`

先完整读取 repo 启动链和 `$env:USERPROFILE\.agents\double-session-common\protocol.md`，然后严格执行其中“planner 唯一流程”。公共核心缺失时 fail-loud；不得复制协议、回退 Claude skill 目录或手改 `.copilot-state.json`。

## Codex 机制适配

- 状态脚本固定为 `$env:USERPROFILE\.agents\double-session-common\double-session-state.ps1`，角色固定为 `planner`。
- 除 `status/stop` 外，启动或恢复调度前先调用状态脚本 `-Action Config`，解析唯一配置并计算 `planner_wait_ms = planner_interval_seconds * 1000`；配置读取或校验失败即停，不得使用 skill 内默认值。`max_budget_seconds` 由状态脚本在新 run/新 segment 时读取。
- 使用 active Goal 保持续轮。若已有无关 unfinished Goal，停止并报告，不得覆盖。
- Goal objective 必须写明 reviewer-only、公共 planner 流程、每次先查 state、未轮到或 `paused_budget` 时按本次固化的 `planner_wait_ms` 原生等待、仅 `done|wait_human` 终态结束；状态变化只能调用公共脚本。
- 不得用 shell `while`、sleep、后台进程或 `codex exec` 代替 Goal/native wait。

## 检查循环

0. 解析 `状态/继续/返工/通过/取消/接管`（兼容 `status/resume/stop/takeover`）。既有本角色 session 的短命令内部使用当前批准编号；全新 session 必须显式 `resume <decision> <human_approval_id>`。裸“继续”不得猜 run 或 takeover；终态拒绝复活。全新 session 发现遗留 `wait_human` 时显示三选一；选择强制初始化时提示改由 coder 入口执行，planner 不调用 `ForceInit`、不消费新任务。
1. 调 `Config` 并固化本次 `planner_wait_ms`；state 存在后固化 repo 绝对路径与 `run_id`，生成本窗口唯一 `worker_token`，再创建 Goal 并在 objective 固化三项绑定与 `planner_wait_ms`；后续每个状态动作都传 `ExpectedRepo / ExpectedRunId / WorkerToken`。state 不存在时等待 coder 初始化，不虚构 run_id。终态后仅当 `temp.md` 非空、文件哈希不同于 `terminal_temp_sha256` 且 `LastWriteTimeUtc` 晚于 state `updated`，才视为“新任务待 Init”；不得读取正文或自行初始化。普通启动遇同角色有效租约时报 `WORKER_ACTIVE`；用户显式 `takeover` 可立即接管。
2. 调 `CheckBudget -Role planner`。
3. `done`：完成 Goal。`cancelled`：结束 Goal但不报业务 PASS。`wait_human`：停止 Goal并报告 reason 与允许的 resume decision，不伪造完成。
4. `paused_budget`：保持 Goal，按本次固化的 `planner_wait_ms` 原生等待后复查，只等 coder `Init`，不碰 `temp.md`。
5. `running + turn=coder`：按本次固化的 `planner_wait_ms` 原生等待后复查，不碰 `temp.md`。
6. `running + turn=planner`：完整执行公共协议的 planner 单轮；安全交棒若返回暂停则转入等待，不结束 Goal。

第一次收到某 `failure_key` 必须核查并 REWORK；只有 state 机械记录两个独立 coder 回合同 key 后才可 `WaitHuman`。不同 key 不累计。
