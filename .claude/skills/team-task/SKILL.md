---
name: team-task
description: Claude/GLM 风险增强执行入口。读取 repo 根 team-task.md，把零散输入漏斗成冻结合同；GLM runtime 默认 MEDIUM，入口默认 AUTO 路由与 B 驱动，仅用户显式 HIGH/A/队形覆盖，关键验收门保持独立复核。公共入口仅用户显式输入 /team-task 时触发；team-workflow 受控委托见正文。
disable-model-invocation: true
argument-hint: "[continue-defaults]"
---

# team-task

把“零散 prompt → 风险登记 → 冻结合同 → 按任务形状执行 → 独立终审”固化成 Claude/GLM 风险增强入口。它不强制建队：实际拓扑为 T1/T2/T3，T4=AUTO 路由策略；本 skill 有写文件/建队副作用，公共入口接受用户显式 `/team-task $ARGUMENTS`，另一合法入口仅为下述受控委托。检测到 `CODEX_GLM|CLAUDE_GLM` 且用户调用本入口，即已按常设策略完成 MEDIUM 风险评估并授权默认 B+AUTO 主动推进。

## team-workflow 受控委托（Claude-GLM 专用）

- 用户准备首轮 team-task，或仅备冻结需求文档由 B 经 `/team-workflow run <文档>` 代起草；Claude-GLM 窗口 B 显式 `/team-workflow run [文档]` 即授权执行当前任务；B 的需求输入只有 team-task.md，无须基线文档或总轮数。A 稍后 `/team-workflow review <冻结文档> max-round=N` 才绑定独立基线和轮数，并在其范围内验收/生成后续任务；首轮计入 N。A 未加入时 B 完成首轮即等候，不自动开启第二轮。此为显式入口的窄扩展；公共 `/team-task` 的 `disable-model-invocation: true` 保持。
- 唯一内部适配器为同级 `team-workflow-run/SKILL.md`。它必须先经 `team-workflow/scripts/workflow.py enter` 接棒及 `permit`，核对 repo、真实 GLM session、当前 run/round、原文 hash、B 归属与停止状态；无有效许可不得借 Read 本文启动执行。
- 获许可后完整读取并执行**本文件同一份 P0-P6**，不调用禁用 model invocation 的 `Skill(team-task)`。P0 参数视为空；用 helper 的 `team_run/source_id` 作为 `run_id/source_block_id`，不重新生成；恢复须原 B 的用户显式 resume 单次 token，按既有阶段/合同链继续。
- 此委托场景中，B 和本轮陪审以 task source + 生效合同为 REQUIREMENTS，只验本轮 done_when；不要求 B 冷启动追读、冻结或核验 A 的独立用户需求文档/criteria。A 承担原始基线全量覆盖，把具体执行要求写进下一轮任务；repo 环境/权限硬规则和实际生产 skill 仍适用，不能借分工跳过。
- P0.5/P5 的显式入口依据在委托场景映射为上述 B 的 run 启动授权；仅已有一手 `CLAUDE_GLM` 证据可继承常设 MEDIUM 与 B+AUTO，全部风险/FACT/四红线/陪审/增补和 P6 门保持。失败累计从 workflow 载入并带回，换轮不重置。
- 本轮 `COMPLETE + P6✓` 且团队静止后由适配器 `finish` 落盘交接并通知 A；A 尚未加入也照常保存，B 挂后台静默 wait。A 晚到直接验收，只有独立核原始基线后才发布下一轮。session-new 仅固化文件；不得关闭/清空 B。内部 `/pin` 仍用于记忆，不用于唤醒 A。

## 漏斗控制流（P0→P6；细则单源见 `funnel-gate.md`）

0. **P0 · run bootstrap（任何新写入前）**：只接受空参数或 `continue-defaults`，其它参数 fail-loud。完整读 `./team-task.md`；缺文件/「本次任务」空则停，不编任务。识别最后一个显式 source block；legacy 未标记输入只可无损包进 source marker，`source_block_id=src-<sha256前8位>`。生成 `run_id=YYYYMMDD-HHmmss-<source_sha前8位>`。
   - 根 `team-progress.md` 命中同 `run_id+source_block_id` 且 `run_status=ACTIVE` → 按阶段标记重入；三者不匹配禁止跳段。同三元组 `WAIT_HUMAN` 且用户明确续做同一任务：合同语义不变时，先记 `RESUME_AUTHORIZED`（入口/日期/指令摘要）并改回 `ACTIVE`；scope/done_when/写权限/红线变化时，保持 `WAIT_HUMAN`，先追加并校验 addendum、核对基础 `contract_id` 且更新 `effective_contract_id`，再同笔记录 `RESUME_AUTHORIZED` 并切 `ACTIVE`。顺序标识：`CONTRACT_CHANGE_RESUME_ORDER=WAIT_HUMAN→ADDENDUM_VALIDATED→RESUME_AUTHORIZED→ACTIVE`。`COMPLETE+P6·` 只许恢复收尾并原子收成 `COMPLETE+P6✓`；`COMPLETE+P6✓|HALTED`，或 `WAIT_HUMAN` 后启动新任务 → 先按 NNN 规则归档、确认成功再重置；非空且无合法终态 → KO「旧 run 未收口」，**不写新标记**。
   - 初始化头写 `run_id/source_block_id/contract_id(pending)/effective_contract_id(pending)/run_status=ACTIVE` + 漏斗行 + `P1已核事实`，并保留「进度日志/当前现状/下一步/卡点/漏斗默认·待确认/自主裁决(B)/OPEN_BLOCKERS/PENDING_HUMAN_NONBLOCKING/复盘位」骨架。每过一阶段立刻落盘，不攒到收尾。
