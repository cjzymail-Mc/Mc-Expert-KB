---
name: double-coder
description: 让 Codex 在当前 Git repo 中担任双窗口接力 coder。用户显式调用 $double-coder 后按公共 JSON 配置创建 active Goal，采用深度授权 B 模式执行或恢复任务；可搭配 Claude 或 Codex 的 double-planner。
---

# `$double-coder`

先完整读取 repo 启动链和 `$env:USERPROFILE\.agents\double-session-common\protocol.md`，然后严格执行其中“coder 唯一流程”。公共核心缺失时 fail-loud；不得复制协议、回退 Claude skill 目录或手改 `.copilot-state.json`。

## Codex 机制适配

- 状态脚本固定为 `$env:USERPROFILE\.agents\double-session-common\double-session-state.ps1`，角色固定为 `coder`。
- **无人值守权限硬门**：除 `status/stop` 外，读取 live skill/protocol 后、调用 `Config` 前，先核对**当前 turn** 的实际权限上下文；正常执行要求当前 turn 明确为 `sandbox_mode=workspace-write + approvals_reviewer=auto_review`，若上下文同时暴露 `approval_policy`，它必须为 `on-request`。`config.toml` 中的 `approval_policy=on-request` 只是新 turn 默认值，不能替代当前 turn 的 sandbox/reviewer 证据；旧 transcript、Goal objective 或本 turn 中途才切换的 UI 选项也不能冒充已生效。当前 developer/environment 权限上下文不能确认 workspace-write 与 auto_review、或明确暴露了冲突 policy 时，零 state/Goal/业务写入并返回 `UNATTENDED_PERMISSION_CONTEXT_INVALID`。修复入口是退出或中断旧 turn，在正确权限下 resume 原 session/Goal；不得清 Goal、换 token 或把权限字段写进 objective 假装修复。
- **零弹窗命令门**：每次 shell 调用前先按冻结任务和公共协议检查权限动作。普通路径不得包含未被 `done_when` 硬依赖且精确授权的 `Remove-Item/rm/del/rmdir/git clean/git reset`、覆盖已有输出、GUI/网络/工作区外写，也不得把清理与构建/验证捆在同一命令。验证需要新输出时使用允许路径内的全新唯一文件名/outdir；可选清理一律记入 `PENDING_HUMAN_NONBLOCKING`，不发 PermissionRequest。真正硬依赖才按公共失败交接给 planner，禁止为“顺手清理”触发审批。
- **状态动作默认沙箱硬门**（`STATE_ACTION_SANDBOX_FIRST=USE_DEFAULT`）：状态脚本虽位于 user-scope，针对当前 repo 的 `Config/GoalContract/Init/Show/WaitTurn/CheckBudget/RefreshBudget/Consume/Handoff/Recover/Cancel/Takeover` 等调用仍必须先走默认沙箱。嵌套 `shell_command` 固定 `login:false`、`workdir=<repo>`、`sandbox_permissions=use_default`（或省略该字段），且每次只运行一个直接的 `pwsh -NoProfile -File ... -Action <action>`；不得加管道、重定向、复合诊断或仅因脚本路径在工作区外而预先申请 `require_escalated`。只有这条精确最小命令明确返回真实 sandbox denial 后，才允许对同一 action 发起至多一次窄化提权；approval reviewer 的拒绝、超时或 `no assessment payload` 不是 sandbox denial，不得同轮循环重试。提权仍失败时保持 state 与任务产物原状，报告 `STATE_ACTION_TRANSPORT_BLOCKED` 并停止本轮，不得绕开状态机手改 state。
- 除 `status/stop` 外，启动或恢复调度前先调用状态脚本 `-Action Config`，解析唯一配置并固化 `coder_wait_seconds = coder_interval_seconds`；配置读取或校验失败即停，不得使用 skill 内默认值。原 session 重新输入 `$double-coder` 时，再用既有绑定调用 `RefreshBudget`；预算未变化为 no-op，变化时从此刻开启一个新 segment。
- 使用 active Goal 保持续轮。非 `status/stop` 入口严格执行 `live skill/protocol → Config → Show live state → get_goal → 决策`；`Show` 之前禁止依据 transcript、旧工具输出或 Goal objective 判断当前 status/turn/seq。已有与当前 repo/run/role 匹配的 unfinished Goal 时必须复用。v2 的 `worker_token` 只能从 Goal objective 独立的 `worker_token=` 行恢复；`store()` 仅可作本轮缓存，绝不是跨 turn 或重启真相源。旧 Goal 可兼容 objective 内嵌的精确 `worker_token=<值>` 字段，但必须同时匹配 repo/run/role，并在首个 mutation 前把该值的 SHA-256 与 state 中本角色 hash 比对；不得回显 token。
- 新 Goal 必须严格执行公共协议的 `CODEX_GOAL_BRIDGE_V1`：用状态脚本 `GoalContract -CodexJsonEnvelope` 生成单行 JSON 信封，且 `env.envelope` 必须精确等于 `DOUBLE_SESSION_CODEX_GOAL_ENVELOPE=v1`，不得拿流程名代替字段值。校验后把完整 `goal_objective` **逐字**作为 `create_goal.objective`；严禁 Base64、`atob`、`btoa`、`Buffer` 或其他自创编码桥。该契约固化 repo/run/role/token，并要求每次 Goal continuation 在任何 state 动作前重新完整读取当前 live skill、公共 protocol 和 Config；live 文件覆盖 Goal 中旧流程文字。
- Goal 只在无新任务的 `done|cancelled` 完成；`paused_budget`、`wait_human`、轮到 planner、state 多轮不变、`store()` 为空都不得 `complete|blocked`。未轮到时调用状态脚本 `WaitTurn`（传刚观察到的 seq 与本次固化的 `coder_wait_seconds`）；合法交棒可提前返回，超时按原周期复查。除这个公共脚本的单次有界 `WaitTurn` 外，不得用 shell 常驻循环、sleep、后台进程代替。
- `WAITTURN_UX=SILENT_UNTIL_RETURN`：同一个 `WaitTurn` 工具 cell 尚未返回时，不得主动输出“继续监听 / 仍在运行 / 等待中”等重复自然语言心跳，也不得仅为心跳重新读取业务 state。只在收到合法 Handoff/Done 信号、达到完整 `TimeoutSeconds` 或异常退出时报告一次；平台自动工具状态不冒充业务进度，也不承诺由 skill 隐藏。
- 命中公共陪审扳机时，先完整读取 `$env:USERPROFILE\.agents\skills\_mc-common\codex-runtime-bindings.md` 与 `$env:USERPROFILE\.codex\agents\mc-expert.toml`，再用 native custom agent `mc-expert`、`fork_turns=none`、四字段合同做一次性只读陪审。无 native surface 或调用失败也不得 `WaitHuman`，须把证据交给 planner；不得用 `codex exec` 冒充。
- 自主接力中不得请求普通用户决策。普通可逆事项按公共协议默认顺序自走并记录；权限动作后置，真正人工硬门非阻塞停机。

