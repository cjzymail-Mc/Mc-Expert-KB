# 接口与数据约定

按需阅读：首轮准备/A 加入用 §1，B 交接用 §2，A 验收用 §3；恢复/排错用 §4。脚本只核验机械状态与证据绑定，**不判断业务要求是否真的达标**。

所有命令前缀：`python "<team-workflow skill-dir>/scripts/workflow.py" <action> --repo "<repo绝对路径>" --session "<CLAUDE_SESSION_ID>"`。除 init/status/prepare-new 外均附 `--run <status返回的run>`，并使用当前返回的状态；禁止凭旧通知自行编造 run/round。

| action | 附加参数 | 用途 |
|---|---|---|
| init | 无 | B 只接入已准备的 team-task，直接 B_READY；拒绝 baseline/max-round 参数 |
| join | `--baseline "<冻结文档绝对路径>" --max-round 3 --criteria "<判据相对路径>"` | A 首次加入才绑定基线、轮数和清单；max-round 缺省为 3。重复加入可省略参数，显式给出的参数须与绑定一致 |
| publish | `--task "<草稿相对路径>"` | 第 2 轮起由 A 发布；PUBLISHING 恢复无需草稿，首轮由 B 重放、后续由 A |
| enter | `--round N [--resume-token <token>]` | 内部 runner 单次接棒；重复调用失败 |
| permit | `--round N` | 执行前/恢复时只读核验当前 B 执行许可 |
| finish | `--report "<handoff-input相对路径>"` | B P6 后交接；先归档、后状态、再事件 |
| review | `--report "<review-input相对路径>"` | A 全局验收；脚本决定停止或递增轮数 |
| wait | `--observed-seq N --timeout 3600` | 原窗口 Bash 后台任务；收到事件或超时仅输出一次 JSON |
| resume | `--reason "<用户明确续做指令>"` | 原 B 中断恢复，生成单次 resume_token |
| stop / status / archive | 无 | 停止请求 / 只读 / 用户明确新任务前封存终态 |
| prepare-new | `--request "<新任务文档或简短标识>" --reason "<本次新任务指令>" [--run <当前run>]` | 当前真实 session 在新任务前自动归档旧任务；无 state 时识别已归档残留。外部维护用 `--actor <实际调用者>` 代替 session，见 §5 |
| pause | `--reason "<错误或停止原因>"` | 当前执行方已静止后留阻断；A 不可借此抢走正在执行的 B |

退出码 0 表示命令成功，**不代表任务达标**；退出码 1 + TEAM_WORKFLOW_ERROR 表示拒绝。state 的 phase 决定下一步。所有报告/证据/草稿路径必须在 repo 内。B 的执行范围由当前 team-task 与生效合同限定；A 按独立基线验收并把缺口写成自足的下一轮任务。

根文件 `.team-workflow-state.json` 只由 helper 写。B init 仅接入现成任务，备份、规范 source 标记并归档清空旧进度；后续 A publish 才替换 source。A join/等待不动任务与进度。状态版本为 3：A 未绑定时没有 baseline 字段，max_round=null 且 round 必须为 1；A join 后才设置 baseline/hash/max_round/criteria。null 不是无限轮次；没有 A 就无法产生第二轮。旧版状态拒绝混用，不设兼容层；不用 temp.md、double-session 或全局 hook。

历史：`team-progress/team-workflow/<run>/before-start/`、`criteria.json`、`round-01/`…。各 round 的 `source.md`、`execution/{team-task.md,team-progress.md}`、`handoff.json`、`review.json` 由 helper 不可覆盖归档；agent 输入文件另命名 `task-draft.md / handoff-input.json / review-input.json`，不得直接写这些归档目标。已归档文件若需要修正，停下查原因，不改旧证据。

## 1. 外部首轮任务与 A 的验收基准

首轮任务有两条准备路径：讨论窗口先备冻结文档和未执行的 team-task.md；或用户给文档，用 `/team-workflow run <文档>` 让 B 起草。明确新任务先走 §5 自动收尾；重复进入同一任务不触发清理。带参 run 在任务缺失/空白时起草，已归档旧任务由 helper 自动核对并清空；不覆盖未经识别的非空任务。B 起草不冻结 A 的基线 hash、不生成 criteria；init 接受无标记正文或单一有效 open source，只加标记/规范换行并保留 before-start 原字节。仍在运行的裸 team-task、旧合同或已执行 source 不得硬接管。

