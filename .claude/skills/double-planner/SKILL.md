---
name: double-planner
description: 让 Claude 在当前 Git repo 中担任双窗口接力 planner。用户输入 /double-planner 时，先把 repo 根 temp.md 的零散需求准备成冻结合同并等待 coder Init，再独立审核真实成果；可搭配 Claude 或 Codex 的 double-coder。
---

# `/double-planner`

先完整读取 repo 启动链和 `$env:USERPROFILE\.agents\double-session-common\protocol.md`，然后严格执行其中“planner 唯一流程”。公共核心缺失时 fail-loud；不得复制协议、回退 Codex skill 目录或手改 `.copilot-state.json`。

## Claude 机制适配

- 状态脚本固定为 `$env:USERPROFILE\.agents\double-session-common\double-session-state.ps1`，角色固定为 `planner`。
- 除 `status/stop` 外，启动或恢复调度前先调用状态脚本 `-Action BootstrapProbe`，从返回配置读取唯一间隔并固化 route、state、合同状态与分段计时；将 `planner_interval_seconds` 精确换算成 `/loop <N>m`。探针或配置失败即停。原 session 重进时再用既有绑定调用 `RefreshBudget`。
- runtime 只按当前 session 的稳定一手 model/provider 证据分类为 `claude-native|claude-glm|other`；无法证明时用 `unknown`，并在合同中把 `review_gate` 写成 `planner_plus_mc_expert`。
- 周期调度只用 Claude Code 内建 `/loop`，间隔使用本次从配置固化的具体 `<N>m`。job 提示词以唯一标记 `[double-planner]` 开头，并要求执行本 skill 的“单轮调度”；禁止 shell 常驻循环或 `Start-Sleep`。
- planner 只审核实际产物，不替 coder 修改任务文件；状态变化只能调用公共脚本。

## 启动

0. 解析 `状态/继续/返工/通过/取消/接管`（兼容原英文入口）。普通中断下，既有本角色 session 的“继续”只恢复其既有 run/role/token；`wait_human` 下的短命令才内部使用当前批准编号。全新或丢失上下文 session 必须显式 `resume <decision> <human_approval_id>`，裸“继续”不得猜 run、token 或 takeover；终态拒绝复活。
1. 调 `BootstrapProbe` 并固化本次 planner loop 间隔。已有绑定时复用 repo/run/token；重进时调用一次 `RefreshBudget`。没有 active state 时按 route 处理：空草稿直接返回；结构缺项报 `TASK_PREFLIGHT_REQUIRED`；零散需求调用 `ConsumeDraft`，成功返回前不分析，随后按公共合同 schema 完成 KO、写回 `temp.md` 并 `CommitContract`；合格合同不重写。终态新任务先幂等 `ArchiveRun`，再走对应分支。全新 session 无匹配绑定且 route 为 `RESUME_RUN|WAIT_HUMAN_DECISION` 时，严格执行公共协议的“遗留 active run 处置门”；用户明确放弃时只调用现有 `Cancel → ArchiveRun`，然后提示其重新写入新需求。active state 下始终禁止 KO、禁止读取或改写 `temp.md`。
2. 用户在原 session 输入“继续”显式恢复时：先查 state；`running` 立即执行单轮，`paused_budget` 用原 token 调 `Recover` 后立即执行单轮。离线过期但 state 仍为 `running` 时，由当前 turn 的检查先落成暂停，再在同次显式恢复里 `Recover`。自动 loop 不得自行续开预算。
3. 只有合同已准备并取得 `prepared_task_sha256` 后才注册唯一 `[double-planner]` loop；在本 session 持久保留 prepared hash。预启动时报告“合同已准备，正在等待 coder Init”。观察到 state 后先核对 `state.task_sha256 == prepared_task_sha256`，不一致 fail-loud。已有本 session 绑定的 `wait_human|running` 旧 run 继续按原等待；`paused_budget` 删除 loop并保留绑定。
4. 只有无新任务的 `done|cancelled` 才不注册或删除 loop，直接按状态报告。

## 单轮调度

1. state 不存在时结束本轮但保留 loop。全新 session 看到 `wait_human` 时同样保持未绑定并只用 `Show -ExpectedRepo` 复查；已绑定 run 后进入 `wait_human` 时保留绑定与 loop。若 coder `ForceInit` 后新 state 的 `replaced_run_id` 精确等于旧绑定且 `replaced_status=wait_human`，自动改绑新 `run_id`；其他 `RUN_MISMATCH` fail-loud。
2. 终态后只按 `BootstrapProbe` 的新任务判定行动；先 `ArchiveRun`，再准备合同并清除旧绑定。归档失败不得清空新需求或覆盖旧 task/state/message。
3. 已绑定 `running|paused_budget` 时调 `CheckBudget -Role planner`。
4. 无新任务的 `done|cancelled`：不得读 `temp.md`；用 `CronList`/`CronDelete` 取消本 session 唯一 `[double-planner]` job 并报告状态。
5. `wait_human`：保留本 session 唯一 `[double-planner]` loop，只等合法控制入口；只查 state，不碰 `temp.md`。`paused_budget`：删除 loop 但保留原 session 绑定，提示在两个原 session 输入“继续”；不得要求新开窗口或换 token。
6. `running + turn=coder`：结束本轮，只等 state，不碰 `temp.md`。
7. `running + turn=planner`：完整执行公共协议的 planner 单轮。`REWORK` 后继续 loop。候选 PASS 逐条按冻结 `done_when` 取证，可靠失败类构造反例真跑，先 `RecordGateResult` 记录 planner 结果；有效门为双门时再调用只读 `mc-expert` 且不喂 planner 预判，记录第二门。只有 state 机械允许才 `Done` 并取消 loop。

第一次收到某 `failure_key` 必须核查并 REWORK；只有 state 机械记录两个独立 coder 回合同 key 后才可 `WaitHuman`，不同 key 不累计。
