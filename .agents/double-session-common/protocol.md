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

支持：`Config / GoalContract / Init / ForceInit / Show / WaitTurn / CheckBudget / RefreshBudget / Consume / Handoff / Done / WaitHuman / ResolveHuman / Cancel / Recover / SafeBootstrapTakeover / SafeTakeover / Takeover`。状态只能由脚本原子写入，模型不得手改。

## 用户可配置参数

`$env:USERPROFILE\.agents\double-session-common\double-session-config.json` 是以下三个参数的唯一真相源：

- `coder_interval_seconds`：coder 调度检查间隔；
- `planner_interval_seconds`：planner 调度检查间隔；
- `max_budget_seconds`：单个连续班次的最大预算。

四个入口启动调度前必须调用状态脚本的 `Config` 动作读取并校验配置，不得在 skill 或脚本中复制默认数值。配置必须恰好包含这三个整数字段；两个检查间隔须为整分钟，范围 60–3600 秒；预算范围 1–86400 秒。缺失、额外字段、非整数、越界或非法 JSON 一律 fail-loud，不静默回退。

调度启动时把对应检查间隔固化到本次 Goal/loop，作为最长兜底等待；支持 `WaitTurn` 的 adapter 可在合法交棒信号后提前复查。新 run 或新预算 segment 从配置读取预算并写入 state 作为运行时快照。普通运行中当前 segment 仍保持冻结；用户修改 JSON 后，在原同角色 session 重新输入对应 double 入口时调用 `RefreshBudget`：仅当 `max_budget_seconds` 确实变化才从调用时刻开启新 segment，保留 `run_id/turn/seq`、原 Goal/loop 与 `worker_token`；另一窗口随后重复调用因预算值已相同而 no-op，不重复刷新 deadline。检查间隔在各自入口重进时重新固化。`status/stop` 不依赖配置读取，配置写坏后仍可查看或终止现有 run。

## 共同不变量

