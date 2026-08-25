---
name: today-core
description: 单 plan 公共执行内核——路由门控、执行、收尾固化、两连败熔断。由 today（单次入口）或 today-loop（完整 loop）调用，不直接响应用户输入、不做 model-driven 自动触发。caller 必须预先通过 args 提供 mode（normal/autopilot），core 自己不问。
arguments: [mode, task]
---

# today-core（单 plan 执行内核 · 被 caller 调用）

> **定位**：从 `today` 抽出的单 plan 公共执行内核。两个 caller 共用：
> - **today**（`/today` 单次入口）：先跑 today §1 全托管前置门拿到 mode，再 `Skill(today-core, args: '<mode> "<task>"')` 调本 core（mode/task 走 `\$ARGUMENTS` 通道 A）。
> - **today-loop**（完整 loop，Phase 3 实现）：BUILD 阶段调本 core 交 `{mode: autopilot, task, run_contract, caller_context}`——mode/task 走通道 A、run_contract 走通道 C（caller Write `.claude/run/<run_id>.contract.yaml` + core Read）、**不重跑 §1 前置门**（Run Contract 已冻结等效全托管授权）。
>
> **caller contract 单源**：`Mc-emoji/[feature-05-loop-self-improvement]/output/plan11-phase1-contracts/today-core-caller-contract.md`（字段 schema + mode 贯穿点 + **字段→传递通道映射 §3.1**）。本 skill 只消费 contract、不自己问 mode。
>
> **判据单源**：`Mc-Expert-repo/references/today完整版loop判据.md`（完整 loop 的状态机/PASS-REWORK-WAIT_HUMAN 判据；本 core 是其中 BUILD/SELF_CHECK/JURY 的单 plan 执行侧）。
>
> **mode 贯穿（★ 全托管"第四面"，抽 core 时最易割裂的坑）**：mode 在本 core 内部有 **4 个消费点**——§1.1 门 3、§1.2 途中决策、**§2.1 收尾段决策+执行**、§2.2 两连败。母本提示框曾只标三面（§1/§2.2/§3.2），漏了 §2.1 收尾段也读 mode。本 core 用同一根 mode 值贯穿全部 4 点，不得把 §2.1 当"与 mode 无关的纯收尾"。

---

## §0 进 core 前的 contract 校验（fail-loud）

caller 调本 core 时，core 先校验从 args 收到的入参：

1. `$mode` 在且 ∈ `{normal, autopilot}`——**缺失即停**（core 不自己问，回退 caller 让它跑 §1 或补 Run Contract）。
2. `$task` 在（本次要执行的任务/阶段目标）。
3. `caller_id` ∈ `{today, today-loop}`（走通道 B 对话上下文，caller 在调用前声明）。
4. `caller_id=today-loop` 时 run_contract 文件应在 `.claude/run/<run_id>.contract.yaml`（通道 C，Phase 3 落地；Phase 2 today 调用不带）。

校验不过 → core 不执行，回报 caller「contract 不完整」，不硬凑默认 mode 往下跑。

**通道机制（不糊弄）**：Skill 工具的 `args` 由 frontmatter `arguments: [mode, task]` 按 shell-style quoting 解析；caller 写成 `args: 'autopilot "完成 X 任务"'`，§0 上面的两个实际消费点分别拿到 mode=autopilot、task=完成 X 任务。多词 task 必须包双引号，task 内双引号写成 `\"`；run_contract 大包不走 args、走文件（详见 caller contract §3.1 通道映射）。

---

## §1 执行调度（原 today §2.1 强制门控，读 mode 分叉）

> **全托管横跨本 core §1/§2/§3 四处**——门控分叉、途中延伸、收尾决策、两连败熔断——是同一根 mode 变量的四面（第四面在 §3 收尾）。改任一处须同步另三处，避免 mode 语义割裂。

### §1.1 强制门控（读完 task 后,先做路由判断,再动手）

1. 任务是否匹配已有 role(builder/researcher/converter/archivist/pm)或 skill?
   - 是 → 立即调用对应 slash command,不要从零规划、不要自己先读项目文件
   - 否 → 进入下一步