0.5. **P0.5 · 风险登记（P1 前必写，非重复问询门）**：仅当一手证据确认 `author_runtime=CODEX_GLM|CLAUDE_GLM` 且用户未显式指定等级时，按 2026-09-04 常设策略登记 `risk_class=MEDIUM / risk_owner=USER / risk_source=USER_STANDING_POLICY_20260904 / runtime_policy=GLM_ALLOWED`；用户显式 MEDIUM/HIGH 时按显式值。`NATIVE_*|OTHER` 未显式分类仍返回 `WAIT_USER_RISK_CLASSIFICATION`，不得冒用 GLM 常设授权。AI 不得降级，runtime 不凭自称或文风猜。
   - `CODEX_GLM|CLAUDE_GLM|OTHER + HIGH` 立即返回 `CUTOVER_NATIVE_REQUIRED`（OTHER 在证明为 native 前不得挂名 `NATIVE_ONLY`）。冻结范围内具备已验证备份、trace、确定性断言、适用签字门且无对外/DLP/权限影响的可回滚 repo 写入保持 MEDIUM；只有运行中新出现且超出入口授权的共享 contract §3.2 高后果事实才标 `HIGH_SUSPECTED` 并停。
   - 风险 envelope 逐字落 `team-progress.md`，随后写入 frozen contract；已确认 GLM 时不因“用户本 run 未重复分类”返回 `WAIT_USER_RISK_CLASSIFICATION`。共享口径唯一指针：`D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/.agents/mc-expert-common/review-contract-v2.md`。
1. **P1 · 控读自答**：先定点 Grep/Read 自答可查事实；预计跨目录或 >10 文件才派一次性 Explore。把已核事实与证据指针落盘后标 `P1✓`，断线不得白跑重查。
2. **P2 · 单轮收口**：用 Skill 工具直接调规范名 `chop-task`（不走 `/chop` command 壳）：`caller=team-task mode=contract-only run_id=<run_id> source_block_id=<id> source=team-task.md output=team-task.md profile=auto input_policy=<initial|answered|continue-defaults>`。chop 必须走完整 kickoff gate；A 模式的决策类才用 AskUserQuestion，默认 B 下非阻断 PREFERENCE 采用安全默认并留痕，不询问 A/B、team/solo 或队形；不可默认的阻断 FACT 按 `funnel-gate.md` 生成 `team-progress/questionnaire-<run_id>.md`。没有墙钟超时：只有用户填答后重入，或显式 `/team-task continue-defaults`，才继续。
   - 用户独有事实、scope/done_when/权限/外部真相身份不得默认；只允许明确标为 PREFERENCE 且带安全默认的未答项降级。降级记「漏斗默认·待确认」，**P5 前不得冒记 `自主裁决(B)`**。仍有阻断事实则停在 P2。
3. **P3 · 冻结合同**：chop 以 `run_id+source_block_id` 幂等追加唯一 `contract_id/status=frozen` 基础合同块（不覆盖零散 prompt、不打 chop consumed）；多依赖检查点/多执行体实质交接/跨会话任一命中才完整集，否则最小集。首次令 `effective_contract_id=contract_id`。冻结后用户合法改变 scope/done_when/允许写或红线时，第一次依新授权执行可变动作前追加 append-only addendum（授权指令逐字引文 + 授权时间/会话 + 被取代条款 + 新条款），令 `effective_contract_id=addendum_id` 并同笔刷新 progress 的过期陈述；P3 重入和 COMPLETE 前均运行 fixture 的真实合同链/hash 校验。
4. **P4 · 二轴路由**：按 `funnel-gate.md` 分开计算 `coordination_score`（选 T1/T2/T3）与 `assurance_profile=BASE|ENHANCED`（只调复核强度）。记录 `recommended_topology`；默认 `routing_mode=AUTO`，实际仍为 T1/T2/T3；用户在任务中显式指定队形时直接记录覆盖，不再弹一次选择。
   - 先按输入、依赖和文件所有权检查独立工作块，再决定 lead 独做；不能用“计划全部自己做”证明只能串行。有输入明确、能独立落盘且整合成本小的工作块时，可按现有路由试用一个临时实现 agent；不强制每轮派人、不默认增设 planner，不为展示并行重复重型测试。分派写明输入、责任文件/共享文件协调、交付物和禁止范围，告知同仓库还有其他修改者，不得回退他人改动；lead 整合，实现者不作自己产物的唯一终审。模型按当前可用能力、风险及授权选型，低风险盘点/格式核查可用适配的较低成本模型；业务规则、金额语义与关键验收不能只按成本选。单 profile OA 和依赖前步输出的写入/回读继续串行，额度或资源不足时减并发。
