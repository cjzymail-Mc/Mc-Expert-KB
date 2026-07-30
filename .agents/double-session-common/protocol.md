# Double session 接力协议

本协议是 `coder / planner` 两个角色的唯一行为正文。Claude 与 Codex 的四个 skill 只适配各自的调度工具，不复制角色规则。

| 平台 | coder 入口 | planner 入口 |
|---|---|---|
| Claude | `/double-coder` | `/double-planner` |
| Codex | `$double-coder` | `$double-planner` |

任意两个窗口可以组成一组，但同一 run 每个角色只能有一个活跃窗口；不得同时启动两个 coder 或两个 planner 竞争同一 `temp.md`。

## 文件与状态工具

| 文件 | 职责 |
|---|---|
| `.copilot-task.md` | coder `Init` 时从 `temp.md` 冻结的任务；run 内只读 |
| `.copilot-state.json` | `status`、`turn=coder|planner`、`seq`、当前班次预算快照、时间与任务哈希 |
| `.copilot-message.md` | 当前交接正文的持久化快照；与 state 的 `message_sha256/message_seq` 同步 |
| `temp.md` | 当前唯一一棒的交接正文 |
| `double-session-config.json` | 用户可编辑的三个运行参数唯一真相源 |

```powershell
$commonRoot = Join-Path $env:USERPROFILE '.agents\double-session-common'
$stateTool = Join-Path $commonRoot 'double-session-state.ps1'
pwsh -NoProfile -File $stateTool -Action Show
```

支持：`Config / Init / ForceInit / Show / CheckBudget / Consume / Handoff / Done / WaitHuman / ResolveHuman / Cancel / Recover / Takeover`。状态只能由脚本原子写入，模型不得手改。

## 用户可配置参数

`$env:USERPROFILE\.agents\double-session-common\double-session-config.json` 是以下三个参数的唯一真相源：

- `coder_interval_seconds`：coder 调度检查间隔；
- `planner_interval_seconds`：planner 调度检查间隔；
- `max_budget_seconds`：单个连续班次的最大预算。

四个入口启动调度前必须调用状态脚本的 `Config` 动作读取并校验配置，不得在 skill 或脚本中复制默认数值。配置必须恰好包含这三个整数字段；两个检查间隔须为整分钟，范围 60–3600 秒；预算范围 1–86400 秒。缺失、额外字段、非整数、越界或非法 JSON 一律 fail-loud，不静默回退。

调度启动时把对应检查间隔固化到本次 Goal/loop；新 run 或新预算 segment 从配置读取预算并写入 state 作为运行时快照。用户修改 JSON 后，新创建的调度和新预算 segment 生效；已经运行的调度与当前 segment 不被中途改写。`status/stop` 不依赖配置读取，配置写坏后仍可查看或终止现有 run。

## 共同不变量

1. 启动前把非空初始任务写入 repo 根 `temp.md`；只有 coder 可以调用 `Init` 创建或恢复 run。
2. 等待方只查看 state；`turn` 不属于自己时不得读取、清空或分析 `temp.md`。
3. 消费必须调用 `Consume`，让“校验冻结任务与 message snapshot → 读取 temp → 立即写空 → 验证长度为 0”在同一 repo 互斥锁内完成；成功返回前不得分析正文或调用其他工具。同 token 重试返回同一 `.copilot-message.md` 快照，不重复推进状态。
4. 生产者先写完整正文并验非空，再 `Handoff` 或 `Done`。两者在同一 repo 互斥锁内先把正文原子落到 `.copilot-message.md`，记录 `message_sha256/message_seq`，再翻转 state。coder 只能交给 planner，planner 只能交给 coder，只有 planner 可以 `Done`。
5. 每轮所有者先 `CheckBudget`。达到当前 segment 从配置冻结的预算后转 `paused_budget`；若在工作中到期，先完成安全交棒再暂停。恢复时由任一平台的 coder 调用 `Init`：`paused_budget` 原位开启下一段；若中断遗留为 `running + turn=coder` 但 deadline 已过，`Init` 在同一次启动中原子开启下一段，不要求用户二次调用。该转换保留 `run_id`、`turn`、`seq`、冻结任务与 `temp.md`。
6. `paused_budget` 是同一 run 的可恢复暂停态，不是终态。已经启动的 planner 必须保留原生等待调度，只查 state、不得读 `temp.md`，等待 coder `Init` 后自动回到正常轮次；不得要求用户在 coder 完成后再次手工启动 planner。
7. `done|cancelled|wait_human` 后禁止继续消费或修改任务产物。`wait_human` 是可恢复人工门，不是新任务：保留 `run_id`、冻结任务、`resume_turn` 与允许决议；只允许 `ResolveHuman` 原 run 恢复或 `Cancel` 终止。真正终态会记录 `temp.md` 哈希；新 run 要求 `temp.md` 非空、哈希已变化且修改时间晚于 state 的 `updated`，旧最终报告不得冒充新任务。v2 旧终态没有哈希时只用时间戳兼容。
8. 状态机使用 `coder|planner`。为在途旧 worker 暂时接受 `claude|codex` 参数别名并映射旧 turn；新写入升级为 v5，v4 在首次合法写入时惰性迁移并新增 `failure_ledger`。
9. v4 每个 run 固化 `owner_repo`；调度器固化 `ExpectedRepo + ExpectedRunId`，所有读取任务、temp、message 前先校验。漂移时报 `REPO_MISMATCH` 或 `RUN_MISMATCH`，拒绝继续。
10. 每个活跃角色窗口生成并仅在自身调度上下文持有唯一 `worker_token`；state 只保存 token 的 SHA-256，不得通过 `Show` 泄漏原 token。状态动作续租 `worker_lease_deadline`；第二个同角色 token 在租约有效时只得 `WORKER_ACTIVE`。普通自动恢复必须等租约过期；用户显式 takeover 可提交 `takeover:<run_id>` 控制凭证立即轮换 token，并记录 `control_entry`。
11. 所有 mutating action 由 repo 级命名 mutex 串行化，状态迁移使用 `ready|working` phase；任务文件在 Consume/Handoff/Done/WaitHuman/ResolveHuman continue/rework 前必须重新核验 `task_sha256`。冻结任务损坏时仅 `Show/status` 与 `Cancel` 可用。