2. 【team task 门】任务是否是「多步实现类、需要 plan→挑刺→实现→复审」的活,或要改多文件/有架构取舍、值得 planner/mc-expert/coder 小队?
   - 是 → **停下,不要自己建队、也不要自己直接开干**;向用户说明「此任务复杂度够 team,建议走 /team-task」+ 一句理由,等用户确认后再动。**mode=autopilot 也不例外**:升级到 team 是难度判断、始终留给用户;caller_id=today-loop 交的 contract 即便 mode=autopilot、也不要自动闯过 team 门、不替用户决定转不转 team。
   - 否(轻量任务,单点改动/查询) → 进入下一步,自己干
3. 【mc-expert 咨询门 · 中等档(team 与单干之间)】没够 team 门、本可自己干,但**你拿不准 / 犹豫不决**,或命中 mc-expert 任一触发条件——**重大技术选型 / 改核心文件(CLAUDE.md、本 repo 的 plan*.md / agent 定义 / 若是 KB repo 则含 principles·reflexes·repo-map·decisions·references)/ 同一问题已连续失败 2 次**——则**别完全单干**:先 `Task(subagent_type=mc-expert)`，按共享 `review-contract-v2.md` 交齐 `REVIEW_PROFILE=HISTORY / AUTHOR_RUNTIME / REVIEW_TARGET / PROJECT_MEMORY / SEALED_DECISION_QUERY / REVIEW_QUESTION`，拿到历史建议再动手。HISTORY 只做开工/中途咨询，不冒充最终终审。
   - **mode=normal(普通档)**:mc-expert 置信度低时按其建议升级给用户;真正琐碎、无疑义的改动才直接自己干。
   - **mode=autopilot(全托管档)**:拿到裁决后**直接照办、继续往下,不回头问用户**。**置信低/无先例不再升级**——采纳 mc-expert 的默认推荐(默认>成功率最高>最易回滚)继续,记进收尾「自主裁决」清单。只有 4 红线才停(见 §3.2:销毁性删除 / 对外交付·Ldterm 明文 / 连失 2 次 / 推翻已封决策)。**连失 2 次熔断优先**:计数到 2 一律转人工审,不再让 mc-expert 续命(见 §3.2)。
   - 注:本门是开工/收尾前的**自觉前门**;若本 repo 装了 mc-expert Stop-hook,收尾时还有 harness 兜底,两者互补——不要因为有 hook 就在该犹豫时跳过咨询。
4. 任务是否需要盘点多个相关文件(skills/agents/templates/pipeline 等)才能动手?
   - 是 → 派 1 个 Explorer subagent 一次性平行盘清楚,不要自己串行 Glob+Read
   - 否 → 自己直接动手

### §1.2 全托管延伸 · 简单任务执行途中冒出决策点(仅 mode=autopilot 时生效)

> mode 四面之二(之一见 §1.1、之三见 §3 收尾、之四见 §3.2)。

- 场景:任务在门 2/门 3 判为轻量、已走"自己干",执行途中却临时冒出一个本来要停下问你的决策点(A 还是 B / 要不要顺手改某处 / 口径拿不准)。门 3 是开工前的前门,接不住这种途中才浮现的;本条专补这段。
- **mode=normal(普通档)**:照常停下问你,行为不变。
- **mode=autopilot(全托管档)**:**别停下问用户**——先按门 3 的 v2 六字段 envelope 调 `Task(subagent_type=mc-expert)`，固定 `REVIEW_PROFILE=HISTORY`，拿历史建议后直接照办、继续往下。**置信低/无先例同样不升级**,采纳其默认推荐继续 + 记进收尾「自主裁决」清单;只有 4 红线才停,连失 2 次熔断优先,转人工审(见 §3.2)。若最终产物命中共享 contract 的原生高影响/GLM 中风险终审门，必须另起 fresh `ENHANCED_FINAL`，不能拿本次 HISTORY 抵扣。
- 边界:只接管"本可自己拍的小决策"。若该决策点意味着任务其实升格到 team(改多文件 / 架构取舍),回门 2——升级到 team 始终留给用户,autopilot 不闯。