5. **P5 · 登记门**：默认 `drive_mode=B / routing_mode=AUTO`，用户仅在任务开始时显式声明 A 或指定队形才覆盖。登记前机械核验 frozen effective contract + OPEN_BLOCKERS 空 + 阻断 FACT 闭合；不满足即停，不能靠默认 B 越过。记录 `routing_mode / recommended_topology / realized_topology / assurance_profile / drive_mode` 后标 P4/P5；`continue-defaults` 不构成 B 授权，显式 `/team-task` + 用户常设策略才构成。
6. **P6 · 执行、增强终审与收尾**：T1=常驻 planner+coder+mxp；T2=常驻 coder+mxp，命中负例/四态取证门时强制一次性 planner；T3=lead 直做+每个关键门一次性 reviewer；T4 按 `realized_topology` 执行并同时留推荐/实际值。关键终签、迁移、权限/发布、schema/API 冻结的独立复核不可跳、不可静默自审降级。
   - **B 模式失败漏斗 `FIRST_FAILURE_MXP_REVIEW`**：首次命中稳定 `failure_key` 且不属红线①②④时，先记 `failure_count=1`，不得直接升人工或无陪审换路；T1/T2 问常驻 mxp，T3/常驻不可用派一次性 mc-expert（`REVIEW_PROFILE=HISTORY`），交齐判据原文、原始失败证据与一个待判问题。mxp 给候选成功率排序与单一默认落点；lead 先试首选并记 `依据=mxp陪审`。若同 key 达 `failure_count=2`，仍不升人工：改试尚未使用的次选；没有可行次选则只允许再问一次 mxp 补一个新落点。第 3 次同 key 失败记 `failure_count=3` 后才按红线③熔断。失败预算共 3 次，换建议、agent、session 均不重置；BASE/ENHANCED 同规。mxp 投递重试一次仍无正文则 `WAIT_HUMAN|BLOCKED`，不得自审续命。
   - `assurance_profile=ENHANCED`（GLM 合法 MEDIUM 必然命中）时，最终 artifact 冻结并计算 SHA-256 后，必须启动一个 **fresh、一次性、只读** mc-expert，按共享 `review-contract-v2.md` 交齐 `REVIEW_PROFILE=ENHANCED_FINAL / AUTHOR_RUNTIME / 风险 envelope / ARTIFACT_MANIFEST / REQUIREMENTS / LIVE_BASELINE / VERIFICATION_EVIDENCE / UNVERIFIED_SCOPE`。不得复用常驻 mxp 的旧上下文，不喂 coder/lead/planner 的 PASS 预判或上一 reviewer verdict。
   - 只有 `VERDICT=GO + HASH_VALIDITY=VALID + UNVERIFIED_SCOPE=NONE + 八个承重检查全过` 才可终签；`GO_WITH_CHANGES` 修后必须以新 hash fresh 重审。`CUTOVER_NATIVE_REQUIRED / CROSS_STACK_REQUIRED / BLOCKED_EVIDENCE / reviewer 不可用` 一律转 `WAIT_HUMAN|BLOCKED`，不得降级为自审。
   - 正常完成时先保持 `run_status=ACTIVE / P6·` 跑收尾 loop，三段预判/跳过理由逐段写入 `## 收尾复盘`；最后同一次落盘原子写成 `run_status=COMPLETE + P6✓`。等待人工/熔断写 `WAIT_HUMAN|HALTED + P6·`。不得先写 COMPLETE 再跑收尾，避免断线留下假完成。

**A/B 衔接唯一口径**：用户显式调用 `/team-task` 即按常设策略批准本 run 默认 B+AUTO；推荐非 team 可自走、推荐 team 可自建并留痕。只有任务开始时显式声明 A 才逐决策点问；这份授权限当前 run，不扩成脱离入口的常驻授权。

## 建队执行（通用要求 · 本 skill 权威）

