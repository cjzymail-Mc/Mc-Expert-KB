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
- 不跳过第 0 步的 A/B 选择（选 A 时还需逐决策点等用户拍板；**选 B「深度放权」时：teammate 报低置信/无先例，lead 不转交用户，当场按「默认>成功率最高>最易回滚」自走 + 记进 team-progress 的「自主裁决(B)」区，仅 4 条红线上报——销毁性删除 / 对外交付·Ldterm 明文 / 连失 2 次 / 推翻已封决策（上报=后置人工门 + 落盘上报，**非中途阻塞框**，见下节）；详见下「B 模式（深度放权）完整流程」节**）。

## B 模式（深度放权）完整流程（最新确认版 · 本 skill 为权威，team-task.md 不再各存一份）

> 2026-06-18 用户确认：A/B 驱动流程的**权威单一版本**在此，各 repo team-task.md 只留「本次任务 + repo 专属落点」，不再复制本节（曾因各存副本而漂移到不同版本）。

**第 0 步 AskUserQuestion 的 A/B 选项文案**（lead 直接喂给 AskUserQuestion，无需各 repo team-task.md 重写）：
- **A · 人工驱动**：lead 每个决策点都停下问用户；派活 / 批 plan / 汇总都等用户确认，lead 只做机械执行。（前期测试期推荐）
- **B · 深度放权（真授权）**：**不确定也先跑**——planner/mc-expert/coder 报「低置信 / 无先例 / 拿不定主意」时，lead 不转交用户，当场按「**默认项 > 历史成功率最高项 > 最易回滚项**」拍一个并继续，逐条记进 team-progress 供事后批量复盘。**仅 4 条红线才上报**，平时用户不插手。（学习型 repo 的快速试错档：宁可先跑出可审结果再快速纠偏，不在每个小分叉上堵用户。）

**选 A**：所有决策点停下问用户；coder 任何改动必须用户批 plan。

**选 B 驱动落地（四条铁律，缺一不可）**：
1. **不确定 ≠ 上报**。teammate 报低置信/无先例/拿不定主意时，lead **不转交用户**，当场按「默认 > 成功率最高 > 最易回滚」拍一个继续。mc-expert 低置信时也必须给具体默认推荐（见其铁律 2），lead 直接采纳，不要求它先"想清楚"。
2. **拍了就记**（放权对价，不可省）。每个自主裁决在根 `team-progress.md` 的 `## 自主裁决(B)` 区追加一行：`决策点 / 候选项 / 选了哪个 / 依据(默认|成功率|易回滚) / 置信度`。这是用户事后批量复盘 + 快速纠偏的唯一入口。
3. **只有 4 条红线才停下问用户**（其余一律自走）：① 销毁性/不可逆操作（多文件删除、覆盖无备份——遵 CLAUDE.md 删除硬规则）；② 对外交付物 / 触碰 Ldterm 明文合规红线；③ 连续失败 2 次熔断；④ 推翻 KB `decisions/` 已封决策。**①②类会触发权限框的命令（rm/删除/无备份覆盖/伸 `~/.claude`·系统·敏感目录/对外）绝不在 B 自主流程中途发起——会死等缺席用户 + 死锁后台 agent；一律攒「待人工处理」后置到人工门，halt 走「不执行该命令 + 落盘报告 + halt 上报」、不靠阻塞式权限框（后置的是决策权，非后置着自己偷偷补做）；forensic/排查也不例外（别用含 `rm`/伸敏感目录的命令去查问题）。详见 KB `decisions/autopilot-defer-perm-to-human-gate`。**
4. **收尾一次性**把「自主裁决(B)」清单连同结果交回用户复盘，**别在过程中逐条确认**。

**两模式都不变的硬线**：teammate **不碰编排权**、不替用户做「推翻已封决策」级判断；CLAUDE.md 的删除 / Ldterm / COM 硬规则两模式下都**不被放权覆盖**。