稍后 A 读取用户在 `/team-workflow review <文档> [max-round=N]` 中指定的完整文档，写 criteria-input.json；首次 join 才一起冻结基线 hash、轮数和 criteria.json。不能从 B 的任务、完成报告或自述反推整份基线。这只是提取独立验收判据，不重做首轮执行计划，不要求 B 等它才开工：

```json
{"items":[{"id":"D1","requirement":"原始要求的字面内容","source":"需求基线-FROZEN.md §2.4 第3段","verify":"对实际产物怎样检查，什么结果才通过"}]}
```

ID 全局唯一，清单覆盖指定基线完整要求。保留项、例外、明确不做的范围同样不得在拆解中消失。后续每轮重新读基线，但不通过缩短 criteria 来获得通过；发现首轮漏列或原始基线被改，应暂停并请用户明确新的范围，不能静默改 hash。

后续草稿保留「本次任务 + done_when」，带 criteria ID 便于 A 对照，但必须写出待修条款、范围、保留项和验证方法，让 B 仅凭任务即可执行。不能把 A 的基线文件或 criteria 清单作为 B 的必读入口。helper 只附 workflow_run/workflow_round/失败累计，不再向任务注入基线路径/hash/criteria 路径；B P2/P3 正常形成合同。

基线检查只用于 A 的加入、验收、下一轮发布等动作。B 的 init/enter/permit/finish/resume 及首轮发布恢复均不读取基线；A 的文件尚未存在或暂时不可访问，也不妨碍 B 完成合法的当前任务。A 基线变动会阻止其验收/派工，不会把基线职责转给 B。

## 2. B 的交接输入

沿用原进度骨架，不在收尾重建一份删减版。正常完成的头部格式如下（仅结构示意，尖括号替换为本轮实际值；不是初始化模板）：

```text
> run_id: <state.team_run，非 workflow run>
> source_block_id: <state.source_id>
> contract_id: <本轮基础合同的 ctr-ID>
> effective_contract_id: <当前合同链末端 ID；无增补时等于 contract_id>
> run_status: COMPLETE
> 漏斗: P0✓ P0.5✓ P1✓ P2✓ P3✓ P4✓ P5✓ P6✓
```

保留全部既有进度、风险登记和复盘段落；五个英文头字段各只出现一次，保持小写键、ASCII 冒号，唯一 `> 漏斗:` 行反映实际阶段。执行与收尾期间仍为 `ACTIVE + P6·`，不能为了交接提前勾选。

定稿顺序：**完成真实工作、规定终审、收尾及 teammate shutdown → 同次落盘 COMPLETE 与唯一 P6✓ 并核对完整头字段/合同链 → 写 summary、非空 evidence 与全量 failure_counts → 最后实算 artifacts 哈希 → finish**。完成前先确认全部执行体已静止；终审后若改动受审产物，须按原终审规则重审。阻断/熔断不套成功头部，按下文保留真实状态。

随后写 handoff-input.json。下面 JSON 仅示意结构：路径、摘要、哈希及累计失败字典都要替换为本轮实值，不可原样提交。

```json
{
  "outcome":"complete",
  "summary":"本轮新增/重验：实际内容；有效旧证据：原时间、范围及本轮适用性；未解项：缺陷/后续阶段/外部阻断（无则明确无）",
  "artifacts":{"output/result.txt":"真实文件的完整64位sha256"},
  "evidence":["team-progress/team-workflow/<run>/round-01/execution-check.txt"],
  "failure_counts":{}
}
```

`artifacts` 必须覆盖本轮实际交付件及会影响验收的脚本/数据，不用“报告说已通过”代替产物。普通成功至少一件；hash 用 Python/hashlib 等实算。`evidence` 必须为非空列表，每条指向 repo 内已存在、非空的原始验证记录，使用本轮实际路径；沿用证据时同时给本轮适用性核对记录。`failure_counts:{}` 仅适用于确无任何累计失败的情况，否则完整承接原 key 和次数。helper 检查源块、run/source ID、合同增补链、effective_contract_id 和当前漏斗行 `COMPLETE + P6✓` 后，绑定交接 hash。哈希生成后不再改被引用文件；如有必要补正，须重新实算受影响引用。

