---
name: team-task-api
description: 降级版 Agent Team 执行入口（team-task 的 api 变体）。和 /team-task 完全同流程（读 repo 根 team-task.md、选驱动模式 A/B、planner/mc-expert 协作、维护 team-progress.md），唯一差别是执行者改为 lead 直驱确定性门脚本 ~/.claude/skills/team-task-api/run_cn_task.ps1 调外部模型 cn（Continue CLI，默认 GLM-5.1，走用户自己的 API）干活（默认 gen→review 两趟 + Claude 承重门），**不再 spawn coder-api/gen/review 任何 Sonnet 子 agent（已退役）**。用于简单任务省 Claude 套餐 token + 对比不同模型 API 能力。用户输入 /team-task-api 时触发。
---

# team-task-api

`/team-task` 的**降级版**：流程一字不差，**唯一差别是执行者** = `coder-api`（驱动外部模型 cn，不 spawn cn 为 teammate，lead 经门脚本 `~/.claude/skills/team-task-api/run_cn_task.ps1` 调用）。设计与锁定决策见 `Mc-emoji/[feature-03-take-a-nap]/coder-api第二套team-实现交接spec.md`。

## 触发后立刻做（同 team-task）

1. **读当前 repo 根目录的 `team-task.md`**（`./team-task.md`）。读不到就停下报"本 repo 根目录没有 team-task.md"，不瞎建队。
2. **先读完整份**——它定义第 0 步驱动模式、团队结构（含「执行者变体」段）、team-progress.md 规则、落点、边界。
3. 看「本次任务」是否填了内容：**空** → 让用户先填，不自己编；**有** → 先归档上一轮 team-progress、再走第 0 步，然后建队执行。
4. **归档上一轮 team-progress**（建队前，按 team-task.md 通用要求）：根 `team-progress.md` 复制进 `team-progress/team-progress-{NNN}.md`（流水号 +1 补零三位），根文件重置为带面包屑的最小骨架；不存在/空骨架则跳过。
5. **第 0 步（建队前强制）**：按 team-task.md，用 AskUserQuestion 让用户二选一 **A 人工驱动 / B 深度放权**，选定前不许动手。

## 执行（默认 = lead 直驱门脚本「gen→review→承重门」，零 Sonnet 执行套壳）

- planner（只读规划）/ mc-expert（带 KB 挑战，只读顾问）**照常**——可作原生 teammate 或 lead 直接驱动，按 repo 的 Agent Teams 可用性定。
- **执行者 = lead 直驱门脚本「两趟 cn」**（🔭 2026-06-05 用户拍板「纯 cn 路线」起；**不再 spawn `coder-api` / `coder-api-gen` / `coder-api-review` 任何 Sonnet 子 agent——那三个壳已退役**）。理由：观察模式要**看见 cn 原始错误**，而 Sonnet 套壳的摘要恰好抹平它；直驱还省冷启动 + 双读。lead（你）亲自经门脚本调 cn 两趟：
  1. **gen 趟**：lead 把 spell-out 好的实现任务经门脚本下发 cn，产物落 `C:\Temp\gen_*`（**留原始 diff/输出供下趟审，别只留摘要**）。
  2. **review 趟**：lead 把 gen 产物/diff 作为待审材料经门脚本交 cn（**换 `-ConfigPath` 增交叉视角**），钉死输出契约让 cn 只回结构化 JSON `{"verdict":"pass|fail|warn","bugs":[],"rule_violations":[],"deviations_from_spec":[],"notes":""}`，别返大段散文。**cn-review 的 pass 是建议、不算交付。**
  3. **Claude(lead) 承重门**：实跑 / acceptance-check / 核首字节明文 magic / promote 决策，末尾过 `/code-review` skill 终审。承重永久在 lead 侧。
  - **cn 是 team 外无状态工具、不 spawn 为 teammate**（team-task.md「边界」的 team 外手工编排）；执行全纯 cn，零 Sonnet 执行套壳。
  - **观察模式记账**：cn 原始输出 + `C:\Temp\cn-calls.log` 直接进 lead 上下文——**要看见 cn 犯哪些错，别提前摘要抹平**。
  - **trivial 任务可降级**：lead 判冗余不值时只调一趟 cn（跳过 review）。
  - **opt-in 重档**：并行 gen×2（不同 config）+ review 多采样 self-consistency，真感单趟不够再上（见 spec §9）。
  - **lead 侧铁律**（原 coder-api.md 折入）：连失 2 次→熔断停下报你；缺 helper / 报错 / 现实冲突→停下不猜不绕；cn 报错**原样带回不粉饰**。
