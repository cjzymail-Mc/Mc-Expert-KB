---
name: team-workflow
description: Claude-GLM 双窗口有限轮接力。A 按冻结文档规划和独立验收，B 执行现有 team-task（可按 run 参数代起草首轮）；任务交接即时唤醒，空闲静默等待一小时后续待机。用于用户要求 team-workflow 的场景。
disable-model-invocation: true
argument-hint: "run [<需求文档>] | review <冻结文档> [max-round=3] | status | resume | stop"
---

# team-workflow

仅适配本机 Windows 的 **Claude Code + GLM、两个独立交互 session、同一 repo**。A 是规划验收窗口，B 是执行窗口；这与 team-task 的 A/B 驱动模式不同，内层默认仍为 B+AUTO。不使用 `/pin` 传消息；`/pin` 原有记忆职责不变。

## 唯一启动顺序：准备 → B 执行 → A 加入

先备一份用户认可的冻结需求文档；首轮任务经两条路径之一进入 repo 根 `team-task.md`（含「本次任务」与 `done_when`）：

- 路径一（讨论窗口代写）：在讨论窗口（可以是 Codex）生成冻结文档，并写好尚未执行的首轮任务。讨论窗口只准备文件，不加入双窗口通信。
- 路径二（B 代起草，简化启动）：用户只备冻结文档，B 用 `/team-workflow run 需求基线.md` 在 init 前自行起草首轮任务写入 team-task.md（起草规则见 `run` 条目）。

随后：

```text
先启动 B：/team-workflow run [需求基线.md]
稍后启动 A：/team-workflow review 需求基线.md max-round=3
```

**B 是执行者，任务输入只有 team-task.md；A 是裁判，输入是用户指定的基线和 B 的实际产物。** 除 `run <文档>` 为起草而显式读取该文档外，B 不寻找、读取、冻结或校验 A 的基线文件；即便起草时读过，也不据此绑定基线、生成 criteria 或决定轮数——这些仍只在 A review 时冻结，执行期间的验收依据始终是 team-task 与生效合同。B 也不决定总轮数；本轮任务所需的具体执行条款由讨论窗口/A 写进 team-task.md，或由 B 按用户 run 参数的显式授权起草。

用户在 B 显式启动 run，授权执行当前任务；A 尚未加入时只允许首轮，完成就静默等待。A 的 review 才绑定独立基线和 max-round（默认 3、上限 20），授权在这份基线范围内验收及生成后续任务。每轮 = B 完整执行一次 team-task + A 完整验收一次，已开始的首轮计入上限；全部达标即提前结束，最后一轮仍须验收。不得为了凑轮数添加优化任务。

这里的 run 是原 team-task 的 workflow 入口：B 用这一条命令代替直接 `/team-task`，仍执行原生产流程。不要先裸跑 `/team-task` 再动态接管。没有 A 先规划的第二种模式，旧 `/team-workflow plan` 不再使用。

本次会话 ID：`${CLAUDE_SESSION_ID}`。helper：`${CLAUDE_SKILL_DIR}/scripts/workflow.py`。命令均用 `python`，所有路径引用完整路径并加引号；不使用 WindowsApps `python3`。先读 repo 的 CLAUDE.md/AGENTS.md；技能相关正文见下文按需路由，不读脚本实现来重新设计机制。

运行前须能用 Claude **Bash 的 `run_in_background:true`**，收到原窗口的后台任务完成通知。若该工具能力被关闭、session ID 未替换、helper 无法从当前 session 原始 JSONL 证明 GLM，报具体阻断并停止；不修改全局 settings/hook，不降级为刷屏轮询。适用于交互窗口，不用 `claude -p` 承载一小时待机。

## 初始化与当前轮调度

首次使用读 [references/relay.md](references/relay.md) 的命令和 JSON 格式。`run`、`review`、`resume` 都在**本窗口主会话**执行，不能 fork 成 subagent。