## 自主轴与人工门归并（coder/planner 共用）

本 run 采用深度授权。只有已经在初始任务中写明 `done_when`、允许范围、禁止动作、验证方式与人工门边界，并被用户认定适合自主执行的任务，才应进入 double-session。运行中的目标是：普通判断不打断用户，planner 最大限度承接人工驱动，非阻塞人工事项留到末尾一次性汇报。

1. **中途零普通人工门**：`Init` 之后，普通口径、方法、命名、范围内取舍、缺少用户默认等判断型疑问，不得弹 `AskUserQuestion` 或等价的中途用户问询，也不得直接 `WaitHuman`。两个角色先按本节自主顺序推进，并把裁决写入交接的 `AUTONOMOUS_DECISIONS`。
2. **自主顺序**：遇到不确定性时依次执行，不得跳步停下：
   1. inspect 实际文件、Git diff、测试输出、冻结任务和现有证据；
   2. 按冻结任务、已封决策或明确默认执行；
   3. 对范围内普通裁量，按“已封默认 > 历史成功率 > 最易回滚”选择；
   4. 只有重大路线分叉、高影响且现有证据支持多个解释的低置信判断，才调用一次性只读 mc-expert；普通缺测试或缺证据不调用，planner 直接按审核阶梯处理。
3. **角色差异**：coder 可在授权范围内按安全默认实施；planner 的自主性只用于选择调查方法、补证据路径和 REWORK 内容，绝不降低 `PASS` 证据门槛。planner 低置信时的安全默认是继续取证，或向 coder 发定向 REWORK，不是默认 `PASS`。
4. **人工门资格**：coder 永远没有人工门权限。命中平台硬拒绝、四红线、只有用户能完成的外部动作或任何技术阻塞时，coder 停止相关动作并把证据交给 planner。planner 也不能以权限担忧、风险、低置信或“更稳妥”为由直接开门；只有状态机已记录两个独立 coder 回合报告同一 `failure_key` 时，planner 才取得资格。取得资格后仍有安全、范围内路线时可以继续 REWORK。
5. **scope 与延后事项**：不得用“可回滚”扩大允许范围或改变验收含义。删除、push、对外交付、范围外优化和可选决策，若未获前置授权且不属于 `done_when`，写入 `PENDING_HUMAN_NONBLOCKING` 后继续；若已在初始任务中明确授权则按授权执行；若它们阻断 `done_when`，按第 4 条处理，不得伪装成可延后事项。
6. **planner 统一归并**：coder 遇到非硬依赖问题必须交给 planner，不直接停。planner 负责继续取证、要求补证据、返工或在末尾汇总。每次 coder/planner 交接都必须原样续传仍未关闭的 `AUTONOMOUS_DECISIONS`、`PENDING_HUMAN_NONBLOCKING`、`OPEN_BLOCKERS`，只可追加或明确标记已关闭，不得静默丢项。
7. **同一失败的机械定义**：`failure_key = <stage>|<error_family>|<error_code>|<unmet_done_when>`，不得包含 PID、时间戳、临时路径或随机文案。相同阶段、类别/错误码和未完成目标才累计；错误移动到新阶段或 key 改变即从 1 开始。同一 coder 回合内的短暂重试、固定一次幂等重试和同 mutation 重放只算一次；只有两个不同 coder→planner 交接序号才能形成 `count=2`。
8. **failure ledger**：coder 失败交接必须传 `HandoffKind failure -FailureKey <key>`，成功交接传 `HandoffKind success` 并清空 active ledger。planner 第一次收到某 key 必须核查并给出可执行 REWORK；第二个独立 coder 回合同 key 后才可调用 `WaitHuman`。不同 key 不累计。`ResolveHuman continue|rework` 清空已处理 ledger，防止旧计数复用。