1. 启动前把非空初始任务写入 repo 根 `temp.md`；只有 coder 可以调用 `Init` 创建新 run。既有 run 的轻量恢复使用原 session 的 `Recover`，不重复 `Init`。
2. 等待方只查看 state；`turn` 不属于自己时不得读取、清空或分析 `temp.md`。
3. 消费必须调用 `Consume`，让“校验冻结任务与 message snapshot → 读取 temp → 立即写空 → 验证长度为 0”在同一 repo 互斥锁内完成；成功返回前不得分析正文或调用其他工具。同 token 对已提交 `Consume` 的重试必须核验 `last_action_seq/message_seq/task/message` 后返回同一 `.copilot-message.md`，不重复推进状态；即使当前角色已把未交棒草稿写入非空 `temp.md`，也绝不能再次消费或清空该草稿。
4. 生产者先写完整正文并验非空，再 `Handoff` 或 `Done`。两者在同一 repo 互斥锁内先把正文原子落到 `.copilot-message.md`，记录 `message_sha256/message_seq`，再翻转 state。coder 只能交给 planner，planner 只能交给 coder，只有 planner 可以 `Done`。
5. 每轮所有者先 `CheckBudget`。达到当前 segment 从配置冻结的预算后转 `paused_budget`；若在工作中到期，先完成安全交棒再暂停。普通自动调度看到过期只暂停，不自行续开预算。用户在原 session 显式选择 Continue Goal、执行 `/goal resume` 或输入“继续”后，入口立即检查；若为 `paused_budget`，用原 token 调 `Recover`，从恢复时刻按当前配置开启下一 segment。若离线期间仍显示 `running` 但 deadline 已过，则先由当前 turn 的角色 `CheckBudget` 落成暂停，再在同次显式恢复中 `Recover`。该转换保留 `run_id`、`turn`、`seq`、冻结任务与 `temp.md`。
6. `paused_budget` 是同一 run 的可恢复暂停态，不是终态。Claude 原 session 复用 loop 上下文；Codex v2 Goal 从 objective 的 `worker_token=` 行恢复原绑定，不能依赖工具进程内的临时 `store()`。等待方只查 state、不得读 `temp.md`，恢复方成功 `Recover` 后两边回到正常轮次。历史 Goal 若未持久化 token，Continue Goal 不能无中生有恢复它，必须按下述兼容边界处理。
7. `done|cancelled|wait_human` 后禁止继续消费或修改任务产物。`wait_human` 是可恢复人工门，不是新任务：保留 `run_id`、冻结任务、`resume_turn` 与允许决议；只允许 `ResolveHuman` 原 run 恢复或 `Cancel` 终止。真正终态会记录 `temp.md` 哈希；新 run 要求 `temp.md` 非空、哈希已变化且修改时间晚于 state 的 `updated`，旧最终报告不得冒充新任务。v2 旧终态没有哈希时只用时间戳兼容。
8. 状态机使用 `coder|planner`。为在途旧 worker 暂时接受 `claude|codex` 参数别名并映射旧 turn；新写入升级为 v5，v4 在首次合法写入时惰性迁移并新增 `failure_ledger`。
9. v4 每个 run 固化 `owner_repo`；调度器固化 `ExpectedRepo + ExpectedRunId`，所有读取任务、temp、message 前先校验。漂移时报 `REPO_MISMATCH` 或 `RUN_MISMATCH`，拒绝继续。
10. 每个活跃角色窗口生成唯一 `worker_token`；state 只保存 token 的 SHA-256，不得通过 `Show` 泄漏原 token。Claude 把原 token 保留在原 loop/session 上下文；Codex 必须调用 `GoalContract`，把其完整 v2 输出逐字作为 Goal objective，使 token 与 repo/run/role 一起持久化。`store()` 只能是缓存。状态动作续租 `worker_lease_deadline`；第二个同角色 token 只得 `WORKER_ACTIVE`。宽松 `Takeover` 仍是人工应急能力，不是日常恢复主路径。
13. `GoalContract` 不改 state，只生成轻量、可持久化的 Codex Goal v2 objective。每次 Goal continuation 必须先按 objective 重新完整读取 live skill、公共 protocol 与 Config，之后才能碰 state；当前 live 文件覆盖 Goal 内旧流程文字。Goal 只有无新任务的 `done|cancelled` 才完成，不能因预算暂停、人工门、对方轮次、状态未变化或临时缓存为空而 `complete|blocked`。
14. `SafeTakeover` 只处理一个机械可证的丢 token 边界：当前正轮到本角色，且最后动作是对方完整提交的 Handoff，`phase/seq/message_seq/temp/message hash` 全部一致，本角色尚未 Consume。它只轮换本角色 lease，不推进 seq、不读取正文。任一条件不满足即拒绝，任务中途已 Consume 的跨 token 重建仍不支持自动化。
15. `SafeBootstrapTakeover` 只处理 coder 启动桥在 `Init` 成功、Goal 创建前失败留下的孤儿 run：必须同时满足 `running / turn=coder / seq=0 / phase=ready`、从未有 `last_action`、planner token 为空、冻结 task/message/temp 三方非空且哈希一致。它只重绑 coder lease，不推进 seq、不读取正文；任一条件不满足即拒绝。
11. 所有 mutating action 由 repo 级命名 mutex 串行化，状态迁移使用 `ready|working` phase；任务文件在 Consume/Handoff/Done/WaitHuman/ResolveHuman continue/rework 前必须重新核验 `task_sha256`。冻结任务损坏时仅 `Show/status` 与 `Cancel` 可用。
12. `WaitTurn` 是纯只读、有界等待：必须绑定 `ExpectedRepo / ExpectedRunId / Role / ObservedSeq` 与本次固化的检查间隔，等待期间不持有 repo mutex，不读 `temp.md`、不续租、不改 state。`Handoff/Done` 完整提交并释放 mutex 后才给对方发送命名事件；事件只是提示，醒后仍以 state 的 run/turn/seq/status 为准。伪信号继续等待剩余时长，丢信号或 signal 失败按固化间隔超时复查，不得把已提交交棒反报失败。

**调度等待纪律**：`state` 尚不存在、planner 正在监视 `wait_human`、`running + turn=对方`，以及一次检查后 state 未变化，都只是调度层的正常等待态，不等于执行阻塞。planner 必须保留本平台原生调度，按配置间隔持续复查；已绑定 run 的 Codex adapter 使用 `WaitTurn` 让合法交棒可提前结束等待，尚未绑定 run 的 planner 仍使用原生等待。`paused_budget` 则是有意停止自动续轮、等待用户显式恢复的可恢复态：Codex 保留原 Goal/绑定但不标 `complete|blocked`，Claude 删除 loop 但保留 session 绑定。除该预算暂停、用户显式停止和无新任务的 `done|cancelled` 外，不结束调度。