## 启动 Goal

0. 解析 `状态/继续/返工/通过/取消/接管`（兼容 `status/resume/stop/takeover`）。普通中断的“继续”只恢复 Goal objective 中的持久绑定；`wait_human` 下的短命令才内部使用当前批准编号。终态拒绝复活。
1. 完整读 live skill/protocol，调 `Config` 并固化 `coder_wait_seconds`，立即调用 `Show -ExpectedRepo <repo>` 取得 live state，最后才 `get_goal`。固定顺序标记：`REENTRY_ORDER=CONFIG_SHOW_GOAL`。本门必须在同一次 `functions.exec` 编排调用中依次串行 `await Config → await Show → await native get_goal`；三者禁止并行，任一步失败即结束该调用。该调用返回前禁止任何 state/Goal mutation，后续只以本次 `Show` 与 `get_goal` 的返回值决策。匹配 Goal 带 v2 契约时逐行恢复绑定；旧 Goal 带完整明文 token 时按相同绑定兼容，但本轮行为以当前 skill/protocol 为准。无关 unfinished Goal 停止并报告。
2. 匹配 Goal 的 `$double-coder` 重进先 `RefreshBudget`；若之后为 `paused_budget` 再 `Recover`。Continue Goal、`/goal resume` 或同 session“继续”显式恢复时先查 state：`running` 立即检查；`paused_budget` 用契约 token `Recover` 后立即检查。`Recover` 成功后立即重新 `Show`，丢弃 Recover 前的 `status/turn/seq/last_action/last_action_role`，只以新 `Show` 继续决策；沿用本轮首次 `get_goal` 已恢复并核验的 Goal binding，不再次调用 `get_goal`。离线过期但仍显示 `running` 时，当前 turn 先 `CheckBudget` 落暂停，再在同次显式恢复中 `Recover`。自动续轮不得自行开预算。
3. 没有 unfinished Goal 时：只有 `temp.md` 新任务且没有活跃 run 才生成 token、调用 `Init`；若 live `Show` 为 `running + turn=coder + seq=0 + phase=ready + last_action 为空 + last_action_seq=-1`，生成新 token但暂不改 state，按第 4 步的孤儿分支处理。若 live `Show` 为 `running|paused_budget + turn=coder + last_action=Handoff + last_action_role=planner`，生成新 token并调用 `SafeTakeover`，由脚本机械核验 phase/seq/message/temp/hash；成功后按第 4 步创建 v2 Goal。其他活跃 run 禁止用 `Init` 偷换绑定并报告 `TOKEN_BINDING_LOST`。
4. 普通新 run 或完整 Handoff 已取得精确 run 后，调用 `GoalContract -CodexJsonEnvelope`，严格校验 `env.envelope === "DOUBLE_SESSION_CODEX_GOAL_ENVELOPE=v1"` 与其余绑定，缓存后将 `goal_objective` 逐字传给 `create_goal`。孤儿分支是唯一顺序例外：先用精确 run 调 `GoalContract`、校验、缓存并创建 Goal，成功后才调用 `SafeBootstrapTakeover`；最后立即 `Show` 复核 token hash。任一步失败即停，不回显 token。随后进入“检查循环”。

