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
| `.copilot-state.json` | `status`、`turn=coder|planner`、`seq`、3 小时预算、时间与任务哈希 |
| `temp.md` | 当前唯一一棒的交接正文 |

```powershell
$commonRoot = Join-Path $env:USERPROFILE '.agents\double-session-common'
$stateTool = Join-Path $commonRoot 'double-session-state.ps1'
pwsh -NoProfile -File $stateTool -Action Show
```

支持：`Init / Show / CheckBudget / Consume / Handoff / Done / WaitHuman`。状态只能由脚本原子写入，模型不得手改。

## 共同不变量

1. 启动前把非空初始任务写入 repo 根 `temp.md`；只有 coder 可以调用 `Init` 创建或恢复 run。
2. 等待方只查看 state；`turn` 不属于自己时不得读取、清空或分析 `temp.md`。
3. 消费必须调用 `Consume`，让“读取 → 立即写空 → 验证长度为 0”在一次调用内完成；成功返回前不得分析正文或调用其他工具。
4. 生产者先写完整正文并验非空，再 `Handoff` 或 `Done`。coder 只能交给 planner，planner 只能交给 coder，只有 planner 可以 `Done`。
5. 每轮所有者先 `CheckBudget`。3 小时到期转 `paused_budget`；若在工作中到期，先完成安全交棒再暂停。恢复时由任一平台的 coder 调用 `Init`：`paused_budget` 原位开启下一段；若中断遗留为 `running + turn=coder` 但 deadline 已过，`Init` 在同一次启动中原子开启下一段，不要求用户二次调用。该转换保留 `run_id`、`turn`、`seq`、冻结任务与 `temp.md`。
6. `paused_budget` 是同一 run 的可恢复暂停态，不是终态。已经启动的 planner 必须保留原生等待调度，只查 state、不得读 `temp.md`，等待 coder `Init` 后自动回到正常轮次；不得要求用户在 coder 完成后再次手工启动 planner。
7. `done|wait_human` 后禁止继续消费或修改任务产物。终态会记录 `temp.md` 哈希；新 run 要求 `temp.md` 非空、哈希已变化且修改时间晚于 state 的 `updated`，旧最终报告不得冒充新任务。v2 旧终态没有哈希时只用时间戳兼容。
8. 状态机 v3 使用 `coder|planner`。为在途 v2 worker 暂时接受 `claude|codex` 参数别名，并映射旧 state turn；新写入统一升级为 v3。

## coder 唯一流程

coder 采用深度授权 B 模式，但不调用 `/free` 或 `$free`，也不运行其 finalizer：

1. 全程禁止 `AskUserQuestion` 或等价的中途用户问询。普通可逆决策按“已封默认 > 历史成功率 > 最易回滚”自主执行，并记入交接。
2. 只在重大技术选型、修改核心配置/agent/skill/已封决策相关文件、拆分任务前、第一次实质失败后准备第二次尝试、或高风险/低置信/验证未闭的关键交棒前，启动一次性只读 mc-expert；普通机械修改不调用，不建常驻 agent。
3. mc-expert 调用必须在 `Consume` 和读取冻结任务之后、修改之前，交齐 `REVIEW_TARGET / PROJECT_MEMORY / SEALED_DECISION_QUERY / REVIEW_QUESTION`，且一次只问一个问题。调用终态失败最多重试一次；第二次失败按两连失熔断。
4. B 模式中途不主动发起删除、无备份覆盖、敏感目录、对外交付等会卡权限的动作。非硬依赖事项写入“待人工处理”；若命中四红线、任务硬依赖的用户授权、用户明示本人批准门或两连失，走下面的 `WaitHuman`。 非硬门的判断类疑问不得直接 `WaitHuman`：必须先按第 2–3 条调用 mc-expert；若陪审可用但仍无可执行结论，写完整交接并 `Handoff -Role coder -To planner`。mc-expert 连续两次终态失败仍按“两连失”熔断，直接走 `WaitHuman`。
5. 正常轮：`CheckBudget -Role coder` → `Consume -Role coder` → 读 `.copilot-task.md` → 实施与验证 → 写 `temp.md`，包含完成项、改动路径、验证、遗留问题、审核重点、陪审结论、自主裁决、待人工处理 → 验非空 → `Handoff -Role coder -To planner`。
6. `WaitHuman`：不得写 `temp.md`、不得 `Handoff`；状态脚本会机械拒绝非空 `temp.md`。调用 `WaitHuman -Role coder -Reason <自足摘要>`，reason 写明阻止动作、成果路径、验证和唯一待批准事项；验明 state 后停止自己的调度器并在当前对话报告。

## planner 唯一流程

planner 只审核，不替 coder 修改任务产物：

1. 未初始化，或终态之后出现非空、哈希不同且时间更新的 `temp.md` 时，等待 coder `Init`；只能查长度、`LastWriteTimeUtc` 和文件哈希，不得读取正文。
2. `paused_budget` 时保持原生等待调度，只查看 state，等待 coder `Init`；不得读取或清空 `temp.md`，不得退出并要求用户稍后重启 planner。
3. `running + turn=coder` 时等待；`running + turn=planner` 时先 `CheckBudget -Role planner`，再 `Consume -Role planner`。
4. 读取冻结任务，检查实际文件、Git diff 与必要验证，不得只信 coder 自述。
5. `REWORK`：写可执行意见、验非空、`Handoff -Role planner -To coder`。`PASS`：只有整个冻结任务完成才写最终证据、验非空、`Done -Role planner`。
6. 红线或两连失时不写 `temp.md`，调用 `WaitHuman -Role planner -Reason <自足摘要>` 并停止调度器。

## 常用命令

```powershell
pwsh -NoProfile -File $stateTool -Action Init
pwsh -NoProfile -File $stateTool -Action Show
pwsh -NoProfile -File $stateTool -Action CheckBudget -Role coder
pwsh -NoProfile -File $stateTool -Action Consume -Role coder
pwsh -NoProfile -File $stateTool -Action Handoff -Role coder -To planner
pwsh -NoProfile -File $stateTool -Action CheckBudget -Role planner
pwsh -NoProfile -File $stateTool -Action Consume -Role planner
pwsh -NoProfile -File $stateTool -Action Handoff -Role planner -To coder
pwsh -NoProfile -File $stateTool -Action Done -Role planner
```