**Codex 状态动作沙箱纪律**（`STATE_ACTION_SANDBOX_FIRST=USE_DEFAULT`）：user-scope 状态脚本是只读入口，脚本位置不决定其 repo-local action 必须提权。Codex 对 `Config/GoalContract/Init/Show/WaitTurn/CheckBudget/RefreshBudget/Consume/Handoff/Done/WaitHuman/ResolveHuman/Recover/Cancel/SafeBootstrapTakeover/SafeTakeover/Takeover` 的第一次调用必须是 `login:false + workdir=<repo> + use_default` 的单一最小 `pwsh -NoProfile -File ... -Action <action>`，不捆绑管道、重定向或诊断。只有该命令明确返回 sandbox denial 才可对同一 action 做至多一次窄化提权；reviewer 拒绝、超时或无 assessment payload 不算 sandbox denial，也不得重试风暴。提权仍失败时保持 state 与产物原状，以 `STATE_ACTION_TRANSPORT_BLOCKED` 停止本轮；不得手改 state，planner 不得越权直接修改 coder 产物。

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

1. planner 入口先固化 repo 与配置中的检查间隔并建立本平台原生调度。`state` 不存在时立即进入“预启动监视”：不虚构或绑定 `run_id`，按配置间隔复查，直到 coder `Init` 后自动绑定新 run。首次只报告“已进入预启动等待；将在配置间隔后自动复查，无需再次输入 planner 启动指令”，不得直接退出。
2. 全新 planner session 看到遗留 `wait_human` 时，不重复制造三选一人工门、不绑定旧 `run_id`、不调用 `ForceInit`；只用 `Show -ExpectedRepo` 观察并按配置间隔复查，等待 coder `ResolveHuman` 或 `ForceInit`。已经绑定该 run 的 planner 同样保持等待，但保留旧绑定。若 coder `ForceInit` 后新 state 的 `replaced_run_id` 精确等于旧绑定且 `replaced_status=wait_human`，允许自动改绑新 `run_id`；其他 `RUN_MISMATCH` 仍须 fail-loud。
3. 无新任务的 `done|cancelled` 才结束 planner 调度。终态之后出现非空、哈希不同且时间更新的 `temp.md` 时，清除旧 run 绑定并进入预启动监视，等待 coder `Init`；只能查长度、`LastWriteTimeUtc` 和文件哈希，不得读取正文。
4. `wait_human` 时保持原生等待调度，只查看 state，等待合法控制入口；不得读取或清空 `temp.md`。`paused_budget` 时停止自动续轮但保留原 session 绑定，等待用户在原窗口显式“继续”并 `Recover`；不得要求新开 planner。
5. `running + turn=coder` 时等待；`running + turn=planner` 时先 `CheckBudget -Role planner`，再 `Consume -Role planner`。
6. **审核自主阶梯**：读取冻结任务与 coder 交接后，依次执行，不得跳步直接 REWORK 或 `WaitHuman`：
   1. 自己检查实际文件、Git diff、测试输出与现有证据，不得只信 coder 自述；
   2. 存在合理替代路径时，至少做一次替代性只读复验，例如重新核对 `done_when`、换工具读取或交叉比对；
   3. 仍属重大、高影响且证据支持多个解释的低置信判断时，调用一次性只读 mc-expert；普通缺证据直接进入下一步；
   4. 只有 coder 能补证据或做定向修复时，才发 REWORK；
   5. 只有命中共用段第 4 条允许的人工门，才进入 `WaitHuman`。
7. `REWORK`：写可执行意见、验非空、`Handoff -Role planner -To coder`。每份 REWORK 必须包含：稳定阻塞点编号 `B-xxx`；实际观察到的事实；缺少的证据或未满足的 `done_when`；coder 下一步具体取证/修复动作；验收方式；允许修改范围；当前 `attempt 1/2` 或 `attempt 2/2`。同时续传三个累积清单，不得以“再看看”代替可执行指令。
8. `PASS`：只有整个冻结任务的 `done_when` 均有实际证据，且剩余 `PENDING_HUMAN_NONBLOCKING` 确认不阻断验收时，才写最终证据并一次性汇报累积的自主裁决与待人工事项，验非空后 `Done -Role planner`。任何阻断 `done_when` 的待人工事项都不得以清单形式带过或伪装成 `PASS`。
9. 第一次收到某 `failure_key` 必须自己核查证据并给出可执行 REWORK，不得 `WaitHuman`。只有 state 中同 key 的独立 coder 报告数达到 2，planner 才可不写 `temp.md` 调用 `WaitHuman -Role planner -Reason <自足摘要>`。approval pass 必须落 `outcome=approval_pass, decision_by=approval_entry`，不冒充 planner 独立 PASS。

