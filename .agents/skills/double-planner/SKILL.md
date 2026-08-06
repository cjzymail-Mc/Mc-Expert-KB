---
name: double-planner
description: 让 Codex 在当前 Git repo 中担任双窗口接力 planner。用户显式调用 $double-planner 后按公共 JSON 配置创建 active Goal 并审核 coder 的真实成果；可搭配 Claude 或 Codex 的 double-coder。
---

# `$double-planner`

先完整读取 repo 启动链和 `$env:USERPROFILE\.agents\double-session-common\protocol.md`，然后严格执行其中“planner 唯一流程”。公共核心缺失时 fail-loud；不得复制协议、回退 Claude skill 目录或手改 `.copilot-state.json`。

## Codex 机制适配

- 状态脚本固定为 `$env:USERPROFILE\.agents\double-session-common\double-session-state.ps1`，角色固定为 `planner`。
- **无人值守权限硬门**：除 `status/stop` 外，读取 live skill/protocol 后、调用 `Config` 前，先核对**当前 turn** 的实际权限上下文；正常执行要求当前 turn 明确为 `sandbox_mode=workspace-write + approvals_reviewer=auto_review`，若上下文同时暴露 `approval_policy`，它必须为 `on-request`。`config.toml` 中的 `approval_policy=on-request` 只是新 turn 默认值，不能替代当前 turn 的 sandbox/reviewer 证据；旧 transcript、Goal objective 或本 turn 中途才切换的 UI 选项也不能冒充已生效。当前 developer/environment 权限上下文不能确认 workspace-write 与 auto_review、或明确暴露了冲突 policy 时，零 state/Goal/业务写入并返回 `UNATTENDED_PERMISSION_CONTEXT_INVALID`。修复入口是退出或中断旧 turn，在正确权限下 resume 原 session/Goal；不得清 Goal、换 token 或把权限字段写进 objective 假装修复。
- **只读审核零弹窗门**：planner 不得删除、覆盖或“顺手清理”任何任务/验证产物，不得把 `Remove-Item/rm/del/rmdir/git clean/git reset` 与独立复验捆在同一命令。确需生成独立证据且冻结任务允许时，只能在允许写路径使用全新唯一文件名/outdir；已有路径即换名，不先删。GUI/网络/工作区外写和可选清理记入累计清单，不发 PermissionRequest；阻断验收时按公共审核阶梯 REWORK，不自行提权。
- **状态动作默认沙箱硬门**（`STATE_ACTION_SANDBOX_FIRST=USE_DEFAULT`）：状态脚本虽位于 user-scope，针对当前 repo 的 `Config/GoalContract/Show/WaitTurn/CheckBudget/RefreshBudget/Consume/Handoff/Done/WaitHuman/ResolveHuman/Recover/Cancel/Takeover` 等调用仍必须先走默认沙箱。嵌套 `shell_command` 固定 `login:false`、`workdir=<repo>`、`sandbox_permissions=use_default`（或省略该字段），且每次只运行一个直接的 `pwsh -NoProfile -File ... -Action <action>`；不得加管道、重定向、复合诊断或仅因脚本路径在工作区外而预先申请 `require_escalated`。只有这条精确最小命令明确返回真实 sandbox denial 后，才允许对同一 action 发起至多一次窄化提权；approval reviewer 的拒绝、超时或 `no assessment payload` 不是 sandbox denial，不得同轮循环重试。提权仍失败时保持 state 与任务产物原状，报告 `STATE_ACTION_TRANSPORT_BLOCKED` 并停止本轮；planner 尤其不得以 `apply_patch` 直接修改 coder 产物来绕开 Handoff 或角色分工。
- 除 `status/stop` 外，启动或恢复调度前先调用状态脚本 `-Action Config`，解析唯一配置并固化 `planner_wait_seconds = planner_interval_seconds`；配置读取或校验失败即停，不得使用 skill 内默认值。原 session 重新输入 `$double-planner` 时，再用既有绑定调用 `RefreshBudget`；预算未变化为 no-op，变化时从此刻开启一个新 segment。
- 使用 active Goal 保持续轮。非 `status/stop` 入口严格执行 `live skill/protocol → Config → Show live state → get_goal → 决策`；`Show` 之前禁止依据 transcript、旧工具输出或 Goal objective 判断当前 status/turn/seq。已有与当前 repo/run/role 匹配的 unfinished Goal 时必须复用。v2 的 `worker_token` 只能从 Goal objective 独立的 `worker_token=` 行恢复；`store()` 仅可作本轮缓存，绝不是跨 turn 或重启真相源。旧 Goal 可兼容 objective 内嵌的精确 `worker_token=<值>` 字段，但必须同时匹配 repo/run/role，并在首个 mutation 前把该值的 SHA-256 与 state 中本角色 hash 比对；不得回显 token。
- 新 Goal 必须严格执行公共协议的 `CODEX_GOAL_BRIDGE_V1`：用状态脚本 `GoalContract -CodexJsonEnvelope` 生成单行 JSON 信封，且 `env.envelope` 必须精确等于 `DOUBLE_SESSION_CODEX_GOAL_ENVELOPE=v1`，不得拿流程名代替字段值。校验后把完整 `goal_objective` **逐字**作为 `create_goal.objective`；严禁 Base64、`atob`、`btoa`、`Buffer` 或其他自创编码桥。该契约固化 repo/run/role/token，并要求每次 Goal continuation 在任何 state 动作前重新完整读取当前 live skill、公共 protocol 和 Config；live 文件覆盖 Goal 中旧流程文字。
- Goal 只在无新任务的 `done|cancelled` 完成；`paused_budget`、`wait_human`、轮到 coder、state 多轮不变、`store()` 为空都不得 `complete|blocked`。绑定前 state 未出现时按原生等待；绑定后未轮到或 `wait_human` 时调用公共脚本 `WaitTurn`，合法交棒可提前返回、超时按原周期复查。
- 除公共脚本的单次有界 `WaitTurn` 外，不得用 shell `while`、sleep、后台进程或 `codex exec` 代替 Goal 等待。
- `WAITTURN_UX=SILENT_UNTIL_RETURN`：同一个 `WaitTurn` 工具 cell 尚未返回时，不得主动输出“继续监听 / 仍在运行 / 等待中”等重复自然语言心跳，也不得仅为心跳重新读取业务 state。只在收到合法 Handoff/Done 信号、达到完整 `TimeoutSeconds` 或异常退出时报告一次；平台自动工具状态不冒充业务进度，也不承诺由 skill 隐藏。

