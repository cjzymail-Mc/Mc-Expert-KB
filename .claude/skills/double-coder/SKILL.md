---
name: double-coder
description: 让 Claude 在当前 Git repo 中担任双窗口接力 coder。用户输入 /double-coder 后，按公共 JSON 配置和 coder 协议采用深度授权 B 模式执行或恢复任务；可搭配 Claude 或 Codex 的 double-planner。
---

# `/double-coder`

先完整读取 repo 启动链和 `$env:USERPROFILE\.agents\double-session-common\protocol.md`，然后严格执行其中“coder 唯一流程”。公共核心缺失时 fail-loud；不得复制协议、回退另一平台目录或手改 `.copilot-state.json`。

## Claude 机制适配

- 状态脚本固定为 `$env:USERPROFILE\.agents\double-session-common\double-session-state.ps1`，角色固定为 `coder`。
- 除 `status/stop` 外，启动或恢复调度前先调用状态脚本 `-Action Config`，读取唯一配置；将 `coder_interval_seconds` 精确换算成整分钟的 Claude `/loop <N>m` 参数。配置读取或校验失败即停，不得使用 skill 内默认值。原 session 重新输入 `/double-coder` 时，再用既有绑定调用 `RefreshBudget`；预算未变化为 no-op，变化时从此刻开启一个新 segment。
- 陪审命中公共协议扳机时，用一次性只读 `Task(mc-expert)`；调用正文必须交齐公共协议规定的四字段。不得建立常驻 teammate。调用失败也不得 `WaitHuman`，须把证据交给 planner。
- 自主接力中不得调用 `AskUserQuestion`。普通决策直接按公共协议默认顺序自走；真正人工硬门走非阻塞 `WaitHuman`。
- 周期调度只用 Claude Code 内建 `/loop`，间隔使用本次从配置固化的具体 `<N>m`。job 提示词以唯一标记 `[double-coder]` 开头，并要求执行本 skill 的“单轮调度”；禁止 shell 常驻循环或 `Start-Sleep`。
- `running + turn=planner` 与连续多轮 state 不变都是正常等待；必须保留 `[double-coder]` loop，不得据此停掉调度或要求用户重新启动 coder。

## 启动

0. 解析 `状态/继续/返工/通过/取消/接管`（兼容原英文入口）。普通中断下，既有本角色 session 的“继续”只恢复其既有 run/role/token；`wait_human` 下的短命令才内部使用当前批准编号。全新或丢失上下文 session 必须显式 `resume <decision> <human_approval_id>`，裸“继续”不得猜 run、token 或 takeover；终态拒绝复活。
1. 调 `Config` 并固化本次 coder loop 间隔。已有本角色绑定时复用 repo/run/token；若本轮由 `/double-coder` 重进，调用一次 `RefreshBudget`。只有新 run 才生成 `worker_token` 并调用 `Init`。此后每个动作都传 `ExpectedRepo / ExpectedRunId / WorkerToken`；token 不匹配时报 `WORKER_ACTIVE`，不隐式 takeover。
2. 用户在原 session 输入“继续”显式恢复时：先查 state；`running` 立即执行单轮，`paused_budget` 用原 token 调 `Recover` 后立即执行单轮。离线过期但 state 仍为 `running` 时，由当前 turn 的检查先落成暂停，再在同次显式恢复里 `Recover`。自动 loop 不得自行续开预算。
3. 立即执行一次“单轮调度”。
4. 若仍为 running，注册唯一 `[double-coder]` loop 并报告 job id。

## 单轮调度

1. 调 `CheckBudget -Role coder`。
2. `done|cancelled|wait_human|paused_budget`：不得读 `temp.md`；用 `CronList`/`CronDelete` 取消本 session 唯一 `[double-coder]` job。`wait_human` 报告允许的 resume decision；预算暂停时保留原 session 绑定，提示在两个原 session 输入“继续”，不得要求新开窗口或换 token。
3. `running + turn=planner`：结束本轮，只等 state；不得碰 `temp.md`。无论连续等待多少轮都保留本 session 唯一 `[double-coder]` loop。
4. `running + turn=coder`：完整执行公共协议的 coder 正常轮。安全交棒后若返回 `paused_budget`，立即取消 loop。
5. coder 永久禁止 `WaitHuman`；失败必须以 `HandoffKind failure + FailureKey` 交给 planner。

只有 planner 可以最终 `Done`；Claude coder 不得自行宣告整体通过。