### 两条恒定不变量（跨所有 repo 的安全阀，换执行者 / 换任务都不许漏）

1. **自主裁决必须「浮」到交付物，不能只埋进 team-progress。** B 模式 lead 替用户拍的判断点（D1/D3 类、口径取舍、低置信选型……），除记进 team-progress 的「自主裁决(B)」区外，**必须在最终交付物汇报里显眼列为待确认项**，供用户验收时一句话能翻。team-progress 是内部文件、用户不看——只埋进去 = 偷偷替用户拍了板。这是「无弹窗」与「不被偷偷拍板」之间的安全阀，不能靠运气（同反射「交付必显式列 pending 项」）。
2. **B 只压「循环内决策门」，不压「用户显式定义的交付/验收门」。** 两类门要分清：①循环内决策点（plan 审批、低置信选型）——B 压掉、自走；②用户显式定义的交付/验收门（如素材审核门、成品人工验收）——**B 不压，照常产出给用户**。换个门结构时，别因为选了 B 就把用户想要的门跳过、也别把用户的验收门误当循环决策吞掉。

> 机制细节、为什么这样设计：见 KB `Mc-Expert-repo/references/agent-teams.md`「新手 FAQ」+ `Mc-emoji/[feature-03-take-a-nap]/sub-plan-stage3-agentteam-spike.md`。

## 收尾 · 微型 loop：mc-update → pin → session-new（Clean up team 之后、每次正常收尾必走）

team 清理完（lead 跑完 `Clean up the team`）、本次任务**正常收尾**后（完成、或带卡点上报但未熔断），按 **mc-update → pin → session-new** 顺序跑一遍收尾固化。三个环节都是**先预判、再决策执行**，不是无脑跑；目的是省掉用户每次手敲 `/mc-update`、`/pin`、`/session-new`，并把本次任务里 **capture_hook 词表漏网的纠正**捞进 feature-05 捕获网。**全程由 lead 执行**（teammate 此刻已 shutdown、不派给他们——pin 陪审走临时 `@agent`(mc-expert) 一次性，见下）。

**触发边界**：
- 正常收尾（完成 / 带卡点上报）→ 进本 loop。
- **熔断 / halt 交用户 / 任务无实质进展**（红线③ 连续失败 2 次熔断等）→ **跳过 mc-update 和 pin**（mc-update 纪律就是"只在任务完成后走"、pin 是"捞本次纠正残留"——未完成/无产物两段都没意义）；但 **session-new 仍走**——预判里点明"本次未正常完成，建议 session-new 固化中断/卡点现场 + team-progress 归档指针以便接续"。

**mc-update → pin → session-new 的顺序语义**：mc-update 先固化"本次经验/记忆层"；**pin 居中**——捞 mc-update 判定后仍漏网的纯陈述式纠正（若 mc-update 判"无新可固化"，pin 预判多半也是"无漏网纠正"）；session-new 最后固化"本次讨论/状态层"做交接（含 team-progress 归档指针），并落 pin 段报告行（见下）。三者职责不重叠（mc-update 偏 memory/feedback、pin 偏 feature-05 燃料补漏、session-new 偏 plan/状态文件 + 归档指针）。

**每个环节两步走**：

1. **预判（必带，不能套话）**：基于**本次任务的实际产物**（team-progress、teammate 产出文件、记忆候选等）给一句话预判——"有/没有可固化（mc-update）/ 漏网纠正（pin）/ 可交接（session-new）的东西，建议跑/不必跑"+ 一句**具体理由**。每次任务的明细、中间产物、来源入口都不同，预判必须落到本次实际，禁止"建议跑 mc-update"这种通用套话。
2. **决策 + 执行**：
   - **A 模式（人工驱动）**：lead 用 AskUserQuestion 弹问用户，把预判写进选项描述（让用户看着预判拍板）——**判断权在用户**。选"是" → **用户不再手敲**，lead 直接用 Skill 工具调用 mc-update / session-new 执行（pin 段见下、走陪审通道）。选"否" → 跳过。
   - **B 模式（深度放权）**：lead **不转交用户**，按铁律 1「默认 > 成功率最高 > 最易回滚」自己判 mc-update / session-new 要不要跑，逐条记进 team-progress 的 `## 自主裁决(B)` 区 + 浮到交付汇报的待确认项（恒定不变量 1）。**熔断场景仍按上面"触发边界"处理**——不让 B 模式给 mc-update 续命。

