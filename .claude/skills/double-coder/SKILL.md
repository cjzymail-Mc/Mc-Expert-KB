---
name: double-coder
description: 让 Claude 在当前 Git repo 中担任双窗口接力 coder。用户输入 /double-coder 后，按公共 coder 协议采用深度授权 B 模式执行或恢复任务，并用 Claude /loop 每 5 分钟检查；可搭配 Claude 或 Codex 的 double-planner。
---

# `/double-coder`

先完整读取 repo 启动链和 `$env:USERPROFILE\.agents\double-session-common\protocol.md`，然后严格执行其中“coder 唯一流程”。公共核心缺失时 fail-loud；不得复制协议、回退另一平台目录或手改 `.copilot-state.json`。

## Claude 机制适配

- 状态脚本固定为 `$env:USERPROFILE\.agents\double-session-common\double-session-state.ps1`，角色固定为 `coder`。
- 陪审命中公共协议扳机时，用一次性只读 `Task(mc-expert)`；调用正文必须交齐公共协议规定的四字段。不得建立常驻 teammate。调用终态失败最多重试一次，第二次按协议 `WaitHuman`。
- 自主接力中不得调用 `AskUserQuestion`。普通决策直接按公共协议默认顺序自走；真正人工硬门走非阻塞 `WaitHuman`。
- 周期调度只用 Claude Code 内建 `/loop 5m`。job 提示词以唯一标记 `[double-coder]` 开头，并要求执行本 skill 的“单轮调度”；禁止 shell 常驻循环或 `Start-Sleep`。

## 启动

1. 调 `Init`。新 run 要求 `temp.md` 是晚于旧终态的新任务；未过期的 running 只恢复，`paused_budget` 原位开启下一班次；中断遗留的 `running + turn=coder + deadline 已过` 由公共状态脚本在本次 `Init` 中原子开启下一班次，不得要求用户再次调用 skill。
2. 立即执行一次“单轮调度”。
3. 若仍为 running，注册唯一 `[double-coder]` loop 并报告 job id。

## 单轮调度

1. 调 `CheckBudget -Role coder`。
2. `done|wait_human|paused_budget`：不得读 `temp.md`；用 `CronList`/`CronDelete` 取消本 session 唯一 `[double-coder]` job。暂停时告诉用户再次启动任一平台 coder；已启动的 planner 会保留等待调度，无需在 coder 完成后人工重启。
3. `running + turn=planner`：结束本轮，只等 state；不得碰 `temp.md`。
4. `running + turn=coder`：完整执行公共协议的 coder 正常轮。安全交棒后若返回 `paused_budget`，立即取消 loop。
5. 公共协议的 `WaitHuman` 路径必须“不写 temp、不交棒 → reason 落 state → 验状态 → 取消 loop → 对话报告”。

只有 planner 可以最终 `Done`；Claude coder 不得自行宣告整体通过。