## coder 唯一流程

coder 采用深度授权 B 模式，但不调用 `/free` 或 `$free`，也不运行其 finalizer：

1. 全程禁止 `AskUserQuestion` 或等价的中途用户问询。普通可逆决策按“已封默认 > 历史成功率 > 最易回滚”自主执行，并记入交接。
2. 只在重大技术选型、修改核心配置/agent/skill/已封决策相关文件、拆分任务前、第一次实质失败后准备第二次尝试、或高风险/低置信/验证未闭的关键交棒前，启动一次性只读 mc-expert；普通机械修改不调用，不建常驻 agent。
3. mc-expert 调用必须在 `Consume` 和读取冻结任务之后、修改之前，交齐 `REVIEW_TARGET / PROJECT_MEMORY / SEALED_DECISION_QUERY / REVIEW_QUESTION`，且一次只问一个问题。调用终态失败最多重试一次；第二次失败按两连失熔断。
4. coder 永久禁止调用 `WaitHuman`。权限疑问、风险、低置信、缺少默认值、mc-expert 不可用、单次技术失败或命中上层硬拒绝，都只能停止相关动作并交给 planner。
5. 正常轮：`CheckBudget -Role coder` → `Consume -Role coder` → 读 `.copilot-task.md` → 实施与验证 → 写 `temp.md`。成功时验非空后调用 `Handoff -Role coder -To planner -HandoffKind success`。
6. 失败轮：交接必须包含稳定 `failure_key`、实际错误、证据路径、本轮实质方案、未满足的 `done_when`、建议 planner 核查点，以及累积清单 `AUTONOMOUS_DECISIONS / PENDING_HUMAN_NONBLOCKING / OPEN_BLOCKERS`；然后调用 `Handoff -Role coder -To planner -HandoffKind failure -FailureKey <key>`。

## planner 唯一流程

planner 只审核，不替 coder 修改任务产物：

1. 未初始化，或终态之后出现非空、哈希不同且时间更新的 `temp.md` 时，等待 coder `Init`；只能查长度、`LastWriteTimeUtc` 和文件哈希，不得读取正文。
2. `paused_budget` 时保持原生等待调度，只查看 state，等待 coder `Init`；不得读取或清空 `temp.md`，不得退出并要求用户稍后重启 planner。
3. `running + turn=coder` 时等待；`running + turn=planner` 时先 `CheckBudget -Role planner`，再 `Consume -Role planner`。
4. **审核自主阶梯**：读取冻结任务与 coder 交接后，依次执行，不得跳步直接 REWORK 或 `WaitHuman`：
   1. 自己检查实际文件、Git diff、测试输出与现有证据，不得只信 coder 自述；
   2. 存在合理替代路径时，至少做一次替代性只读复验，例如重新核对 `done_when`、换工具读取或交叉比对；
   3. 仍属重大、高影响且证据支持多个解释的低置信判断时，调用一次性只读 mc-expert；普通缺证据直接进入下一步；
   4. 只有 coder 能补证据或做定向修复时，才发 REWORK；
   5. 只有命中共用段第 4 条允许的人工门，才进入 `WaitHuman`。
5. `REWORK`：写可执行意见、验非空、`Handoff -Role planner -To coder`。每份 REWORK 必须包含：稳定阻塞点编号 `B-xxx`；实际观察到的事实；缺少的证据或未满足的 `done_when`；coder 下一步具体取证/修复动作；验收方式；允许修改范围；当前 `attempt 1/2` 或 `attempt 2/2`。同时续传三个累积清单，不得以“再看看”代替可执行指令。
6. `PASS`：只有整个冻结任务的 `done_when` 均有实际证据，且剩余 `PENDING_HUMAN_NONBLOCKING` 确认不阻断验收时，才写最终证据并一次性汇报累积的自主裁决与待人工事项，验非空后 `Done -Role planner`。任何阻断 `done_when` 的待人工事项都不得以清单形式带过或伪装成 `PASS`。
7. 第一次收到某 `failure_key` 必须自己核查证据并给出可执行 REWORK，不得 `WaitHuman`。只有 state 中同 key 的独立 coder 报告数达到 2，planner 才可不写 `temp.md` 调用 `WaitHuman -Role planner -Reason <自足摘要>`。approval pass 必须落 `outcome=approval_pass, decision_by=approval_entry`，不冒充 planner 独立 PASS。

