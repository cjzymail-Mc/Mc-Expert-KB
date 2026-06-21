---
name: team-task
description: 用 Agent Team 执行任务的入口（类似 /today）。读取当前 repo 根目录的 team-task.md，先让用户选驱动模式（A 人工驱动 / B 深度放权），再按其建一个三角色协调小队（planner / mc-expert / coder）、维护根目录 team-progress.md，然后执行 team-task.md 的「本次任务」。用户输入 /team-task 时触发。
---

# team-task

把"启用 agent team 干一件事"固化成一个命令。等价于 `/today`，但目标文件是 `team-task.md`、且强制走 team 工作流。

## 触发后立刻做

1. **读当前 repo 根目录的 `team-task.md`**（`./team-task.md`）。读不到就停下报告"本 repo 根目录没有 team-task.md"，不要瞎建队。
2. **先读完整份**——瘦身后它只定义 **repo 专属落点/边界 + 本次任务**；通用流程（第 0 步 A/B 驱动模式选择含 B 模式深度放权完整流程、团队结构、team-progress 归档与规则、收尾）= 本 skill 权威，见下各节。
3. 看「本次任务」是否填了内容：
   - **空** → 告诉用户"team-task.md 的『本次任务』是空的，请先填写"，不要自己编任务。
   - **有** → 先归档上一轮 team-progress、再走第 0 步，然后建队执行。
4. **归档上一轮 team-progress（建队前必做，先于覆写）**：扫 `team-progress/` 现有 `team-progress-NNN.md` 取最大序号 +1（补零三位，空目录从 `001`）→ 复制根 `team-progress.md` 进 `team-progress/team-progress-{NNN}.md`（路径含 `[]` 的 repo 用 `Copy-Item -LiteralPath` 或引号包裹、勿用 Office SaveAs），**确认复制成功**再继续 → 把根文件重置为最小骨架（标题 + 空的「进度日志/当前现状/下一步/卡点」+ 顶部面包屑 `> 上一轮已归档至 team-progress/team-progress-{NNN}.md，如需续接先读它`）。根文件不存在 / 只剩空骨架（无 `### 日期` 条目）则跳过。
5. **第 0 步（建队前强制）**：用 AskUserQuestion 让用户二选一驱动模式 **A 人工驱动 / B 深度放权**（选项文案 + 落地见下「B 模式（深度放权）完整流程」节 = 本 skill 权威，不靠各 repo team-task.md），选定前不许建队。

## 建队执行（通用要求 · 本 skill 权威）