- 前提：本 repo 已开 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`。若用自然语言建队后没 spawn 出 teammate，提示用户确认开关已开 + CC ≥ v2.1.32（`claude --version`）。
- 按 `realized_topology` 建队：T1 常驻 planner（规划+取证）/ mc-expert（KB 挑战）/ coder（实现）；T2 常驻 mc-expert/coder，需负例或四态取证时临时派 planner；T3 不建常驻 team。关键背景写进 spawn prompt（teammate 不继承 lead 对话历史）；mc-expert 的过程咨询短锚必须交齐共享 `review-contract-v2.md` 的 v2 六字段并写 `REVIEW_PROFILE=HISTORY`。
- **放权深度**：A/B 驱动模式的完整流程（选项文案 + 四铁律 + 三条恒定不变量）**写死在本 skill（见下「B 模式（深度放权）完整流程」节）= 权威单一版本**，不依赖各 repo team-task.md 是否写到——这是「无弹窗」与「不被偷偷替你拍板」之间的安全阀，不能靠每个 repo 各自补。只有**真·repo 专属落地**（落点路径等）才留给该 repo team-task.md。
- **team-progress.md**：lead 当唯一写手，teammate 经 mailbox 汇报、lead 汇总落根目录 `team-progress.md`；只读角色不自己写文件。每完成一步更新（做了什么 / 现状 / 下一步 / 卡点）。骨架的三累积区为 `自主裁决(B)` / `OPEN_BLOCKERS` / `PENDING_HUMAN_NONBLOCKING`，另有「漏斗默认·待确认」与复盘位；spawn 只带快照指针。断线按 P0 的 run 三元组续工作内容，**活 team 状态续不回**（teammate 要重 spawn）。
- **长正文回传 / 里程碑汇报（含只读角色）**——建队 spawn prompt 里对每个 teammate 写明下列：
  1. **传输层**：teammate 完成后**必须显式 `SendMessage` 发给 lead**——别依赖 idle 通知（只带一行摘要、不带正文）。〔2026-06-17 实测：显式 `SendMessage` 单条 ~46KB 全量逐字到达——通道与容量没问题。〕
  2. **承重层（2026-06-18 修订旧「不是落盘」口径）**：显式 `SendMessage` **必要不充分**。实证：①投递 flaky——同一 coder 同 session 既有完整正文(1730字)到达、也有连 3 轮只到 idle 零正文(mc-debug07)；②teammate 可能撞 session 限额在汇报前被截断(本次两 coder 实测)。故**有 Write 的角色(coder)：有产物的报告先写盘 + `SendMessage` 发指针，承重靠盘**；只读角色(planner/mc-expert，无 Write、opus)仍发全文（同 session 6.7k/3.5k/5.2k 字均逐字到达，可靠）。
  3. **lead 兜底**：「产物/报告已落盘」节点 lead **默认直接读文件验收**，正文连等 ≤2 轮询拿不到 → 直接自核产物（Bash/zipfile 实扫），别陷进反复 nudge 的递减回报。
  4. **诊断纠偏**：本环境 team = `backendType: in-process`（**非 tmux**）。失败是同 session 投递 flaky + 可能 session 限额截断，**不是** tmux 轮询/通道容量/agent 漏发工具调用——别查 pane、改 tmux、分块正文、或加「记得发工具」这种无效咒语。
  5. **★T3 选型纠偏（最高杠杆）★**：若是**单点串行流水线**（一个执行体握全量从 M1 干到 M4、其余角色只前端把关一次），推荐 T3——执行体隔 flaky mailbox 汇报是自找失败面。P5 已登记 T3 后就地 solo 执行（不绕 todays-task、不重敲命令、不丢授权）。**陪审不省**：前端 plan/素材门、每个关键验收门交用户前、mode-B 自主裁决点仍派一次性 `@agent`（mc-expert/planner）带三件套把关。team 留给真并行/真多专长协作。
  〔机制实证版单一权威诊断见 KB `Mc-Expert-repo/references/agent-teams.md`「idle-零正文：故障模型 + 兜底策略」节〕

### spawn 短锚与里程碑五件套（防漂移承重件）

- **spawn prompt = 短锚（≈10 行）+ 指针，不塞任务全文**：①角色定位一句 ②任务终态一句 + 当前检查点 ③`team-task.md`（及判据文件）路径指针 ④**第一动作 = 完整读 team-task.md**（teammate 不继承 lead 历史，spawn prompt 即宪法；每次读 live 文件，天然防任务文本漂移）⑤汇报纪律一行（见下分档）⑥B 模式红线一行（权限类命令不在中途发起、攒待人工）。失败陪审另加：`failure_key / failure_count / 已失败方案与原始证据 / 已试候选 / 待比较候选`，并要求 HISTORY mxp 输出成功率排序 + 单一默认落点。三清单等台账状态只给 team-progress 快照指针，不复制内容。
- **主动纠偏三问**（teammate 接新活 / 新检查点 / 关键交接 / 声称完成前必答，随短锚以一行引用）：①当前动作明确服务哪个检查点、哪个未满足的 done_when？映射不上立即停下重锚主线；②是否把「明确不做」或范围外优化偷偷变成必做？③正要声称「已完成」的内容，实际实现、文档、可复验证据三方一致吗？
- **汇报分档**：日常 mailbox 汇报保持轻量（收尾只报 完成/卡点/下一步，**不变**）；仅**里程碑 / 检查点完成 / 关键交棒**须**五件套**——①当前检查点与 done_when 映射 ②实际改动 ③实际验证与证据路径 ④三条纠偏自问结论（含是否复用已审模式）⑤三清单（自主裁决(B) / OPEN_BLOCKERS / PENDING_HUMAN_NONBLOCKING）当前状态。
- **失败交接带稳定 `failure_key`**（`stage|error_family|error_code|unmet_done_when`，禁 PID/时间戳/随机文案——保证同源失败可机械累计）。key 的稳定定义借用 double protocol §自主轴 7（`Mc-Expert-repo/.agents/double-session-common/protocol.md`），但 team-task 的失败预算以本 skill 为准：第 3 次同 key 才熔断，不沿用 double 的两回合阈值。

### 关键验收门（每门独立 reviewer；验收背景 = 三件套）

- 每个关键验收门交用户前安排独立 reviewer：T1/T2 可用已在队内且未执行该产物的 reviewer，T2 负例门与 T3 用一次性 `@agent`（mc-expert/planner）。**三件套 = 判据字面原文 + 原始证据（产物路径/实际输出/行号）+ 待判问题**；**禁喂已采信结论**——不给 coder 自报 PASS、不给 lead 倾向性表述；用户拍板的边界约束可给（那是约束不是结论）。
- **分轨**：T1=常驻 planner 取证，风险扳机才叠 mc-expert；T2=普通门由 mxp 独立复核，命中负例/四态取证强制一次性 planner；T3=lead 自跑证据+一次性 reviewer。planner 已在场不为同一证据面机械叠第二 reviewer；独立 reviewer 不可用则 `PENDING_INDEPENDENT_REVIEW/WAIT_HUMAN/BLOCKED`，不得自审冒充。
- **终审例外**：上条只管过程门。`assurance_profile=ENHANCED` 的最终终签始终另起 fresh `mc-expert`，执行共享 `review-contract-v2.md` 的 `ENHANCED_FINAL`；常驻 mxp 的 HISTORY/过程结论不能抵扣终审。

- **效率/通信**：能匹配已有 role/skill 就直接走、别从零规划；需盘点多文件派 Explore subagent、别自己串行翻；不复述 team-task.md、直接动手；收尾只报 完成 / 卡点 / 下一步。
- 收尾让 **lead** 跑 `Clean up the team`（先 shutdown 所有 teammate）。

### 验收签注四态（done_when 逐条；一手 > 二手）

- **标尺**：拎 done_when 字面原文逐条映射到实际行为/产物——不取 coder 自述/验收报告/docstring 二手结论；验收报告或陪审结论与独立复跑冲突 → **信独立复跑**，差异逐条列给用户、不擅自调和。「学习型 repo 宽严」不是漏判挡箭牌：宽严只影响要不要现在修，不影响达没达标。
- **四态**：`PASS_DYNAMIC` 本 run 独立复跑看到对 / `STATIC_ONLY` 仅静态推断未跑负例（= reflexes 2026-08-05「仅静态推断、待动态复跑」态）/ `FAIL` 真跑看到错 / `BLOCKED` 想跑跑不了·环境阻断（非 FAIL 非 PASS，落「待动态复跑或交用户」）。
- **STATIC_ONLY 三锁**：①禁写成「达标/完成」；②强制浮到最终交付物待确认项（挂恒定不变量 1）；③准入仅限不存在有意义的动态验证、或当前环境客观不可用/不安全/超出授权——必须记录原因、所缺条件、可用时的复跑命令/步骤，**方便/成本高不构成理由**（签它比跑负例便宜 ≠ 准签）。
- **负例执行体**：T1 常驻 planner；T2 一次性 planner；T3 lead 在系统临时目录隔离副本真跑后交一次性 reviewer 独立判证据。判据含「可靠失败/缺 Y 中止」必须看到真失败。边界：①不动工作树正本/交付产物；②取证≠编排，gate 拍板留 lead；③coder 自检可用，但不得成为关键终签唯一证据。

## 不要做

- 不复述 team-task.md 全文，直接说"开始执行 X"后动手。
- 不让 teammate 碰编排权 / 替用户做「推翻已封决策」级判断。
- 不把 P5 登记门重新变成 A/B+队形重复问询；默认 B+AUTO，A/指定队形只认用户任务开始时的显式覆盖。B 按默认>成功率>易回滚自走并留痕，仅 4 红线上报；不把 `continue-defaults` 偷换成 B 授权。

## B 模式（深度放权）完整流程（最新确认版 · 本 skill 为权威，team-task.md 不再各存一份）

> 2026-06-18 用户确认：A/B 驱动流程的**权威单一版本**在此，各 repo team-task.md 只留「本次任务 + repo 专属落点」，不再复制本节（曾因各存副本而漂移到不同版本）。

**P5 默认策略（2026-09-04 用户终裁）**：显式调用 `/team-task` 默认 **B · 深度放权 + T4-AUTO**，不再弹 A/B 或队形选择；planner/mc-expert/coder 报低置信/无先例/拿不定主意时，lead 按「**默认项 > 历史成功率最高项 > 最易回滚项**」拍一个并继续，逐条记进 team-progress。只有用户在任务开始时显式声明 **A · 人工驱动**，才让所有决策点停下并由用户批 plan；显式指定队形则直接覆盖 AUTO 并登记。

**选 B 驱动落地（四条铁律，缺一不可）**：
1. **不确定 ≠ 上报**。未发生失败的普通裁量，lead 按「默认 > 成功率最高 > 最易回滚」拍一个继续；低置信且无法选出下一步，或首次出现非红线失败，则强制走 `FIRST_FAILURE_MXP_REVIEW`，拿到 mxp 的排序与具体默认落点后继续，仍不转交用户。
2. **拍了就记**（放权对价，不可省）。每个自主裁决在根 `team-progress.md` 的 `## 自主裁决(B)` 区追加一行：`决策点 / 候选项 / 选了哪个 / 依据(默认|成功率|易回滚|mxp陪审) / 置信度`；失败陪审另记 `failure_key / failure_count / mxp候选排序 / 本次选项 / 尝试结果`。这是用户事后批量复盘 + 快速纠偏的唯一入口。
3. **只有 4 条红线才停下问用户**（其余一律自走）：① 销毁性/不可逆操作（多文件删除、覆盖无备份——遵 CLAUDE.md 删除硬规则）；② 对外交付物 / 触碰 Ldterm 明文合规红线；③同一 `failure_key` 在 mxp 首选与次选/补充建议均失败后达到 `failure_count=3`；④ 推翻 KB `decisions/` 已封决策。第 1/2 次非红线失败不是人工门；①②④仍立即停，不得以陪审为由先试。**①②类会触发权限框的命令（rm/删除/无备份覆盖/伸 `~/.claude`·系统·敏感目录/对外）绝不在 B 自主流程中途发起——会死等缺席用户 + 死锁后台 agent；一律攒「待人工处理」后置到人工门，halt 走「不执行该命令 + 落盘报告 + halt 上报」、不靠阻塞式权限框（后置的是决策权，非后置着自己偷偷补做）；forensic/排查也不例外（别用含 `rm`/伸敏感目录的命令去查问题）。详见 KB `decisions/autopilot-defer-perm-to-human-gate`。**
4. **收尾一次性**把「自主裁决(B)」及失败陪审的采纳项/结果清单交回用户复盘，**别在过程中逐条确认**。

