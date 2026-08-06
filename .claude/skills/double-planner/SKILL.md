---
name: double-planner
description: 让 Claude 在当前 Git repo 中担任双窗口接力 planner。用户输入 /double-planner 后，按公共 JSON 配置检查并审核 coder 的真实成果；可搭配 Claude 或 Codex 的 double-coder。
---

# `/double-planner`

先完整读取 repo 启动链和 `$env:USERPROFILE\.agents\double-session-common\protocol.md`，然后严格执行其中“planner 唯一流程”。公共核心缺失时 fail-loud；不得复制协议、回退 Codex skill 目录或手改 `.copilot-state.json`。

## Claude 机制适配

- 状态脚本固定为 `$env:USERPROFILE\.agents\double-session-common\double-session-state.ps1`，角色固定为 `planner`。
- 除 `status/stop` 外，启动或恢复调度前先调用状态脚本 `-Action Config`，读取唯一配置；将 `planner_interval_seconds` 精确换算成整分钟的 Claude `/loop <N>m` 参数。配置读取或校验失败即停，不得使用 skill 内默认值。原 session 重新输入 `/double-planner` 时，再用既有绑定调用 `RefreshBudget`；预算未变化为 no-op，变化时从此刻开启一个新 segment。
- 周期调度只用 Claude Code 内建 `/loop`，间隔使用本次从配置固化的具体 `<N>m`。job 提示词以唯一标记 `[double-planner]` 开头，并要求执行本 skill 的“单轮调度”；禁止 shell 常驻循环或 `Start-Sleep`。
- planner 只审核实际产物，不替 coder 修改任务文件；状态变化只能调用公共脚本。

## 启动

0. 解析 `状态/继续/返工/通过/取消/接管`（兼容原英文入口）。普通中断下，既有本角色 session 的“继续”只恢复其既有 run/role/token；`wait_human` 下的短命令才内部使用当前批准编号。全新或丢失上下文 session 必须显式 `resume <decision> <human_approval_id>`，裸“继续”不得猜 run、token 或 takeover；终态拒绝复活。
1. 调 `Config` 并固化本次 planner loop 间隔。已有本角色绑定时复用 repo/run/token；若本轮由 `/double-planner` 重进，调用一次 `RefreshBudget`。只有真正的新 planner 调度才生成 `worker_token`。state 尚不存在时保持未绑定，只用 `ExpectedRepo` 做只读检查；首次观察到可绑定的 `running|paused_budget` 后才固化 `run_id`，此后每个动作传 `ExpectedRepo / ExpectedRunId / WorkerToken`。token 不匹配时报 `WORKER_ACTIVE`，不隐式 takeover。
2. 用户在原 session 输入“继续”显式恢复时：先查 state；`running` 立即执行单轮，`paused_budget` 用原 token 调 `Recover` 后立即执行单轮。离线过期但 state 仍为 `running` 时，由当前 turn 的检查先落成暂停，再在同次显式恢复里 `Recover`。自动 loop 不得自行续开预算。
3. 若 state 尚未初始化、处于 `wait_human|running`，或终态后有一份更新的新任务等待 coder `Init`，注册唯一 `[double-planner]` loop 并报告 job id。预启动时报告“已进入预启动等待；将在 `<N>` 分钟后自动复查，无需再次输入 `/double-planner`”。等待状态只查 state，不碰 `temp.md`。`paused_budget` 删除 loop，保留原 session 绑定，等待显式“继续”。
4. 只有无新任务的 `done|cancelled` 才不注册或删除 loop，直接按状态报告。

## 单轮调度

1. state 不存在时结束本轮但保留 loop。全新 session 看到 `wait_human` 时同样保持未绑定并只用 `Show -ExpectedRepo` 复查；已绑定 run 后进入 `wait_human` 时保留绑定与 loop。若 coder `ForceInit` 后新 state 的 `replaced_run_id` 精确等于旧绑定且 `replaced_status=wait_human`，自动改绑新 `run_id`；其他 `RUN_MISMATCH` fail-loud。
2. 终态后仅当 `temp.md` 非空、文件哈希不同于 `terminal_temp_sha256` 且 `LastWriteTimeUtc` 晚于 state `updated`，才清除旧绑定并视为“新任务待 Init”；v2 无终态哈希时只比时间。只能查元数据与文件哈希，不得读取正文。
3. 已绑定 `running|paused_budget` 时调 `CheckBudget -Role planner`。
4. 无新任务的 `done|cancelled`：不得读 `temp.md`；用 `CronList`/`CronDelete` 取消本 session 唯一 `[double-planner]` job 并报告状态。
5. `wait_human`：保留本 session 唯一 `[double-planner]` loop，只等合法控制入口；只查 state，不碰 `temp.md`。`paused_budget`：删除 loop 但保留原 session 绑定，提示在两个原 session 输入“继续”；不得要求新开窗口或换 token。
6. `running + turn=coder`：结束本轮，只等 state，不碰 `temp.md`。
7. `running + turn=planner`：完整执行公共协议的 planner 单轮。`REWORK` 后继续 loop；`PASS` 调 `Done` 后立即取消 loop；安全交棒返回暂停时删除 loop并保留原 session 绑定，等待显式恢复。

第一次收到某 `failure_key` 必须核查并 REWORK；只有 state 机械记录两个独立 coder 回合同 key 后才可 `WaitHuman`，不同 key 不累计。