### §1.3 效率规则

- task 直接引用的文件(如 mc-debugN.md)和它在同一条消息里并行 Read;路径未知必须 Glob 时,Glob+Read 串行可接受
- 扫描/查找/盘点类只读动作派给 Explorer subagent(单点 1 个、多角度并行多个),不要自己 Glob/Grep 翻
- 写文件、改代码、跑命令仍由你自己执行,不委托 Explorer

### §1.4 通信规则

- 不要复述 task 内容,直接说"开始执行 X"后动手
- 收尾只报:完成了什么 / 卡点 / 下一步建议,不要列过程清单
- **mode=autopilot 额外**:收尾必在交付汇报里**显眼**附一份「自主裁决」清单(每条:决策点 / 候选 / 选了哪个 / 依据(默认|成功率|易回滚) / 置信度),供用户验收时一句话能翻、一次性批量复盘——放权的对价是**留痕浮到交付物**,不是埋进内部文件、也不是过程中逐条确认。

---

## §2 收尾固化（原 today §3，mode 第四面在这里）

### §2.1 微型 loop:mc-update → pin → session-new(每次正常收尾必走)

task **正常收尾**后(完成、或带卡点上报但未熔断),不要就此结束——按 **mc-update → pin → session-new** 顺序跑一遍收尾固化。三个环节都是**先预判、再决策执行**,不是无脑跑;目的是省掉每次手敲 `/mc-update`、`/pin`、`/session-new`,并把本次任务里 **capture_hook 词表漏网的纠正**捞进 feature-05 捕获网(pin 段职责)。**session-new 段现含第 0 步主线回顾**(读主线锚点→评估偏离→判下一步是否已落 plan→写进 plan),让收尾 loop 自驱推进主线下一步、不靠你人工追问;主线判断归 session-new 内部,core 不替它判(守两层判断边界)。

**触发边界**:
- 正常收尾(完成 / 带卡点上报)→ 进本 loop。
- **熔断 / halt 交用户 / 任务无实质进展** → **跳过 mc-update 和 pin**(mc-update 纪律就是"只在任务完成后走"、pin 是"捞本次纠正残留"——未完成/无产物两段都没意义);但 **session-new 仍走**——预判里点明"本次未正常完成,建议 session-new 固化中断/卡点现场以便接续"。

**mc-update → pin → session-new 的顺序语义**:mc-update 先固化"本次经验/记忆层";**pin 居中**——捞 mc-update 判定后仍漏网的纯陈述式纠正(若 mc-update 判"无新可固化",pin 预判多半也是"无漏网纠正");session-new 最后固化"本次讨论/状态层"做交接,并落 pin 段报告行(见下)。三者职责不重叠(mc-update 偏 memory/feedback、pin 偏 feature-05 燃料补漏、session-new 偏 plan/状态文件)。

**每个环节两步走**:

1. **预判(必带,不能套话)**:基于**本次任务的实际产物**给一句话预判——"有/没有可固化(mc-update)/ 漏网纠正(pin)的东西,建议跑/不必跑;**session-new 段判本次是否正常收尾**(正常收尾→必启动,主线/下一步判断归 session-new 内部第 0 步、不在本层判)"+ 一句**具体理由**。每次任务的明细、中间产物、来源入口都不同,预判必须落到本次实际,禁止"建议跑 mc-update"这种通用套话。
2. **决策 + 执行**:
   - **mode=normal(普通档)**:用 AskUserQuestion 弹问,把预判写进选项描述(让你看着预判拍板)——**判断权在你**。选"是" → **你不再手敲**,Claude 直接用 Skill 工具调用 mc-update / session-new 执行(pin 段见下、走陪审通道)。选"否" → 跳过。
   - **mode=autopilot(全托管档)**:不弹你,把"要不要跑 mc-update / session-new"+ 任务背景/产物丢给 mc-expert 咨询,它判定后 Claude 直接照办(跑或跳),记进收尾「自主裁决」清单。**熔断场景仍按上面"触发边界"处理**——不让 mc-expert 给 mc-update 续命。

