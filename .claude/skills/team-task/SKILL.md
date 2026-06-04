---
name: team-task
description: 用 Agent Team 执行任务的入口（类似 /today）。读取当前 repo 根目录的 team-task.md，先让用户选驱动模式（A 人工驱动 / B 深度放权），再按其建一个三角色协调小队（planner / mc-expert / coder）、维护根目录 team-progress.md，然后执行 team-task.md 的「本次任务」。用户输入 /team-task 时触发。
---

# team-task

把"启用 agent team 干一件事"固化成一个命令。等价于 `/today`，但目标文件是 `team-task.md`、且强制走 team 工作流。

## 触发后立刻做

1. **读当前 repo 根目录的 `team-task.md`**（`./team-task.md`）。读不到就停下报告"本 repo 根目录没有 team-task.md"，不要瞎建队。
2. **先读完整份**——它定义了第 0 步驱动模式选择、团队结构、team-progress.md 规则、落点规范、边界。
3. 看「本次任务」是否填了内容：
   - **空** → 告诉用户"team-task.md 的『本次任务』是空的，请先填写"，不要自己编任务。
   - **有** → 先归档上一轮 team-progress、再走第 0 步，然后建队执行。
4. **归档上一轮 team-progress（建队前，按 team-task.md 通用要求执行）**：把根 `team-progress.md` 复制进 `team-progress/team-progress-{NNN}.md`（流水号取现有最大 +1，补零三位），再把根文件重置为带面包屑的最小骨架。根文件不存在/空骨架则跳过。（team-task.md 通用要求无此步的 repo 直接跳过。）
5. **第 0 步（建队前强制）**：按 team-task.md，用 AskUserQuestion 让用户二选一驱动模式 **A 人工驱动 / B 深度放权**，选定前不许建队。

## 建队执行（严格照 team-task.md 通用要求）

- 前提：本 repo 已开 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`。若用自然语言建队后没 spawn 出 teammate，提示用户确认开关已开 + CC ≥ v2.1.32（`claude --version`）。
- 用自然语言建一个 team：planner（只读规划）/ mc-expert（带 KB 挑战，只读顾问）/ coder（含 Edit/Write）。关键背景写进 spawn prompt（teammate 不继承 lead 对话历史）。
- **放权深度**：按 team-task.md 第 0 步的 A/B 选择执行，skill 不在此另定（单一事实源在 team-task.md）。
- **team-progress.md**：lead 当唯一写手，teammate 经 mailbox 汇报、lead 汇总落根目录 `team-progress.md`；只读角色不自己写文件。
- 收尾让 **lead** 跑 `Clean up the team`（先 shutdown 所有 teammate）。

## 不要做

- 不复述 team-task.md 全文，直接说"开始执行 X"后动手。
- 不让 teammate 碰编排权 / 替用户做「推翻已封决策」级判断。
- 不跳过第 0 步的 A/B 选择（选 A 时还需逐决策点等用户拍板；选 B 时 lead 自主审批，仅高风险/连失 2 次上报）。

> 机制细节、为什么这样设计：见 KB `Mc-Expert-repo/references/agent-teams.md`「新手 FAQ」+ `Mc-emoji/[feature-03-take-a-nap]/sub-plan-stage3-agentteam-spike.md`。
