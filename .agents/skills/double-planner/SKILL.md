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
- Goal objective 必须写明 reviewer-only、公共 planner 流程、固化的 repo / `worker_token` / `planner_wait_ms`、每次先查 state，以及“首次观察到可绑定的 `running|paused_budget` 后固化 `run_id`”。state 未出现、`wait_human`、未轮到或 `paused_budget` 时都按本次固化的 `planner_wait_ms` 原生等待；只有无新任务的 `done|cancelled` 才结束。
- 上述等待都是 Goal 的正常监控状态；state 连续多轮不变也不得据此调用 `update_goal(blocked)`、结束 Goal 或要求用户重新输入 `$double-planner`。
- 不得用 shell `while`、sleep、后台进程或 `codex exec` 代替 Goal/native wait。

## 检查循环

0. 解析 `状态/继续/返工/通过/取消/接管`（兼容 `status/resume/stop/takeover`）。既有本角色 session 的短命令内部使用当前批准编号；全新 session 必须显式 `resume <decision> <human_approval_id>`。裸“继续”不得猜 run 或 takeover；终态拒绝复活。全新 session 发现遗留 `wait_human` 时只显示旧 run 摘要，随后进入预启动等待；不重复三选一人工门、不调用 `ForceInit`、不消费新任务。
1. 调 `Config` 并固化本次 `planner_wait_ms`；确认无冲突 Goal，固化 repo 绝对路径并生成本窗口唯一 `worker_token`，立即创建 active Goal。即使 state 尚不存在或仍是 `wait_human`，也必须先创建 Goal，不得退出。objective 将 `run_id` 记为“首次观察到的可绑定 `running|paused_budget`”；绑定前只传 `ExpectedRepo` 做只读 `Show`，绑定后每个状态动作都传 `ExpectedRepo / ExpectedRunId / WorkerToken`。
2. 每轮先只读检查 state。state 不存在时进入预启动等待；报告“已进入预启动等待；将在 `<planner_interval_seconds / 60>` 分钟后自动复查，无需再次输入 `$double-planner`”，按 `planner_wait_ms` 等待后重试，不虚构 `run_id`。
3. 全新 session 观察到 `wait_human` 时保持未绑定，只用 `Show -ExpectedRepo` 复查；已绑定 run 后进入 `wait_human` 时保留绑定并等待合法控制入口。若 coder `ForceInit` 后新 state 的 `replaced_run_id` 精确等于旧绑定且 `replaced_status=wait_human`，自动改绑新 `run_id`；其他 `RUN_MISMATCH` 一律停止并报告。
4. `done|cancelled` 后，仅当 `temp.md` 非空、文件哈希不同于 `terminal_temp_sha256` 且 `LastWriteTimeUtc` 晚于 state `updated`，才清除旧绑定并视为“新任务待 Init”，进入预启动等待；只查元数据和哈希，不读正文。没有新任务时结束 Goal，`cancelled` 不报业务 PASS。
5. 绑定 `running|paused_budget` 后调 `CheckBudget -Role planner`。普通启动遇同角色有效租约时报 `WORKER_ACTIVE` 时，保留 Goal 并按 `planner_wait_ms` 复查；用户显式 `takeover` 可立即接管。
6. `wait_human|paused_budget`：保持 Goal，按 `planner_wait_ms` 原生等待后复查，只等合法控制入口或 coder `Init`，不碰 `temp.md`。
7. `running + turn=coder`：按 `planner_wait_ms` 原生等待后复查，不碰 `temp.md`。
8. `running + turn=planner`：完整执行公共协议的 planner 单轮；安全交棒若返回暂停则转入等待，不结束 Goal。

第一次收到某 `failure_key` 必须核查并 REWORK；只有 state 机械记录两个独立 coder 回合同 key 后才可 `WaitHuman`。不同 key 不累计。