- `run [<需求文档>]`：用户明确启动**新任务**时，先按 [新任务自动收尾 §5](references/relay.md#5-新任务启动前自动收尾) 调 `prepare-new`：终态直接归档；无人执行的中断任务保留原始证据后记 CANCELLED 并归档；正在执行或情况不明时报告具体占用。使用本窗口真实 session，不要求用户切回旧窗口或执行 `!` 命令。重复调用当前任务或请求续做走 status/resume，不当作新任务清理。
  - **无参数**：只接入已准备且未执行的 team-task.md，完整读其正文、repo 硬规则和必要生产 skill；不自行重写或扩展任务，不额外追读 A 的基线。
  - **带文档参数**：自动收尾成功后，team-task.md 缺失/空白才完整读指定文档并自动起草首轮自足任务（「本次任务 + done_when」、范围/保留项/验证方法，不带 source 标记、不写轮数或 criteria），回显范围后继续。文档缺失/空白则报错。旧归档文件由 helper 核对字节后清空，不交给用户手工删。若留下的是不能证明属于旧归档的非空任务，保留它并集中说明冲突；本会话刚写入而 init 尚未成功的同一草稿直接重试，不重复清理。
  - 随后 `init`（不传 baseline/max-round）：备份原任务与旧进度，给现成任务加 source 标记、保留正文，清空已归档旧进度并进入 B_READY。state 此时无 baseline、max_round=null，只限首轮；A review 才绑定全局基线、criteria 与轮数。自动收尾不会执行业务、恢复旧任务或解除其人工门。
- `review <文档> [max-round=N]`：A 先 status，随后**完整读取用户在此命令指定的基线及其依赖**，提取全局 criteria（原文定位、验收方法、保留项、例外边界、模板标注要求），写 criteria-input.json。执行 `join --run ... --baseline <绝对路径> --max-round N --criteria ...`，才冻结基线 hash、轮数和清单并绑定 A。加入不改 B 的 source、progress、合同或当前阶段；B 正在做则静默等待，B 已完成则立即验收交接。已绑定 A 重入须核对参数与原绑定一致，不能换基线、加轮数或重新冻结清单。没有 workflow 则提示先在 B 启动 run；若已 PAUSED/终态，只报告结果，不重开。
- 每次完成通知/角色工作返回后，先 `status`，核对本窗口 ID、run、round、phase；**通知是提醒，盘上状态才决定轮到谁**。旧通知、重复通知不构成执行许可。

| 状态 | A 的动作 | B 的动作 |
|---|---|---|
| A_PLAN（只出现在第 2 轮起） | 全量重读冻结文档；只按基线缺口写下一轮草稿并 `publish` | 静默等待 |
| PUBLISHING | 第 2 轮起由 A 重放 `publish`；首轮只等待 | 首轮中断恢复由 B 重放 `publish`；后续轮只等待 |
| B_READY | 静默等待 | 调用 `Skill(team-workflow-run, "run=<run> round=<round>")`，随后重新读状态 |
| B_RUNNING | 静默等待 | 正在执行则继续；冷恢复仅报一次“需原窗口 /team-workflow resume”，不自动再次执行 |
| A_REVIEW | 独立验收并 `review`；未达标且未达上限则自动进入下一轮 A_PLAN | 静默等待 |
| DONE / LIMIT / CANCELLED / PAUSED | 报一次结果或阻断，结束调度 | 结束调度；不重复 A 的验收汇报 |

B 完成时 A 尚未加入：照常 finish 写 A_REVIEW 和不可覆盖交接，再静默等待。A 晚到读盘即可验收；不因无人监听就丢交接、自动重跑或增加轮数。B 不代建 A 的验收清单，不代签验收。

### 派工前的三个检查

适用于讨论窗口准备首轮、B 按带参 run 起草首轮，以及 A 发布后续自足任务；补进现有任务说明，不另建表单：

1. 本轮推进用户最终结果的哪段链路、补哪项尚缺的证据？材料和登录具备时优先贯通最小真实业务链，缺外部条件时先做独立可做部分，不为此提前扩展全部类别。
2. 哪些已有材料、候选入口、能力及阻断记录仍可复用？历史入口不替代当次身份、材料和业务事实核实。
3. 必要的源码、schema、配置、测试、构建清单及使用说明是否一并列入允许写范围，并明确责任文件、共享文件协调及禁止范围？已知配套不留到下一轮补授权；新发现的越界需求仍走现有合同增补，不能用“必要连带修改”概括授权认证、安全守卫、保存行为或全局 skill。

### A 的独立验收

1. **每轮重读原始冻结文档**，核对 hash；完整逐条覆盖初始 criteria。不能只验 B 本轮 done_when，也不能把 B 的完成报告当验收结论。
2. 先按判据直接检查实物/原始数据、在隔离副本独立复跑有意义的验证，把本轮证据写到 round 目录的 `acceptance/`。相关依赖和产物 hash 未变、原验证范围与当前环境适用且无未解差异时，可引用仍有效的既有独立原始证据，同时记录原验证时间、范围和本轮适用性核对；不写成“本轮重跑”。登录身份、当前页面及终局 DOM 须当次核实，合同规定的 fresh 终审和必要交叉复核照常执行。A 不修业务产物、不编辑 B 的合同或 progress；需修的全部交下一轮 B。下一轮 team-task 必须自足地写清待修要求、范围和 done_when，不能只写“去看用户需求.md/criteria.json”；全局基线的逐条覆盖与核验由 A 保持。
3. 再读交接证据，比较差异。每条签 `PASS_DYNAMIC / STATIC_ONLY / FAIL / BLOCKED`；仅原始基线**明确允许的豁免**签 `EXEMPT` 并引用原条款。STATIC_ONLY 不能冒充完成；使用条件沿用 team-task 的四态纪律。基线文字性判据可直接检查实际交付文本并记录实测，不要求把所有判据变成代码测试。
4. 写 review-input.json 后执行 helper `review`。helper 要求全部 criteria 均有证据；只有全为 PASS_DYNAMIC/EXEMPT 且 B 合法完成，才能 DONE。否则仅针对原基线未满足项派下一轮；达到 A 绑定的上限时未达标为 LIMIT，列出缺口后结束。B 已遇人工门/熔断则判 pause，A 不凭复审把人工门改成自动返工。

交接和审查摘要简短写清“本轮新增/重验、有效旧证据及其时间与范围、未解项”。未解项区分具体缺陷、尚未开展的后续阶段与外部阻断。A 侧重用户目标、跨轮遗漏和业务证据；临时 reviewer 围绕指定技术风险、原始数据重算或冻结产物复核，派工写清具体问题，实现者不作自己产物的唯一终审。`rework` 也可能是阶段合格后继续派工，不能直接统计为缺陷次数。格式和定稿顺序见 [交接约定 §2—§3](references/relay.md#2-b-的交接输入)。

## 静默待机与唤醒（不可省）

当表格要求等待时，用 **Bash 工具 `run_in_background:true`** 执行一次：

```text
python "<skill-dir>/scripts/workflow.py" wait --repo "<repo>" --session "<本窗口 ID>" --run <run> --observed-seq <当前 seq> --timeout 3600
```

- 记录 Bash 返回的 task_id；每窗口只保留一个等待任务。wait 阻塞在 Windows 事件上，无心跳输出、不读业务文件、不占着 repo mutex 睡觉。交接提交后发事件，wait 退出，由 Claude 原生 task-notification 唤醒本窗口。
- 后台任务已启动后结束当前 turn，让窗口空闲；**不输出“正在等待/继续待机/一小时后检查”等文字**。工作里程碑可简报一次，空闲期间不叙述状态。不得用 TaskOutput 反复轮询、`/loop`、cron、连续 sleep 或自发用户消息代替本机制。
- 收到此 task_id 完成通知时，读对应输出并重新 `status`。WAKE → 按状态调度；TIMEOUT 且仍非本窗口回合 → **无用户可见文字地重挂一次 3600 秒 wait**。超时不派任务、不涨轮数；一次性错误则报一次并停止，不能错误自旋。
- 重复通知/其它任务通知先按 task_id 去重；已挂 wait 时不再挂第二个。helper 返回 `WAITER_ALREADY_RUNNING` 时保留原等待任务，不杀原进程、不重试循环。若状态已交接而事件先于 listener，wait 会直接读到新状态，立即退出。
- 收到 killed/异常退出通知先 `status`，记录 task_id、通知所述原因和阶段；宿主明确要求等请求再重启时，不立即重挂。收到明确恢复请求或重新进入原入口时，按 [恢复约定 §4](references/relay.md#4-原窗口恢复和实际边界) 核对原 waiter：`status` 不证明它存活，状态不明不创建第二个。宿主退出后不声称仍持续待机；配额等待与业务缺陷分别记录。

## 状态、停止与中断

- `/team-workflow status`：只读当前状态，简报角色、轮数、谁在工作及阻断，不启动循环。A 未加入时标“首轮 / 总轮数待 A 设定”，不要把 null 显示为无限执行。
- `/team-workflow stop`：原 A/B 调 helper `stop`。若 B 正在执行，只设停止请求；B 在下一个检查点停止新增工作，完成在途写入和团队关闭后 `pause --reason ...` 确认静止。**不杀 Office/其他窗口进程**。停止不等于验收通过。
- `/team-workflow resume`：只恢复绑定的原 session。按表格继续本窗口回合；首轮 PUBLISHING 由 B 重放 publish。等待方重挂 wait（原 waiter 尚在则沿用）。B 若 B_RUNNING，用户此次显式 resume 先走 helper `resume --reason <用户原话>`，再传返回的单次 resume_token 调内部 runner，复用同一 team_run/source/合同/失败计数，不再跑一个新任务。
- PAUSED 是人工门，resume 不静默清除；DONE/LIMIT/CANCELLED 不自动重开。明确的新任务通过 `prepare-new` 收尾旧 run 后正常 init，细则见 §5；同一基线的 PAUSED/LIMIT/熔断不能借此换 run 解除。自动归档不等于旧任务完成，不转移 A/B 绑定，不恢复旧业务执行，不迁移旧版状态。原窗口的 `archive` 保留兼容。
- helper 检出基线/源块/产物漂移、归档冲突等错误时，停止依赖动作并报一次；轮到本窗口且执行体已静止时可 `pause --reason <原始错误>` 留状态。不要手工改 `.team-workflow-state.json`、删状态、重置计数来续跑。

当前版本：v0.4（2026-10-28），新增明确新任务前的自动归档/中断退役，保留原绑定 resume、A/B 接力与人工门。终态可由当前调用者收尾，无须冒用旧 session；中断退役须通过真实进程及 waiter 检查。隔离机械测试、实际旧任务清理与真实双 session 接力分别记验证层次，不互相代替。
