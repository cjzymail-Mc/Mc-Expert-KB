---
name: double-coder
description: 让 Codex 在当前 Git repo 中担任双窗口接力 coder。用户显式调用 $double-coder 后创建最长 3 小时的 active Goal，采用深度授权 B 模式执行或恢复任务，每 5 分钟检查；可搭配 Claude 或 Codex 的 double-planner。
---

# `$double-coder`

先完整读取 repo 启动链和 `$env:USERPROFILE\.agents\double-session-common\protocol.md`，然后严格执行其中“coder 唯一流程”。公共核心缺失时 fail-loud；不得复制协议、回退 Claude skill 目录或手改 `.copilot-state.json`。

## Codex 机制适配

- 状态脚本固定为 `$env:USERPROFILE\.agents\double-session-common\double-session-state.ps1`，角色固定为 `coder`。
- 使用 active Goal 保持续轮。若已有无关 unfinished Goal，停止并报告，不得覆盖或先调用 `Init`。
- Goal objective 必须写明公共 coder 流程、每次先查 state、未轮到时原生等待 300000 ms、班次暂停或终态即结束；不得用 shell 常驻循环、sleep、后台进程代替。
- 命中公共陪审扳机时，先完整读取 `$env:USERPROFILE\.agents\skills\_mc-common\codex-runtime-bindings.md` 与 `$env:USERPROFILE\.codex\agents\mc-expert.toml`，再用 native custom agent `mc-expert`、`fork_turns=none`、四字段合同做一次性只读陪审。无 native surface 或连续两次终态失败时按公共协议 `WaitHuman`；不得用 `codex exec` 冒充。
- 自主接力中不得请求普通用户决策。普通可逆事项按公共协议默认顺序自走并记录；权限动作后置，真正人工硬门非阻塞停机。

## 启动 Goal

1. 确认无冲突 Goal后创建 active Goal。
2. 调 `Init`。新 run 要求 `temp.md` 是晚于旧终态的新任务；未过期的 running 只恢复，`paused_budget` 原位开启下一班次；中断遗留的 `running + turn=coder + deadline 已过` 由公共状态脚本在本次 `Init` 中原子开启下一班次，不得要求用户再次调用 skill。
3. 立即进入“检查循环”。

## 检查循环

1. 调 `CheckBudget -Role coder`。
2. `done`：完成 Goal。`wait_human`：停止 Goal并报告 reason。`paused_budget`：完成本班次 Goal，提示再次启动任一平台 coder；已启动的 planner 保持等待，无需在 coder 完成后人工重启。
3. `running + turn=planner`：原生等待 5 分钟后复查，不碰 `temp.md`。
4. `running + turn=coder`：完整执行公共协议的 coder 正常轮；安全交棒后若返回暂停，结束本班次 Goal。

公共协议的 `WaitHuman` 路径必须“不写 temp、不交棒 → reason 落 state → 验状态 → 停止 Goal并对话报告”。只有 planner 可以最终 `Done`。