- 前提：本 repo 已开 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`。若用自然语言建队后没 spawn 出 teammate，提示用户确认开关已开 + CC ≥ v2.1.32（`claude --version`）。
- 用自然语言建一个 team：planner（只读规划）/ mc-expert（带 KB 挑战，只读顾问）/ coder（含 Edit/Write）。关键背景写进 spawn prompt（teammate 不继承 lead 对话历史）。
- **放权深度**：A/B 驱动模式的完整流程（选项文案 + 四铁律 + 两条恒定不变量）**写死在本 skill（见下「B 模式（深度放权）完整流程」节）= 权威单一版本**，不依赖各 repo team-task.md 是否写到——这是「无弹窗」与「不被偷偷替你拍板」之间的安全阀，不能靠每个 repo 各自补。只有**真·repo 专属落地**（落点路径等）才留给该 repo team-task.md。
- **team-progress.md**：lead 当唯一写手，teammate 经 mailbox 汇报、lead 汇总落根目录 `team-progress.md`；只读角色不自己写文件。每完成一步更新（做了什么 / 现状 / 下一步 / 卡点）。断线续命：建队前归档已把上一轮存进 `team-progress/`，要续接先读那份最新归档——续的是工作内容/进度，**活 team 状态续不回**（teammate 要重 spawn）。
- **长正文回传 / 里程碑汇报（含只读角色）**——建队 spawn prompt 里对每个 teammate 写明下列：
  1. **传输层**：teammate 完成后**必须显式 `SendMessage` 发给 lead**——别依赖 idle 通知（只带一行摘要、不带正文）。〔2026-06-17 实测：显式 `SendMessage` 单条 ~46KB 全量逐字到达——通道与容量没问题。〕
  2. **承重层（2026-06-18 修订旧「不是落盘」口径）**：显式 `SendMessage` **必要不充分**。实证：①投递 flaky——同一 coder 同 session 既有完整正文(1730字)到达、也有连 3 轮只到 idle 零正文(mc-debug07)；②teammate 可能撞 session 限额在汇报前被截断(本次两 coder 实测)。故**有 Write 的角色(coder)：有产物的报告先写盘 + `SendMessage` 发指针，承重靠盘**；只读角色(planner/mc-expert，无 Write、opus)仍发全文（同 session 6.7k/3.5k/5.2k 字均逐字到达，可靠）。
  3. **lead 兜底**：「产物/报告已落盘」节点 lead **默认直接读文件验收**，正文连等 ≤2 轮询拿不到 → 直接自核产物（Bash/zipfile 实扫），别陷进反复 nudge 的递减回报。
  4. **诊断纠偏**：本环境 team = `backendType: in-process`（**非 tmux**）。失败是同 session 投递 flaky + 可能 session 限额截断，**不是** tmux 轮询/通道容量/agent 漏发工具调用——别查 pane、改 tmux、分块正文、或加「记得发工具」这种无效咒语。
  5. **★选型纠偏（最高杠杆·建队前先判）★**：若是**单点串行流水线**（一个 coder 握全量从 M1 干到 M4、其余角色只前端把关一次），**不建队**——执行体隔 flaky mailbox 汇报是自找失败面。lead 向用户说明「建议 solo + 理由」，得 OK 后**就地 solo 执行**（沿用 step-0 已选 A/B 档，不绕 todays-task、不重敲命令、不丢授权）。**陪审不省（深度授权的安全阀）**：solo 省的是常驻 team 的冷启动/编排成本、**不是省 mc-expert 陪审**——前端 plan 审/素材门、**每个关键验收门交用户之前**、以及 mode-B 自主裁决点，仍派**一次性 `@agent`（mc-expert/planner）带验收背景把关、用完即释**（[[feedback_keygate_mc_expert_jury]]：逐门审非只审一次；其「不存在/悬空」类否定结论因工具只见本 repo 须实测再采，正面建议照收）。执行段 lead 自己写代码/COM 自检。这样 idle-零正文从源头不发生（[[feedback_solo_vs_cold_team]]）。并提示用户：此类 task-shape 下次在 chop-task 前端就该进 todays-task / 单干 lane。team 留给真并行/真多专长协作。
  〔机制实证版单一权威诊断见 KB `Mc-Expert-repo/references/agent-teams.md`「idle-零正文：故障模型 + 兜底策略」节〕
- **效率/通信**：能匹配已有 role/skill 就直接走、别从零规划；需盘点多文件派 Explore subagent、别自己串行翻；不复述 team-task.md、直接动手；收尾只报 完成 / 卡点 / 下一步。
- 收尾让 **lead** 跑 `Clean up the team`（先 shutdown 所有 teammate）。

## 不要做

- 不复述 team-task.md 全文，直接说"开始执行 X"后动手。
- 不让 teammate 碰编排权 / 替用户做「推翻已封决策」级判断。
- 不跳过第 0 步的 A/B 选择（选 A 时还需逐决策点等用户拍板；**选 B「深度放权」时：teammate 报低置信/无先例，lead 不转交用户，当场按「默认>成功率最高>最易回滚」自走 + 记进 team-progress 的「自主裁决(B)」区，仅 4 条红线上报——销毁性删除 / 对外交付·Ldterm 明文 / 连失 2 次 / 推翻已封决策；详见下「B 模式（深度放权）完整流程」节**）。

## B 模式（深度放权）完整流程（最新确认版 · 本 skill 为权威，team-task.md 不再各存一份）

> 2026-06-18 用户确认：A/B 驱动流程的**权威单一版本**在此，各 repo team-task.md 只留「本次任务 + repo 专属落点」，不再复制本节（曾因各存副本而漂移到不同版本）。

**第 0 步 AskUserQuestion 的 A/B 选项文案**（lead 直接喂给 AskUserQuestion，无需各 repo team-task.md 重写）：
- **A · 人工驱动**：lead 每个决策点都停下问用户；派活 / 批 plan / 汇总都等用户确认，lead 只做机械执行。（前期测试期推荐）
- **B · 深度放权（真授权）**：**不确定也先跑**——planner/mc-expert/coder 报「低置信 / 无先例 / 拿不定主意」时，lead 不转交用户，当场按「**默认项 > 历史成功率最高项 > 最易回滚项**」拍一个并继续，逐条记进 team-progress 供事后批量复盘。**仅 4 条红线才上报**，平时用户不插手。（学习型 repo 的快速试错档：宁可先跑出可审结果再快速纠偏，不在每个小分叉上堵用户。）

**选 A**：所有决策点停下问用户；coder 任何改动必须用户批 plan。

**选 B 驱动落地（四条铁律，缺一不可）**：
1. **不确定 ≠ 上报**。teammate 报低置信/无先例/拿不定主意时，lead **不转交用户**，当场按「默认 > 成功率最高 > 最易回滚」拍一个继续。mc-expert 低置信时也必须给具体默认推荐（见其铁律 2），lead 直接采纳，不要求它先"想清楚"。
2. **拍了就记**（放权对价，不可省）。每个自主裁决在根 `team-progress.md` 的 `## 自主裁决(B)` 区追加一行：`决策点 / 候选项 / 选了哪个 / 依据(默认|成功率|易回滚) / 置信度`。这是用户事后批量复盘 + 快速纠偏的唯一入口。
3. **只有 4 条红线才停下问用户**（其余一律自走）：① 销毁性/不可逆操作（多文件删除、覆盖无备份——遵 CLAUDE.md 删除硬规则）；② 对外交付物 / 触碰 Ldterm 明文合规红线；③ 连续失败 2 次熔断；④ 推翻 KB `decisions/` 已封决策。
4. **收尾一次性**把「自主裁决(B)」清单连同结果交回用户复盘，**别在过程中逐条确认**。