**两模式都不变的硬线**：teammate **不碰编排权**、不替用户做「推翻已封决策」级判断；CLAUDE.md 的删除 / Ldterm / COM 硬规则两模式下都**不被放权覆盖**。

### 三条恒定不变量（跨所有 repo 的安全阀，换执行者 / 换任务都不许漏）

1. **自主裁决必须「浮」到交付物，不能只埋进 team-progress。** B 模式 lead 替用户拍的判断点（D1/D3 类、口径取舍、低置信选型……），除记进 team-progress 的「自主裁决(B)」区外，**必须在最终交付物汇报里显眼列为待确认项**，供用户验收时一句话能翻。team-progress 是内部文件、用户不看——只埋进去 = 偷偷替用户拍了板。这是「无弹窗」与「不被偷偷拍板」之间的安全阀，不能靠运气（同反射「交付必显式列 pending 项」）。
2. **B 只压「循环内决策门」，不压「用户显式定义的交付/验收门」。** 两类门要分清：①循环内决策点（plan 审批、低置信选型）——B 压掉、自走；②用户显式定义的交付/验收门（如素材审核门、成品人工验收）——**B 不压，照常产出给用户**。换个门结构时，别因为选了 B 就把用户想要的门跳过、也别把用户的验收门误当循环决策吞掉。
3. **验收只认一手证据，STATIC_ONLY 不得报完成。** done_when 逐条按「验收签注四态」签注；没独立复跑过的判据最多 STATIC_ONLY，交付汇报里显式列为待确认项——不许写「已完成/达标」。