> ★ 本条「决策+执行」的 mode 分叉是**全托管第四面**(母本提示框曾漏标)。mode=normal 弹 AskUserQuestion、mode=autopilot 丢 mc-expert——与 §1.1 门 3、§1.2 途中延伸用同一根 mode 变量,不得解耦。

**★ pin 段(居中 · feature-05 补漏层)**——**判据单一指针见 KB `Mc-Expert-repo/references/收尾loop判据.md`**(PIN/DROP 判据、方案 a 去重、掉线降级、陪审 spawn 五要素都在那;本 core 只写控制流、不抄判据,改判据只改那一处):
1. **预判闸(必带)**:一句话判"本次有无词表漏网的纠正迹象"——**无迹象直接跳 pin 段、不派 mc-expert**(省陪审成本,实测一次约 2m56s+token)。有迹象才往下。
2. 有迹象 → 回顾本次任务列纠正候选(**认不出不硬造**,pin.md 铁律)。
3. **去重(方案 a)**:Grep/Read 本会话 `live-candidates.<session>.jsonl`,capture_hook 已抓的剔除(pin_capture.py 跨文件不去重,必须 LLM 自查)。
4. **派 mc-expert 陪审**:候选 ≥2 条一次 spawn 全给、逐条判;单条才单发。spawn prompt 五要素 + 红线"只给 PIN/DROP+依据、不复述纠正、不顺势修错、**不附概率分**"见判据指针 §5。
5. **掉线降级**:mc-expert 零正文 / Connection closed → 重试 1 次 → 仍失败 → 该候选落 `Loops/review-queue.md` 交用户补判(**不硬 pin、不 DROP、不连试 ≥2 次**,细则见判据指针 §4)。
6. **产提案清单(不自动落账)**:对陪审 PIN 的候选**不调 `pin_capture.py`**,而是整理成结构化 pin 提案清单,作为人工门输入(见 pin 段末"人工门批量落账")。lead 在产出前自校验 fail-loud(陪审缺 PIN/DROP/纠正原文/依据 → 不硬凑提案字段,见判据指针 §6);候选为空 → 静默跳过、不产空清单。
   - **提案清单 schema**(字段名与 `pin_capture.py` 入参对齐,供人工门批量解析;LLM 按此产出):
     ```json
     {
       "pin_proposals": [
         {"verdict": "PIN", "category": "<classify>", "corr": "<纠正原文>", "ai": "<被纠正的AI动作>", "followup": "<可选>", "note": "<可选>", "jury_basis": "<mc-expert 陪审依据>"}
       ],
       "dropped": [{"verdict": "DROP", "corr": "...", "reason": "..."}],
       "degraded_to_review_queue": [{"verdict": "DEGRADED", "corr": "...", "reason": "mc-expert 掉线"}]
     }
     ```
   - 清单作为"pin 提案"写进 session-new 段产出的 plan / 交付汇报,**等用户人工门审核**,不在收尾链里自动落账。**判别+陪审+去重(1-5 步)+产提案(第6步)+报告(第7步)全是脑力活,跨 repo 可跑、不依赖 `$pin` skill 或 pin_capture.py 在场**——这是 pin 解缠的关键:收尾链不再因缺 `$pin` 断链。
   - **dedup 边界提示**:第 3 步只查 capture_hook 抓的 `live-candidates.<session>.jsonl`,**不查 `pinned-candidates.jsonl`**(已 pin 历史)——故 PIN 候选可能含历史已 pin 项,`pin_capture.py` 文件级 dedup 是人工门批量落账时的唯一兜底(命中即跳过、不报错)。
7. **报告行**:pin/drop/掉线降级任一发生 → 在 session-new 段产出的 plan 里记一行 `pin N / drop M / 降级 K 落 review-queue` + 附上第 6 步的提案清单(漏跑频率可观测,供决定是否上路线 C Stop hook)。