**两模式都不变的硬线**：teammate **不碰编排权**、不替用户做「推翻已封决策」级判断；CLAUDE.md 的删除 / Ldterm / COM 硬规则两模式下都**不被放权覆盖**。

### 两条恒定不变量（跨所有 repo 的安全阀，换执行者 / 换任务都不许漏）

1. **自主裁决必须「浮」到交付物，不能只埋进 team-progress。** B 模式 lead 替用户拍的判断点（D1/D3 类、口径取舍、低置信选型……），除记进 team-progress 的「自主裁决(B)」区外，**必须在最终交付物汇报里显眼列为待确认项**，供用户验收时一句话能翻。team-progress 是内部文件、用户不看——只埋进去 = 偷偷替用户拍了板。这是「无弹窗」与「不被偷偷拍板」之间的安全阀，不能靠运气（同反射「交付必显式列 pending 项」）。
2. **B 只压「循环内决策门」，不压「用户显式定义的交付/验收门」。** 两类门要分清：①循环内决策点（plan 审批、低置信选型）——B 压掉、自走；②用户显式定义的交付/验收门（如素材审核门、成品人工验收）——**B 不压，照常产出给用户**。换个门结构时，别因为选了 B 就把用户想要的门跳过、也别把用户的验收门误当循环决策吞掉。

> 机制细节、为什么这样设计：见 KB `Mc-Expert-repo/references/agent-teams.md`「新手 FAQ」+ `Mc-emoji/[feature-03-take-a-nap]/sub-plan-stage3-agentteam-spike.md`。