**★ pin 段（居中 · feature-05 补漏层 · lead 执行）**——**判据单一指针见 KB `Mc-Expert-repo/references/收尾loop判据.md`**（PIN/DROP 判据、方案 a 去重、掉线降级、陪审 spawn 五要素都在那；本 skill 只写控制流、不抄判据，改判据只改那一处）：
1. **预判闸（必带）**：一句话判"本次有无词表漏网的纠正迹象"——**无迹象直接跳 pin 段、不派 mc-expert**（省陪审成本）。有迹象才往下。
2. 有迹象 → 回顾本次任务列纠正候选（**认不出不硬造**，pin.md 铁律）。
3. **去重（方案 a）**：Grep/Read 本会话 `live-candidates.<session>.jsonl`，capture_hook 已抓的剔除。
4. **派 mc-expert 陪审**：team 已 shutdown，**临时 `@agent`(mc-expert) 一次性**（用完即释，呼应建队执行「陪审不省」）；候选 ≥2 条一次 spawn 全给、逐条判，单条才单发。spawn prompt 五要素 + 红线"只给 PIN/DROP+依据、不复述纠正、不顺势修错、**不附概率分**"见判据指针 §5。
5. **掉线降级**：mc-expert 零正文 / Connection closed → 重试 1 次 → 仍失败 → 该候选落 `Loops/review-queue.md` 交用户补判（**不硬 pin、不 DROP、不连试 ≥2 次**，细则见判据指针 §4）。
6. **落账**：只对陪审 PIN 的跑 `pin_capture.py`（`--corr`/`--ai`/`--note`/`[--followup]`）；lead 调用前自校验 fail-loud（陪审缺 PIN/DROP/纠正原文/依据 → 不硬凑参数，见判据指针 §6）；候选为空 → 静默跳过。
7. **报告行**：pin/drop/掉线降级任一发生 → 在 session-new 段产出的 plan 里记一行 `pin N / drop M / 降级 K 落 review-queue`。

**一致性约束（堵 B 模式 lead 自判跳过偏差）**：
- 收尾三段**每段预判一句话 + 跳过必给具体理由**，不许套话跳过。
- **B 模式下 pin 段预判闸判"无迹象"可直接跳**（事实判断）；**但只要"有迹象"就必须派陪审、不许自判"算了不 pin"**——靠本 checklist 收窄走样空间，**但不保证**（要保证"必跑"只能路线 C Stop hook，本版未实现）。

**两层判断边界（别越权）**：本 loop 只判"**要不要启动** mc-update / pin / session-new"。启动之后——写不写记忆、pin 哪条、产不产 plan——是 mc-update / pin_capture / session-new **各自流程的职责**（mc-update 有频次/去重两道闸门、pin 走判据指针、session-new 有自己的四步），team-task 收尾不替它们判、也不重复其内部逻辑。

**B 模式下 session-new 的边界**：lead 判"跑 session-new" = 走固化交接流程（产 plan + 更新状态文件 + team-progress 归档指针），**不是强制清空/重开 session**——真正关 session、重开仍由用户操作，lead 不替用户决定何时真关。

**session-new 段幂等（防 loop 重入产重复 plan）**：session-new 重入前查本会话 plan 是否已存在（同名/同任务），存在则跳过、不堆重复/空 plan。