## 人工控制与恢复

- 四入口接受中文短命令 `状态/继续/返工/通过/取消/接管`，分别对应 `status/continue/rework/pass/cancel/takeover`。只有用户本轮明确输入控制词时才执行，模型不得看到 `wait_human` 或预算暂停后自行开启新班次。
- `状态` 只调用 `Show` 并投影状态，不创建 Goal/loop、不刷新租约、不迁移状态。
- 既有同角色 session 在普通中断或 `paused_budget` 下输入“继续”，复用已持久绑定的 Goal/loop、repo、run、role 与 token：`running` 立即检查，`paused_budget` 调 `Recover` 后立即检查。对 `DOUBLE_SESSION_GOAL_CONTRACT=v2` 的 Codex Goal，Continue Goal 与同 session“继续”均走此路径；历史 Goal 必须先确认 objective 确实含明文 token，不能把客户端恢复 transcript 误当成恢复工具临时内存。
- `wait_human` 是不同语义：既有同角色 session 输入 `继续/返工/通过` 时，入口从当前绑定 state 内部取得一次性 `human_approval_id` 并传给 `ResolveHuman`；全新或丢失上下文 session 仍须使用 `resume <decision> <human_approval_id>`，裸“继续”不得猜 run 或隐式 takeover。
- 全新 coder session 发现同 repo 遗留 `wait_human` 时，必须显示旧 run 摘要并让用户明确选择：`恢复旧任务 / 取消旧任务并强制初始化 / 保留人工门并退出`。不得默认选择，不创建 Goal/loop。只有 coder 入口在用户本轮明确选择第二项后，才可用旧 run、repo 与当前 approval id 调 `ForceInit`。全新 planner session 不重复询问或退出，按“planner 唯一流程”进入预启动监视；它仍不得自行恢复、`ForceInit` 或消费新任务。
- `ForceInit` 只接受 `wait_human`，要求非空且较旧 state 更新、hash 不同的新 `temp.md`，在 repo mutex 内冻结新任务并创建全新 coder run；新 state 记录 `replaced_run_id/replaced_status/replaced_at` 并清空旧批准编号与 ledger。旧窗口随后必须因 `RUN_MISMATCH` 被拒绝。其他状态调用或未检测到新任务均拒绝。
- `继续` 分态：`wait_human` 按批准编号恢复同一 run；`paused_budget` 由原 session 的本角色用原 token `Recover` 开新 segment；`running` 立即检查但不重复创建调度器；`done|cancelled` 拒绝复活。非 `resume_turn` 角色不得扮演另一角色。
- 原 session 重新输入对应 double 入口时，先 `Config`，再以既有绑定调用 `RefreshBudget`；不得创建新 Goal/loop、`Init` 或新 token。配置预算未变化时该动作不写 state；变化时只开启一次新 segment。随后若仍为 `paused_budget`，再按“继续”规则 `Recover`。
- `stop` 入口只调用 `Cancel`；允许从 `running|paused_budget|wait_human` 终止，同一 scheduler 下次 tick 看到 `cancelled` 必须退出。重复 stop 幂等返回原 cancelled 状态；done 后 stop 明确返回 `CANCEL_NOT_ALLOWED_DONE`。脚本只记录 `decision_by=control_entry`。
- `continue|rework|pass|cancel` 只能用于当前 `wait_human` 的 `allowed_resolutions`，并必须提交匹配的一次性 `human_approval_id`；不匹配即拒绝，成功后立即清空 id。
- 新建 Codex Goal 前必须调用 `GoalContract`，并把 stdout 逐字交给 `create_goal`。v2 Goal 使用 Continue Goal、`/goal resume` 或同 session“继续”恢复；`/goal clear` 会删除持久 token，禁止把它作为 v2 日常恢复步骤，只能在 run 已终态或用户明确放弃旧任务后使用。
- `CODEX_GOAL_BRIDGE_V1`：全新 run 保持“生成 token → `Init` → `GoalContract -CodexJsonEnvelope` → 校验信封 → `store()` 缓存绑定 → `create_goal`”的既有顺序。本次桥接失败留下的 `seq=0` 孤儿 run 走唯一例外：“生成 token → 用精确 run 调 `GoalContract -CodexJsonEnvelope` → 校验信封 → `store()` → `create_goal` → 成功后才调 `SafeBootstrapTakeover`”；这样修复当前残留而不改变普通新 run 架构。嵌套 `shell_command` 必须使用 `login:false`；PowerShell 必须捕获并禁止中间 stdout，只把 `CodexJsonEnvelope` 的单行压缩 JSON 作为唯一 payload。JavaScript 只允许从 shell 返回值的 `Output:` 段提取该唯一 JSON 行并直接 `JSON.parse`；`env.envelope` **必须精确等于** `DOUBLE_SESSION_CODEX_GOAL_ENVELOPE=v1`，不得拿流程名 `CODEX_GOAL_BRIDGE_V1` 代替字段值。随后逐项核验 `repo/run_id/role`，并确认 `goal_objective` 首行为 `DOUBLE_SESSION_GOAL_CONTRACT=v2`、其中 token 与信封完全一致；不得把信封或 token 传给 `text/image/audio/notify`。严禁 Base64、`atob`、`btoa`、`Buffer` 或其他自创编码桥；当前 `functions.exec` V8 环境不保证这些 API 存在。`store()` 只是同 session 故障缓存，不能替代 Goal objective。
- Codex double 入口的恢复判断顺序固定为 `读 live skill/protocol → Config → Show live state → get_goal → 决策`。`Show` 前禁止用 transcript、旧工具输出或 Goal objective 推断当前 status/turn/seq；旧 Goal 为 `complete` 也不能覆盖 live state 已处于本角色安全 Handoff 边界的事实。
- 历史 Goal 兼容边界：objective 含精确 repo/run/role/token 时，重新输入当前 `$double-coder` / `$double-planner` 可用旧 token、但按 live skill/protocol 行为恢复；objective 缺 token 时必须报 `TOKEN_BINDING_LOST`，不能完成 Goal或猜 token。若旧 Goal已终止且 state 正处于对方完整 Handoff 给本角色的未消费边界，可用新 token `SafeTakeover` 并创建 v2 Goal；其余跨 token 中途恢复仍留作未来升级。
- 唯一一次性历史迁移例外：旧 Codex planner Goal 已 `paused`、无法由现有 Goal 工具原地更新 objective，且 live state 正轮到 coder 时，用户可明确执行一次 `/goal clear` 后重输 `$double-planner`。新 planner Goal 只持久化新 token并 `WaitTurn`，不抢 planner lease；收到 coder 完整 Handoff 后才 `SafeTakeover`。这不是 v2 日常恢复步骤，不扩展到任意中途接管。
- 自动找回任意旧 token、已 Consume 后跨 token 重建、事件日志或完整审计仍属于未来升级入口。显式 `Takeover -HumanApprovalId takeover:<run_id>` 仅保留为人工应急命令，不应写成日常恢复流程。
- 所有后续动作都传 `ExpectedRepo`、`ExpectedRunId`、`WorkerToken`；`Show/status` 至少传前两项。唯一例外是尚未绑定 run 的 planner 预启动监视：只传 `ExpectedRepo`，观察到可绑定的 `running|paused_budget` 后立即固化 `ExpectedRunId`。