- **唯一调用方式（铁律）**：禁止直接 `cn -p`，一律经
  `pwsh -File "$HOME\.claude\skills\team-task-api\run_cn_task.ps1" -Task "<原文>" -WorkDir "<绝对路径>" [-ConfigPath <每模型一个 config>] [-TargetFiles a,b]`。
  门脚本负责：首字节路由（`50 4B`→python / `88 7D 1C`→自动直穿 COM helper / 未知→**观察模式放行**）、注入 15 行 guardrail、产物落 `C:\Temp\`、退出码、调用日志 `C:\Temp\cn-calls.log`、**禁库使用扫描（观察模式：命中只记进日志 `violation` 字段、保留 cn 真实退出码）**。
  > 🔭 **2026-06-05 观察模式**：门脚本**不再拦截/判 cn 失败**（原"未知→STOP exit 2"、"禁库命中→exit 9"均降级为放行+记录）。目标 = 最大化探测 cn 能力边界，cn 犯错是要记录的实验数据。承重核验（明文 magic / promote）仍在 Claude 侧人工把关，与门脚本无关。
- **能力边界**：T0 纯文本直接交 cn；T1（主力）加密/明文 Office 只让 cn **调已测 helper 黑盒**、不自写 COM、不直接 open 文件；越界（无现成 helper 的新 COM）→ 停下回报，让 Claude 先建+测 helper。
- **后验留 Claude 侧**：cn 产物在 `C:\Temp\`，核验首字节明文 magic 后才能 promote 到 `[feature-XX]/output/`；连失 2 次熔断。
- **team-progress.md**：lead 唯一写手；coder-api 经汇报、lead 落盘。收尾 lead 跑 `Clean up the team`。

## ⚠️ 用前必看（真实项目的数据外发红线）

本 api 变体（lead 直驱门脚本 → cn）会把**任务文本 / 文件内容**发到外部 cn（GLM）API。**含客户机密 / 对外交付物的真实项目，别走 api 变体，留默认 `/team-task`（原生 coder）。** api 变体定位是「学习探索 repo 省 token + 模型对比」。python 明文/外发的合规边界见 spec 的「合规红线」与根 CLAUDE.md「实测发现」卡。

## 不要做

- 不复述 team-task.md 全文，直接动手。
- 不让 cn 自写 COM / 直接 open Office / 自由填输出路径或选 Dispatch 模式（观察模式下门脚本只记录不拦，**承重护栏在 Claude 侧**：产物明文 magic 核验 + promote 把关）。
- **🔭 lead 不得自己写业务代码（纯 cn 路线纪律，2026-06-05）**：实现类改动**必须经门脚本 `run_cn_task.ps1` 交 cn**；lead（你）只做写任务书 / 承重核验 / promote，**绝不图省事用 Edit/Write 自己把活干了、跳过 cn**——那会污染模型对比实验（你以为在测 cn，实则 Claude 写的）。退掉 Sonnet 套壳后**工具锁没了**（子 agent 才能限制 tools，lead 手里有 Edit/Write），这条从工具级硬锁降为**纪律**。审计线 = **`C:\Temp\cn-calls.log`**：一个实现任务"完成"却无对应 cn 调用记录 = lead 偷懒，应自查/补跑。例外（lead 本职、非业务实现，允许直接写）：纯文档 / `plan.md` / `team-progress.md` / 把 `C:\Temp\` 产物 promote 到交付目录。
- 不跳过第 0 步 A/B 选择；不让 teammate 碰编排权。

> 机制与锁定决策：`Mc-emoji/[feature-03-take-a-nap]/coder-api第二套team-实现交接spec.md`（含门脚本、guardrail、coder-api.md 全文 + phase-2 多代理路线）。team-task 母版见同级 `team-task` skill。