## 检查循环

0. 解析 `状态/继续/返工/通过/取消/接管`（兼容 `status/resume/stop/takeover`）。普通中断的“继续”只恢复 Goal objective 中的持久绑定；`wait_human` 下的短命令才内部使用当前批准编号。终态拒绝复活。
1. 完整读 live skill/protocol，调 `Config` 并固化 `planner_wait_seconds`，立即调用 `Show -ExpectedRepo <repo>`（state 不存在只接受 `STATE_NOT_FOUND`），最后才 `get_goal`。固定顺序标记：`REENTRY_ORDER=CONFIG_SHOW_GOAL`。本门必须在同一次 `functions.exec` 编排调用中依次串行 `await Config → await Show → await native get_goal`；三者禁止并行，任一步失败即结束该调用。该调用返回前禁止任何 state/Goal mutation，后续只以本次 `Show` 与 `get_goal` 的返回值决策。匹配 Goal 带 v2 契约时逐行恢复绑定；旧 Goal 带完整明文 token 时按相同绑定兼容，但本轮行为以当前 skill/protocol 为准。无关 unfinished Goal 停止并报告。
2. 匹配 Goal 的 `$double-planner` 重进先 `RefreshBudget`；若之后为 `paused_budget` 再 `Recover`。Continue Goal、`/goal resume` 或同 session“继续”显式恢复时先查 state：`running` 立即检查；`paused_budget` 用契约 token `Recover` 后立即检查。`Recover` 成功后立即重新 `Show`，丢弃 Recover 前的 `status/turn/seq/last_action/last_action_role`，只以新 `Show` 继续决策；沿用本轮首次 `get_goal` 已恢复并核验的 Goal binding，不再次调用 `get_goal`。离线过期但仍显示 `running` 时，当前 turn 先 `CheckBudget` 落暂停，再在同次显式恢复中 `Recover`。自动续轮不得自行开预算。
3. 没有 unfinished Goal 时生成 planner token。state 尚不存在可用 `GoalContract` 的 `run_id=PENDING` 创建 Goal并预启动等待。已有活跃 run 时分两种：① live state 正轮到 planner 且最后动作是 coder Handoff，先 `SafeTakeover` 再创建 v2 Goal；② live state 正轮到 coder，直接为该 run 创建 v2 Goal但不碰 planner lease，只用 `WaitTurn` 等 Handoff。其他 planner 中途现场报告 `TOKEN_BINDING_LOST`。当前旧 `paused` planner Goal不能由工具原地改 objective；用户明确 `/goal clear` 后重输 `$double-planner`，只按本条做一次性 v2 迁移。
4. 新建或安全重绑时，在同一个 `functions.exec` cell 内按 `CODEX_GOAL_BRIDGE_V1` 调用 `GoalContract -CodexJsonEnvelope -Role planner -ExpectedRepo <repo> [-ExpectedRunId <run>] -WorkerToken <token>`，严格校验 `env.envelope === "DOUBLE_SESSION_CODEX_GOAL_ENVELOPE=v1"` 与其余绑定，缓存后将 `goal_objective` 逐字传给 `create_goal`；不得把 token 只放进 `store()`。绑定后每个状态动作都传 `ExpectedRepo / ExpectedRunId / WorkerToken`。
5. 每轮先只读检查 state。state 不存在时进入预启动等待；报告“已进入预启动等待；将在 `<planner_interval_seconds / 60>` 分钟后自动复查，无需再次输入 `$double-planner`”，按固化间隔原生等待后重试，不虚构 `run_id`。
6. 全新 session 观察到 `wait_human` 时保持未绑定，只用 `Show -ExpectedRepo` 复查；已绑定 run 后进入 `wait_human` 时保留绑定并等待合法控制入口。若 coder `ForceInit` 后新 state 的 `replaced_run_id` 精确等于旧绑定且 `replaced_status=wait_human`，自动改绑新 `run_id`；其他 `RUN_MISMATCH` 一律停止并报告。
7. `done|cancelled` 后，仅当 `temp.md` 非空、文件哈希不同于 `terminal_temp_sha256` 且 `LastWriteTimeUtc` 晚于 state `updated`，才清除旧绑定并视为“新任务待 Init”，进入预启动等待；只查元数据和哈希，不读正文。没有新任务时结束 Goal，`cancelled` 不报业务 PASS。
8. 每轮先 `Show`。从 objective 恢复 token 后计算 SHA-256 并与 state 中 planner hash 比对：匹配才调 `CheckBudget`；不匹配且 `turn=coder` 时只执行 `WaitTurn`；不匹配且当前是 coder→planner 完整 Handoff 时先 `SafeTakeover`，再 `CheckBudget/Consume`；其他不匹配现场 fail-loud。显式恢复预算仍按第 2 步处理，不使用宽松 `Takeover`。
9. 已绑定 run 的 `wait_human`：保持 Goal，调用 `WaitTurn -Role planner -ObservedSeq <刚观察到的 seq> -TimeoutSeconds <planner_wait_seconds>` 并传 repo/run 绑定。`paused_budget`：停止本次自动续轮但保留原 Goal/绑定，提示在两个原 session 选择 Continue Goal 或输入“继续”；不得标成 complete/blocked，不得清 Goal。
10. `running + turn=coder`：用同一 `WaitTurn` 调用等待 signal 或 timeout，返回后复查，不碰 `temp.md`。
11. `running + turn=planner`：完整执行公共协议的 planner 单轮；安全交棒若返回暂停，只结束本次自动续轮，保留可 Continue 的原 Goal。

第一次收到某 `failure_key` 必须核查并 REWORK；只有 state 机械记录两个独立 coder 回合同 key 后才可 `WaitHuman`。不同 key 不累计。