`EVIDENCE_REQUIRED` → 补真实非空证据列表；`TEAM_PROGRESS_INVALID` → 按原合同补正头字段/有效链；`TEAM_P6_NOT_COMPLETE` → 核实真实工作和收尾是否完成，再修正状态及唯一漏斗行，未完成则继续工作或如实交接阻断。先 `status` 确认仍是本轮 B_RUNNING，且没有已落盘的本轮 execution 归档或 handoff，才能补正输入、更新哈希并重试 finish；沿用失败预算，不靠盲重试过门。已出现归档/交接、状态不符或身份/源块/合同漂移时保留现场，按原错误/暂停规则处理，不覆盖旧证据、不手改 state。

遇真实人工门或熔断，用 `outcome=blocked|halted`、progress 写 `WAIT_HUMAN|HALTED|BLOCKED + P6·`，带原始阻断证据；不能先伪造 COMPLETE 再交 A。A 收到这种交接只能 pause，不能把它自动换包装成下一轮以绕门。

`failure_counts` 是**累计全量字典**：稳定 key=`stage|error_family|error_code|unmet_done_when`，值为已发生次数。新 round/session 不能清零或漏掉旧 key。A 判出同一验收失败时也累计；不把同一份 B 已登记失败证据再次计数。首败陪审/第二次未用次选/第三次熔断继续沿用 team-task 规则；换名字不构成新问题。

## 3. A 的验收输入

每轮重读冻结基线、全量覆盖判据，再写 review-input.json。本轮新增/重验、有效旧证据的原时间与范围、未解项可直接写在现有 summary 和 acceptance 记录中，不新增报告字段：

```json
{
  "decision":"rework",
  "summary":"本轮新增/重验：D1 实物核查；有效旧证据：无；未解项：D1 的具体缺口及下一轮范围",
  "failure_counts":{"review|content|missing_field|D1":1},
  "checks":[{"id":"D1","status":"FAIL","evidence":["team-progress/team-workflow/<run>/round-01/acceptance/D1.txt"]}]
}
```

`decision=pass|rework|pause`；checks **必须恰好覆盖所有 criteria ID**。EXEMPT 除 evidence 外还必须有 `clause` 原始豁免条款。PASS_DYNAMIC 必须有 A 本轮独立核验记录，不能只用 B 自述或旧 reviewer 结论；相关依赖/产物 hash 未变、原范围及当前环境适用且无未解差异时，可引用既有独立原始证据并附本轮适用性核对记录，不把引用写成本轮重跑。身份、当前页面、终局 DOM 当次验证及合同规定的 fresh 终审不可抵扣。脚本能检查“有证据且未变化”，语义独立性由 A 依判据落实。

rework 只有在未达 max_round 且未触发人工门/同 key 三次失败时才递增；全通过则提前 DONE。达到轮次上限是 LIMIT，**不是 COMPLETE/PASS**。暂停列出需要用户处理的具体条件；时间到、低置信或普通默认选择本身不构成人工门。

## 4. 原窗口恢复和实际边界

每次完成通知前先确认对应的后台 task_id；随后 status。B_READY 才可首次 enter；B_RUNNING 只能通过用户显式 resume 的单次 token 恢复原 team_run。permit 不创建任务、不复位进度。PUBLISHING 表示源已冻结但根文件可能只更新了一份，首轮 B/后续 A 重放 publish 会核对旧/新 hash 后完成剩余写入；禁止另写计划压过去。A 未上线时 finish 仍持久化 A_REVIEW；B 续等，A 加入后直接验收。无需为晚加入新增消息队列或另一套状态机。

Windows 事件采用 double-session 的 AutoResetEvent + repo mutex 思路，代码自足，不要求启动 double-workflow。事件只是提示；真正交接条件都在 state。关掉窗口、电脑休眠/退出登录、工具被禁用会中断唤醒；本版不提供独立于 Claude 窗口的后台服务。

异常等待沿用原入口处理，不新增监控或轮询：

- `TIMEOUT`、重复通知和 `WAITER_ALREADY_RUNNING` 按 SKILL 正文处理。
- killed/异常退出通知到达后，先 status，记录原 task_id、通知所述错误类型和 run/round/phase；只把低内存等原因归于通知陈述，不推断未经遥测的具体宿主故障。若通知要求等请求再启动，遵守该停止指令，不立即无限重挂。
- 收到明确重挂/resume 请求，或上下文恢复进入原入口时，先 status 核对绑定 session、角色、run、round 和 phase，再结合原 task_id 的完成通知或后台任务状态确认 waiter。status 本身不证明 waiter 存活；仍在则沿用，确已消失且宿主允许重挂、当前仍需等待时才恢复唯一 3600 秒后台 wait；状态不明不创建第二个，已轮到本窗口则按调度表接棒。
- 宿主已退出或无可处理通知时，由下次入口恢复，不声称后台持续运行；配额等待与业务缺陷分开记录。不能改为定时轮询、自动杀进程、常驻监控或无限重试。明确新任务的非终态孤儿可按 §5 自动退役；需要继续旧业务、状态损坏或超出机械判断的现场仍交外部维护，不内建通用接管/执行恢复机制。

