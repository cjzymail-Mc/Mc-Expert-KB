---
name: team-task-api
description: 降级版 Agent Team 执行入口（team-task 的 api 变体）。和 /team-task 完全同流程（读 repo 根 team-task.md、选驱动模式 A/B、planner/mc-expert 协作、维护 team-progress.md），唯一差别是执行者从原生 coder 换成 coder-api——经确定性门脚本 ~/.claude/scripts/run_cn_task.ps1 驱动外部模型 cn（Continue CLI，默认 GLM-5.1，走用户自己的 API）干活、回传摘要。用于简单任务省 Claude 套餐 token + 对比不同模型 API 能力。用户输入 /team-task-api 时触发。
---

# team-task-api

`/team-task` 的**降级版**：流程一字不差，**唯一差别是执行者** = `coder-api`（驱动外部模型 cn，不 spawn cn 为 teammate，lead 经门脚本 `~/.claude/scripts/run_cn_task.ps1` 调用）。设计与锁定决策见 `Mc-emoji/[feature-03-take-a-nap]/coder-api第二套team-实现交接spec.md`。

## 触发后立刻做（同 team-task）

1. **读当前 repo 根目录的 `team-task.md`**（`./team-task.md`）。读不到就停下报"本 repo 根目录没有 team-task.md"，不瞎建队。
2. **先读完整份**——它定义第 0 步驱动模式、团队结构（含「执行者变体」段）、team-progress.md 规则、落点、边界。
3. 看「本次任务」是否填了内容：**空** → 让用户先填，不自己编；**有** → 先归档上一轮 team-progress、再走第 0 步，然后建队执行。
4. **归档上一轮 team-progress**（建队前，按 team-task.md 通用要求）：根 `team-progress.md` 复制进 `team-progress/team-progress-{NNN}.md`（流水号 +1 补零三位），根文件重置为带面包屑的最小骨架；不存在/空骨架则跳过。
5. **第 0 步（建队前强制）**：按 team-task.md，用 AskUserQuestion 让用户二选一 **A 人工驱动 / B 深度放权**，选定前不许动手。

## 执行（与 team-task 唯一的不同：执行者 = coder-api）

- planner（只读规划）/ mc-expert（带 KB 挑战，只读顾问）**照常**——可作原生 teammate 或 lead 直接驱动，按 repo 的 Agent Teams 可用性定。
- **执行者不是原生 coder，而是 `coder-api`**（user 级 agent，model=sonnet）：它**不亲自写业务代码**，经门脚本驱动 cn 实现，再把结果**摘要**回传。**cn 是 team 外无状态工具、不 spawn 为 teammate**——这是 team-task.md「边界」所说的「team 外手工编排」。
- **唯一调用方式（铁律）**：禁止直接 `cn -p`，一律经
  `pwsh -File "$HOME\.claude\scripts\run_cn_task.ps1" -Task "<原文>" -WorkDir "<绝对路径>" [-ConfigPath <每模型一个 config>] [-TargetFiles a,b]`。
  门脚本负责：首字节路由（`50 4B`→python / `88 7D 1C`→自动直穿 COM helper / 未知→停）、注入 15 行 guardrail、产物落 `C:\Temp\`、退出码、调用日志 `C:\Temp\cn-calls.log`。
- **能力边界**：T0 纯文本直接交 cn；T1（主力）加密/明文 Office 只让 cn **调已测 helper 黑盒**、不自写 COM、不直接 open 文件；越界（无现成 helper 的新 COM）→ 停下回报，让 Claude 先建+测 helper。
- **后验留 Claude 侧**：cn 产物在 `C:\Temp\`，核验首字节明文 magic 后才能 promote 到 `[feature-XX]/output/`；连失 2 次熔断。
- **team-progress.md**：lead 唯一写手；coder-api 经汇报、lead 落盘。收尾 lead 跑 `Clean up the team`。

## ⚠️ 用前必看（真实项目的数据外发红线）

coder-api 会把**任务文本 / 文件内容**发到外部 cn（GLM）API。**含客户机密 / 对外交付物的真实项目，别走 api 变体，留默认 `/team-task`（原生 coder）。** api 变体定位是「学习探索 repo 省 token + 模型对比」。python 明文/外发的合规边界见 spec 的「合规红线」与根 CLAUDE.md「实测发现」卡。

## 不要做

- 不复述 team-task.md 全文，直接动手。
- 不让 cn 自写 COM / 直接 open Office / 自由填输出路径或选 Dispatch 模式（护栏全在门脚本 + Claude 侧）。
- 不跳过第 0 步 A/B 选择；不让 teammate 碰编排权。

> 机制与锁定决策：`Mc-emoji/[feature-03-take-a-nap]/coder-api第二套team-实现交接spec.md`（含门脚本、guardrail、coder-api.md 全文 + phase-2 多代理路线）。team-task 母版见同级 `team-task` skill。