> 机制细节、为什么这样设计：见 KB `Mc-Expert-repo/references/agent-teams.md`「新手 FAQ」+ `Mc-emoji/[feature-03-take-a-nap]/sub-plan-stage3-agentteam-spike.md`。

## 收尾 · 微型 loop：mc-update → pin → session-new（Clean up team 之后、每次正常收尾必走）

team 清理完（lead 跑完 `Clean up the team`）、本次任务**正常收尾**后（完成、或带卡点上报但未熔断），按 **mc-update → pin → session-new** 顺序跑一遍收尾固化。三个环节都是**先预判、再决策执行**，不是无脑跑；目的是省掉用户每次手敲 `/mc-update`、`/pin`、`/session-new`，并把本次任务里 **capture_hook 词表漏网的纠正**捞进 feature-05 捕获网。**全程由 lead 执行**（teammate 此刻已 shutdown、不派给他们——pin 陪审走临时 `@agent`(mc-expert) 一次性，见下）。

**触发边界**：
- 正常收尾（完成 / 带卡点上报）→ 进本 loop。
- **熔断 / halt 交用户 / 任务无实质进展**（红线③同一 failure_key 第 3 次失败熔断等）→ **跳过 mc-update 和 pin**（mc-update 纪律就是"只在任务完成后走"、pin 是"捞本次纠正残留"——未完成/无产物两段都没意义）；但 **session-new 仍走**——预判里点明"本次未正常完成，建议 session-new 固化中断/卡点现场 + team-progress 归档指针以便接续"。