依据：Claude 官方 [Bash 工具参考](https://code.claude.com/docs/en/tools-reference) 与 [后台任务](https://code.claude.com/docs/en/interactive-mode)。交互 session 的后台任务可在主 turn 结束后继续运行并通知原会话；`-p` 的进程结束会终止会话内后台任务。技能变量见 [skills 文档](https://code.claude.com/docs/en/skills)。本机检查版本为 2.1.266；不要把文档支持误写成已通过真实 Claude-GLM 两窗口验收。

## 5. 新任务启动前自动收尾

用户明确发起新任务（含本次已授权的启动请求）时，由 agent 自动执行一次预检收尾；不为旧 run 换窗、复制旧 session ID 或要求用户跑 `!` 命令。仅查状态、重复进入当前任务、续做旧任务不触发归档。新任务不能是通过重命名绕过同一业务的人工门、失败预算或保存 registry。

```text
python "<skill-dir>/scripts/workflow.py" prepare-new --repo "<repo>" --session "<本窗口真实ID>" --run <当前run> --request "<新任务文档路径或简短标识>" --reason "<用户本次明确新任务意图>"
```

state 存在时先 status，并传它的实际 run；不存在时省略 `--run`，helper 可识别官方 archive 后遗留的相同字节。由 Codex 等外部 agent 维护时，省略 `--session`、使用 `--actor "Codex"` 如实记录调用者；这只允许新任务前收尾，不获取 A/B 执行权。request/reason 不放账号、凭证或业务敏感值。

| 现场 | 自动动作 |
|---|---|
| DONE / LIMIT / CANCELLED | 核对根任务/进度与记录的 hash，保留原状态与最终原文件后归档；终态不要求原绑定窗口存在 |
| 非终态且原 A/B、相关子进程与 waiter 均已退出 | Windows 进程起点及存活检查＋会话目录/相关进程一次性盘点，核对根任务来源与进度身份；保留原始状态/任务/进度，记 CANCELLED（未完成退役），保留失败计数、合同及全部轮次证据后归档 |
| 原绑定窗口、相关执行者或 waiter 仍存活，或检查失败/未知 | 停止依赖动作并报告具体占用；不靠 mtime/长时间无消息判死，不杀进程、不冒用 ID。原绑定会话记录消失时使用 init/join/enter 已记录的最小 PID/进程起点；旧 run 两处均无进程依据则报具体缺口，不把空列表当退出证明。当前窗口若就是原执行方，可先按原 stop/pause 流程关闭在途工作，成为终态后再收尾 |
| state 已由旧 archive 移除，但根文件与该 run 的 final 完全相同 | 自动识别并清空已归档残留，然后起草新任务 |
| 无旧 state，也无可证明的旧文件归属 | 保留现有草稿；合法未执行草稿按原入口接入，未知非空任务报告冲突 |
| 同一基线的 PAUSED / LIMIT / 熔断；损坏/旧版状态或归档冲突 | 保留现场与具体原因；归档不能自行解除旧任务门槛 |

每个旧 run 的 `prepare-new/` 保存原 state 原字节、任务/进度与哈希、调用者/新任务依据及 receipt；`final/`、`state-final.json` 为最终归档。旧工件不改，未完成不签 DONE。先可回读归档，再核对并清空**仅属于旧 run**的两个根文件，最后移除活动 state；命令中断重试复用 receipt，发现新草稿/新 run 或备份漂移即拒绝。没有另建守护进程、轮询服务或自动续填机制。

收到 `TEAM_WORKFLOW_NEW_TASK_READY` 后，agent 立即继续准备新首轮并 init，无需用户再确认已授权的收尾。未完成退役时，先读取归档进度、合同和失败历史，把仍影响新任务的成果/缺口/失败 key 带进首轮任务；不虚报旧任务完成，不清预算以重试同一问题。新任务依旧由独立 B 执行、A 加入验收。

此动作只处理 workflow 的 state、team-task、team-progress 和自身归档，不操作 OA 页面、业务 profile 锁/registry/凭证，不证明业务现场已就绪；后续业务执行仍按 repo 的当次身份、锁、registry 与页面规则核实。