## 常用命令

```powershell
$repo = (& git rev-parse --show-toplevel).Trim()
$workerToken = [guid]::NewGuid().ToString('N')
$state = pwsh -NoProfile -File $stateTool -Action Init -ExpectedRepo $repo -WorkerToken $workerToken | ConvertFrom-Json
$runId = $state.run_id
$goalObjective = pwsh -NoProfile -File $stateTool -Action GoalContract -Role coder -ExpectedRepo $repo -ExpectedRunId $runId -WorkerToken $workerToken
pwsh -NoProfile -File $stateTool -Action Show -ExpectedRepo $repo -ExpectedRunId $runId
pwsh -NoProfile -File $stateTool -Action WaitTurn -Role coder -ObservedSeq $state.seq -TimeoutSeconds 3600 -ExpectedRepo $repo -ExpectedRunId $runId
pwsh -NoProfile -File $stateTool -Action CheckBudget -Role coder -ExpectedRepo $repo -ExpectedRunId $runId -WorkerToken $workerToken
pwsh -NoProfile -File $stateTool -Action Consume -Role coder -ExpectedRepo $repo -ExpectedRunId $runId -WorkerToken $workerToken
pwsh -NoProfile -File $stateTool -Action Handoff -Role coder -To planner -ExpectedRepo $repo -ExpectedRunId $runId -WorkerToken $workerToken
```

planner 使用自己生成的 `$workerToken`，并同样传三项绑定。`ResolveHuman` 还必须传 state 中本次待裁决的 `-HumanApprovalId`；`Cancel` 记录控制入口来源而非不可证明的人类身份。