**mc-update → pin → session-new 的顺序语义**：mc-update 先固化"本次经验/记忆层"；**pin 居中**——捞 mc-update 判定后仍漏网的纯陈述式纠正（若 mc-update 判"无新可固化"，pin 预判多半也是"无漏网纠正"）；session-new 最后固化"本次讨论/状态层"做交接（含 team-progress 归档指针），并落 pin 段报告行（见下）。三者职责不重叠（mc-update 偏 memory/feedback、pin 偏 feature-05 燃料补漏、session-new 偏 plan/状态文件 + 归档指针）。

**每个环节两步走**：

1. **预判（必带，不能套话）**：基于**本次任务的实际产物**（team-progress、teammate 产出文件、记忆候选等）给一句话预判——"有/没有可固化（mc-update）/ 漏网纠正（pin）/ 可交接（session-new）的东西，建议跑/不必跑"+ 一句**具体理由**。每次任务的明细、中间产物、来源入口都不同，预判必须落到本次实际，禁止"建议跑 mc-update"这种通用套话。
2. **决策 + 执行**：
   - **A 模式（人工驱动）**：lead 用 AskUserQuestion 弹问用户，把预判写进选项描述（让用户看着预判拍板）——**判断权在用户**。选"是" → **用户不再手敲**，lead 直接用 Skill 工具调用 mc-update / session-new 执行（pin 段见下、走陪审通道）。选"否" → 跳过。
   - **B 模式（深度放权）**：lead **不转交用户**，按铁律 1「默认 > 成功率最高 > 最易回滚」自己判 mc-update / session-new 要不要跑，逐条记进 team-progress 的 `## 自主裁决(B)` 区 + 浮到交付汇报的待确认项（恒定不变量 1）。**熔断场景仍按上面"触发边界"处理**——不让 B 模式给 mc-update 续命。

**★ pin 段（居中 · feature-05 补漏层 · lead 执行）**——**判据单一指针见 KB `Mc-Expert-repo/references/收尾loop判据.md`**（PIN/DROP 判据、方案 a 去重、掉线降级、陪审 spawn 五要素都在那；本 skill 只写控制流、不抄判据，改判据只改那一处）：
1. **预判闸（必带）**：一句话判"本次有无词表漏网的纠正迹象"——**无迹象直接跳 pin 段、不派 mc-expert**（省陪审成本）。有迹象才往下。team 运行期 **STATIC_ONLY 未复跑数量 / 自主裁决(B) 分布**是预判输入之一（漏网纠正迹象的高发区）。
2. 有迹象 → 回顾本次任务列纠正候选（**认不出不硬造**，pin.md 铁律）。
3. **去重（方案 a）**：Grep/Read 本会话 `live-candidates.<session>.jsonl`，capture_hook 已抓的剔除。
4. **派 mc-expert 陪审**：team 已 shutdown，**临时 `@agent`(mc-expert) 一次性**（用完即释，呼应建队执行「陪审不省」）；候选 ≥2 条一次 spawn 全给、逐条判，单条才单发。spawn prompt 五要素 + 红线"只给 PIN/DROP+依据、不复述纠正、不顺势修错、**不附概率分**"见判据指针 §5。
5. **掉线降级**：mc-expert 零正文 / Connection closed → 重试 1 次 → 仍失败 → 该候选落 `Loops/review-queue.md` 交用户补判（**不硬 pin、不 DROP、不连试 ≥2 次**，细则见判据指针 §4）。
6. **落账**：只对陪审 PIN 的跑中央单写入口：`python "D:/Downloads/Mc Claude Code Workshop/Mc-emoji/[feature-05-loop-self-improvement]/历史扫描/pin_capture.py" --pin-log "D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/.claude/auto-memory/pin/pinned-candidates.jsonl" --platform claude --corr ... --ai ... --note ... [--followup ...]`；lead 调用前自校验 fail-loud（陪审缺 PIN/DROP/纠正原文/依据 → 不硬凑参数，见判据指针 §6）；候选为空 → 静默跳过。中央 sink 缺失/不可写时明确失败，不回退旧 sink。
7. **报告行**：pin/drop/掉线降级任一发生 → 在 session-new 段产出的 plan 里记一行 `pin N / drop M / 降级 K 落 review-queue`。

