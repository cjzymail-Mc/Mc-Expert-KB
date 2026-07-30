---
name: double-planner
description: 让 Claude 在当前 Git repo 中担任双窗口接力 planner。用户输入 /double-planner 后，按公共 JSON 配置检查并审核 coder 的真实成果；可搭配 Claude 或 Codex 的 double-coder。
---

# `/double-planner`

先完整读取 repo 启动链和 `$env:USERPROFILE\.agents\double-session-common\protocol.md`，然后严格执行其中“planner 唯一流程”。公共核心缺失时 fail-loud；不得复制协议、回退 Codex skill 目录或手改 `.copilot-state.json`。

## Claude 机制适配

- 状态脚本固定为 `$env:USERPROFILE\.agents\double-session-common\double-session-state.ps1`，角色固定为 `planner`。
- 除 `status/stop` 外，启动或恢复调度前先调用状态脚本 `-Action Config`，读取唯一配置；将 `planner_interval_seconds` 精确换算成整分钟的 Claude `/loop <N>m` 参数。配置读取或校验失败即停，不得使用 skill 内默认值。`max_budget_seconds` 由状态脚本在新 run/新 segment 时读取。
- 周期调度只用 Claude Code 内建 `/loop`，间隔使用本次从配置固化的具体 `<N>m`。job 提示词以唯一标记 `[double-planner]` 开头，并要求执行本 skill 的“单轮调度”；禁止 shell 常驻循环或 `Start-Sleep`。
- planner 只审核实际产物，不替 coder 修改任务文件；状态变化只能调用公共脚本。

## 启动

0. 解析 `状态/继续/返工/通过/取消/接管`（兼容原英文入口）。既有本角色 session 的短命令内部使用当前批准编号；全新 session 必须显式 `resume <decision> <human_approval_id>`。裸“继续”不得猜 run 或 takeover；终态拒绝复活。全新 session 发现遗留 `wait_human` 时显示三选一；选择强制初始化时提示改由 coder 入口执行，planner 不调用 `ForceInit`、不消费新任务。
1. 调 `Config` 并固化本次 planner loop 间隔；state 存在后固化 repo 绝对路径与 `run_id`，生成本窗口唯一 `worker_token`。每个动作传 `ExpectedRepo / ExpectedRunId / WorkerToken`。state 不存在时只能等待 coder Init，不能虚构 run_id。立即执行一次“单轮调度”；普通启动遇同角色有效租约时报 `WORKER_ACTIVE`，用户显式 takeover 可立即接管。
2. 若 state 尚未初始化、正在 `running|paused_budget`，或终态后有一份更新的新任务等待 coder `Init`，注册唯一 `[double-planner]` loop 并报告 job id。`paused_budget` 下 loop 只等待 coder 原位恢复，不碰 `temp.md`。
3. 若已是无新任务的 `done|wait_human`，不注册 loop，直接按状态报告。

## 单轮调度

1. state 不存在时只等待。终态后仅当 `temp.md` 非空、文件哈希不同于 `terminal_temp_sha256` 且 `LastWriteTimeUtc` 晚于 state `updated`，才视为“新任务待 Init”；v2 无终态哈希时只比时间。只能查元数据与文件哈希，不得读取正文。
2. 调 `CheckBudget -Role planner`。
3. `done|cancelled|wait_human` 且不是“新任务待 Init”：不得读 `temp.md`；用 `CronList`/`CronDelete` 取消本 session 唯一 `[double-planner]` job并报告状态。
4. `paused_budget`：保留本 session 唯一 `[double-planner]` loop，只等 coder `Init` 原位开启下一段；只查 state，不碰 `temp.md`。
5. `running + turn=coder`：结束本轮，只等 state，不碰 `temp.md`。
6. `running + turn=planner`：完整执行公共协议的 planner 单轮。`REWORK` 后继续 loop；`PASS` 调 `Done` 后立即取消 loop；安全交棒返回暂停时保留 loop，等待 coder 恢复。

第一次收到某 `failure_key` 必须核查并 REWORK；只有 state 机械记录两个独立 coder 回合同 key 后才可 `WaitHuman`，不同 key 不累计。
