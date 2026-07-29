---
name: double-planner
description: 让 Codex 在当前 Git repo 中担任双窗口接力 planner。用户显式调用 $double-planner 后创建最长 3 小时的 active Goal，每 10 分钟检查并审核 coder 的真实成果；可搭配 Claude 或 Codex 的 double-coder。
---

# `$double-planner`

先完整读取 repo 启动链和 `$env:USERPROFILE\.agents\double-session-common\protocol.md`，然后严格执行其中“planner 唯一流程”。公共核心缺失时 fail-loud；不得复制协议、回退 Claude skill 目录或手改 `.copilot-state.json`。

## Codex 机制适配

- 状态脚本固定为 `$env:USERPROFILE\.agents\double-session-common\double-session-state.ps1`，角色固定为 `planner`。
- 使用 active Goal 保持续轮。若已有无关 unfinished Goal，停止并报告，不得覆盖。
- Goal objective 必须写明 reviewer-only、公共 planner 流程、每次先查 state、未轮到或 `paused_budget` 时原生等待 600000 ms、仅 `done|wait_human` 终态结束；状态变化只能调用公共脚本。
- 不得用 shell `while`、sleep、后台进程或 `codex exec` 代替 Goal/native wait。

## 检查循环

1. state 不存在时等待 coder 初始化。终态后仅当 `temp.md` 非空、文件哈希不同于 `terminal_temp_sha256` 且 `LastWriteTimeUtc` 晚于 state `updated`，才视为“新任务待 Init”；v2 无终态哈希时只比时间。不得读取正文或自行初始化。
2. 调 `CheckBudget -Role planner`。
3. `done`：完成 Goal。`wait_human`：停止 Goal并报告 reason，不伪造完成。
4. `paused_budget`：保持 Goal，原生等待 10 分钟后复查，只等 coder `Init`，不碰 `temp.md`。
5. `running + turn=coder`：原生等待 10 分钟后复查，不碰 `temp.md`。
6. `running + turn=planner`：完整执行公共协议的 planner 单轮；安全交棒若返回暂停则转入等待，不结束 Goal。

连续两次评审机制失败或命中四红线时，严格走公共协议的 planner `WaitHuman` 路径。