## 人工控制与恢复

- 四入口接受中文短命令 `状态/继续/返工/通过/取消/接管`，分别对应 `status/continue/rework/pass/cancel/takeover`。只有用户本轮明确输入控制词时才执行，模型不得看到 `wait_human` 后自动恢复。
- `状态` 只调用 `Show` 并投影状态，不创建 Goal/loop、不刷新租约、不迁移状态。
- 既有同角色 session 在 `wait_human` 下输入 `继续/返工/通过` 时，入口从当前绑定 state 内部取得一次性 `human_approval_id` 并传给 `ResolveHuman`；全新或丢失上下文 session 仍须使用 `resume <decision> <human_approval_id>`，裸“继续”不得猜 run 或隐式 takeover。
- 全新 session 发现同 repo 遗留 `wait_human` 时，必须显示旧 run 摘要并让用户明确选择：`恢复旧任务 / 取消旧任务并强制初始化 / 保留人工门并退出`。不得默认选择，不创建 Goal/loop。只有 coder 入口在用户本轮明确选择第二项后，才可用旧 run、repo 与当前 approval id 调 `ForceInit`；planner 入口只提示改由 coder 入口执行。
- `ForceInit` 只接受 `wait_human`，要求非空且较旧 state 更新、hash 不同的新 `temp.md`，在 repo mutex 内冻结新任务并创建全新 coder run；新 state 记录 `replaced_run_id/replaced_status/replaced_at` 并清空旧批准编号与 ledger。旧窗口随后必须因 `RUN_MISMATCH` 被拒绝。其他状态调用或未检测到新任务均拒绝。
- `继续` 分态：`wait_human` 恢复同一 run；`paused_budget` 由 coder 开新 segment、planner 工作或待机；`running` 立即检查但不重复创建调度器；`done|cancelled` 拒绝复活。非 `resume_turn` 角色不得扮演另一角色。
- `stop` 入口只调用 `Cancel`；允许从 `running|paused_budget|wait_human` 终止，同一 scheduler 下次 tick 看到 `cancelled` 必须退出。重复 stop 幂等返回原 cancelled 状态；done 后 stop 明确返回 `CANCEL_NOT_ALLOWED_DONE`。脚本只记录 `decision_by=control_entry`。
- `continue|rework|pass|cancel` 只能用于当前 `wait_human` 的 `allowed_resolutions`，并必须提交匹配的一次性 `human_approval_id`；不匹配即拒绝，成功后立即清空 id。
- 中断恢复优先原 token；token 丢失时，自动恢复必须等租约过期。用户显式 `Takeover -HumanApprovalId takeover:<run_id>` 可立即接管并轮换 token；不得靠扫描进程或猜窗口存活。
- 所有后续动作都传 `ExpectedRepo`、`ExpectedRunId`、`WorkerToken`；`Show/status` 至少传前两项。

## 常用命令

```powershell
$repo = (& git rev-parse --show-toplevel).Trim()
$workerToken = [guid]::NewGuid().ToString('N')
$state = pwsh -NoProfile -File $stateTool -Action Init -ExpectedRepo $repo -WorkerToken $workerToken | ConvertFrom-Json
$runId = $state.run_id
pwsh -NoProfile -File $stateTool -Action Show -ExpectedRepo $repo -ExpectedRunId $runId
pwsh -NoProfile -File $stateTool -Action CheckBudget -Role coder -ExpectedRepo $repo -ExpectedRunId $runId -WorkerToken $workerToken
pwsh -NoProfile -File $stateTool -Action Consume -Role coder -ExpectedRepo $repo -ExpectedRunId $runId -WorkerToken $workerToken
pwsh -NoProfile -File $stateTool -Action Handoff -Role coder -To planner -ExpectedRepo $repo -ExpectedRunId $runId -WorkerToken $workerToken
```

planner 使用自己生成的 `$workerToken`，并同样传三项绑定。`ResolveHuman` 还必须传 state 中本次待裁决的 `-HumanApprovalId`；`Cancel` 记录控制入口来源而非不可证明的人类身份。