**一致性约束（堵 B 模式 lead 自判跳过偏差）**：
- 收尾三段**每段预判一句话 + 跳过必给具体理由**，并逐段落入 `team-progress.md` 的 `## 收尾复盘`，不许只在聊天汇报、不许套话跳过。
- **B 模式下 pin 段预判闸判"无迹象"可直接跳**（事实判断）；**但只要"有迹象"就必须派陪审、不许自判"算了不 pin"**——靠本 checklist 收窄走样空间，**但不保证**（要保证"必跑"只能路线 C Stop hook，本版未实现）。

**两层判断边界（别越权）**：本 loop 只判"**要不要启动** mc-update / pin / session-new"。启动之后——写不写记忆、pin 哪条、产不产 plan——是 mc-update / pin_capture / session-new **各自流程的职责**（mc-update 有频次/去重两道闸门、pin 走判据指针、session-new 有自己的四步），team-task 收尾不替它们判、也不重复其内部逻辑。

**B 模式下 session-new 的边界**：lead 判"跑 session-new" = 走固化交接流程（产 plan + 更新状态文件 + team-progress 归档指针），**不是强制清空/重开 session**——真正关 session、重开仍由用户操作，lead 不替用户决定何时真关。

**session-new 段幂等（防 loop 重入产重复 plan）**：session-new 重入前查本会话 plan 是否已存在（同名/同任务），存在则跳过、不堆重复/空 plan。

---

## 附录：team-task.md 模板（单一真源）

**流程权威声明**：本 skill 是 team 编排流程（A/B 驱动、关键验收门、四态签注、收尾 loop）的单一真源；repo 侧 team-task.md 中旧的通用模板 / 通用编排流程副本如与本 skill 冲突，以本 skill 为准——repo 专属任务、路径、硬约束和用户明确验收标准继续有效。完整集②内嵌的**任务内容冲突优先级**（用户最新明确指令 > repo 硬规则/已封决策 > 本次冻结任务 > 检查点计划 > 历史说明）是任务内容的优先级，别与「skill = 流程单一真源」混写。

**最小集（默认档，全文照抄）**：

> **# 任务：<一句话标题>**
> **## 本次任务**
> - 终态一句话：<做完后的结果状态；禁「重构/实现/优化」动作词>
> - 本轮做 / 明确不做：<1-3 句> / <排除项逐条，与做什么同等重要>
> - 允许写 / 只读 / 禁止：<路径/动作>
> - 红线：<四红线 + 本项目禁止动作>
>
> **## done_when（字面可判；至少 1 条可外部取证）**
> - [ ] D1: <结果属性>（验证：<命令/文件/查询及预期>）

**完整集 7 块骨架**（仅块名 + 每块 1 行要点，照 KO 防漂移指南 §4/§6 投影、不整段复制）：①任务终态（结果状态非动作词）②权威源·主线·范围（repo 绝对路径 + 冷启动必读 + 冲突优先级一行 + 本轮做/明确不做 + 允许/只读/禁止三态路径 + 保留无关工作树改动）③全局 done_when（每条结果属性+验证方式；单检查点通过 ≠ 全局完成）④检查点路线（depends_on / scope / local_done_when / evidence / novelty / expert_review；当前入口明确）⑤红线·禁止·人工门（四红线 + 项目禁止 + 已前置授权 vs 后置 PENDING_HUMAN_NONBLOCKING + 阻断 done_when 的事项不得后置伪装完成）⑥纠偏三问与陪审扳机（指针到 skill 正文，不复制）⑦交接口径（指针到「里程碑五件套」，不复制）。