**人工门批量落账(pin 段提案化后的落账方式,由用户显式发起)**:用户拿到 pin 提案清单 → 审核 → 拍板"这 N 条 pin";**LLM 一次性批量落账** = 对用户确认的 N 条,循环调 `python "D:/Downloads/Mc Claude Code Workshop/Mc-emoji/[feature-05-loop-self-improvement]/历史扫描/pin_capture.py" --pin-log "D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/.claude/auto-memory/pin/pinned-candidates.jsonl" --platform <claude/codex> --corr ... --ai ... --followup ... --note ...`(N 次)。`pin_capture.py` 文件级 dedup 幂等,重复自动跳过、不报错；中央 sink 缺失/不可写时明确失败，不回退旧 sink。**dedup 按 `ai + corr + followup` 三字段算——followup 措辞差异会导致 hash 不同、可能重复入网**,故人工门审提案时若某条疑似历史已 pin,**以 `ai + corr` 为主核对**、不靠脚本 dedup 兜底。writer/core 仍由 Mc-emoji feature05 单源维护，原始纠正信号统一写入中央 ignored raw lane；这不是跨 repo 自动调用 `$pin` skill。

**一致性约束(堵 temp.md 实证偏差:B 模式下 claude 曾自判跳过、没派 mc-expert)**:
- 收尾三段**每段预判一句话 + 跳过必给具体理由**,不许"看起来没什么"的套话跳过。
- **mode=autopilot 下,pin 段预判闸判"无迹象"可直接跳**(这是基于产物的事实判断、不是偷懒);**但只要"有迹象"就必须派陪审、不许自判"算了不 pin"**——这是规则在场仍被违反的点,靠本 checklist 收窄走样空间,**但不保证**(temp.md 已证软自律不保证必跑;要保证"必跑收尾"只能路线 C,本版未实现,此为已知缺口)。

**两层判断边界(别越权)**:本 loop 只判"**要不要启动** mc-update / pin / session-new"。启动之后——写不写记忆、pin 哪条、产不产 plan——是 mc-update / pin_capture / session-new **各自流程的职责**(mc-update 有频次/去重两道闸门、pin 走判据指针、session-new 有自己的四步),core 收尾不替它们判、也不重复其内部逻辑。

**autopilot 下 session-new 的边界**:mc-expert 判"跑 session-new" = 走固化交接流程(产 plan + 更新状态文件),**不是强制清空/重开 session**——真正关 session、重开仍由你操作,mc-expert 不替你决定何时真关。

**session-new 段幂等(防 loop 重入产重复 plan)**:session-new 重入前查本会话 plan 是否已存在(同名/同任务)——存在则**只跑第 0 步主线回顾 + 状态更新、不重复产 plan**(不再整个跳过,否则主线回顾也漏)。

### §2.2 全托管安全阀 · 连续失败 2 次 → 转人工审(仅 mode=autopilot 时生效;触发于 §1 每步判定后)

> mode 四面之四(之一见 §1.1、之二见 §1.2、之三见 §2.1 收尾)。

- 为什么用脚本:阈值计数不能靠你自己记(context 压缩会丢计数、"再试一次"会越过阈值)。确定性交给计数文件 + 固定脚本,你只负责"认这次成/败"。
- 脚本:`pwsh -File "$env:USERPROFILE\.claude\commands\autopilot_failcount.ps1" -Mode <reset|fail|status>`(经 junction 解析到 KB repo,换机/换账号都通)。
- autopilot 开跑**先 `-Mode reset` 清零**。
- 每个任务步骤判定后:这步**确实失败**→跑 `-Mode fail`;**确实成功**→跑 `-Mode reset`(连续失败,成功即断 streak)。成/败是你的语义判断,不是每个微动作都记。
- 脚本累计达 2 时输出 `AUTOPILOT_STOP`(带 🛑)并退出码 2:**见到 `AUTOPILOT_STOP` 或退出码 2,立即停止本次执行,把现状 + 卡点交用户,不得再试第 3 次**——要不要继续不由你判断。
- 兜底层不变:delete-guard hook + 权限方案 A 仍在 agent 层之下拦危险动作,autopilot 不放宽。
- **caller_id=today-loop 时**:计数由 today-loop 台账的 `consecutive_failures` + 本脚本双轨(脚本文件不被 compact,台账供 SELECT 回读,见判据 §3/§5)。