## 检查循环

1. 每轮先 `Show`。从 objective 恢复 token 后计算 SHA-256 并与 state 中 coder hash 比对；不匹配且当前是 planner→coder 完整 Handoff 时先 `SafeTakeover`，其他不匹配现场 fail-loud。随后才调 `CheckBudget -Role coder`。
2. `done`：完成 Goal。`cancelled`：结束 Goal但不报业务 PASS。`wait_human`：停止本次自动续轮并报告 reason 与允许的 resume decision。`paused_budget`：停止本次自动续轮但保留原 Goal/绑定，提示在两个原 session 选择 Continue Goal 或输入“继续”；不得标成 complete/blocked，不得清 Goal。
3. `running + turn=planner`：调用 `WaitTurn -Role coder -ObservedSeq <刚观察到的 seq> -TimeoutSeconds <coder_wait_seconds>` 并传 repo/run 绑定；工具调用 timeout 必须覆盖该等待上限。收到 signal 或 timeout 后都重新查 state，不碰 `temp.md`；无论连续等待多少轮都不标记 Goal `blocked`，也不要求用户重新启动 coder。
4. `running + turn=coder`：完整执行公共协议的 coder 正常轮；安全交棒后若返回暂停，只结束本次自动续轮，保留可 Continue 的原 Goal。

coder 永久禁止 `WaitHuman`；失败必须按公共协议写完整证据，以 `HandoffKind failure + FailureKey` 交给 planner。只有 planner 可以最终 `Done`。
