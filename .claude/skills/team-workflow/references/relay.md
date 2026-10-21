# 接口与数据约定

按需阅读：首轮准备/A 加入用 §1，B 交接用 §2，A 验收用 §3；恢复/排错用 §4。脚本只核验机械状态与证据绑定，**不判断业务要求是否真的达标**。

所有命令前缀：`python "<team-workflow skill-dir>/scripts/workflow.py" <action> --repo "<repo绝对路径>" --session "<CLAUDE_SESSION_ID>"`。除 init/status 外均附 `--run <status返回的run>`，并使用当前返回的状态；禁止凭旧通知自行编造 run/round。

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
| pause | `--reason "<错误或停止原因>"` | 当前执行方已静止后留阻断；A 不可借此抢走正在执行的 B |

退出码 0 表示命令成功，**不代表任务达标**；退出码 1 + TEAM_WORKFLOW_ERROR 表示拒绝。state 的 phase 决定下一步。所有报告/证据/草稿路径必须在 repo 内。B 的执行范围由当前 team-task 与生效合同限定；A 按独立基线验收并把缺口写成自足的下一轮任务。

根文件 `.team-workflow-state.json` 只由 helper 写。B init 仅接入现成任务，备份、规范 source 标记并归档清空旧进度；后续 A publish 才替换 source。A join/等待不动任务与进度。状态版本为 3：A 未绑定时没有 baseline 字段，max_round=null 且 round 必须为 1；A join 后才设置 baseline/hash/max_round/criteria。null 不是无限轮次；没有 A 就无法产生第二轮。旧版状态拒绝混用，不设兼容层；不用 temp.md、double-session 或全局 hook。

历史：`team-progress/team-workflow/<run>/before-start/`、`criteria.json`、`round-01/`…。各 round 的 `source.md`、`execution/{team-task.md,team-progress.md}`、`handoff.json`、`review.json` 由 helper 不可覆盖归档；agent 输入文件另命名 `task-draft.md / handoff-input.json / review-input.json`，不得直接写这些归档目标。已归档文件若需要修正，停下查原因，不改旧证据。

## 1. 外部首轮任务与 A 的验收基准

首轮任务有两条准备路径：讨论窗口（可使用 Codex 或其它工具）先写用户认可的冻结文档和根 team-task.md；或用户只备冻结文档，用 `/team-workflow run <文档>` 让 B 在 init 前自行起草并写入根 team-task.md（`.team-workflow-state.json` 已存在则不起草、转 status/resume；team-task.md 缺失/空白（空白=strip 后无可见字符）才起草并自动创建，非空则一律停下，请用户清理后重跑或去掉参数沿用）。任务应含「本次任务 + done_when」，且不混入旧合同。B 代起草不冻结基线 hash、不生成 criteria，A 的 join 仍独立冻结。首轮 B init 对两条路径一视同仁：接受无标记正文或单一有效 open source；只补标记/规范换行，源正文不改，原始字节存 before-start。旧 progress 为空可直接用新任务；ACTIVE/WAIT_HUMAN 等未收口进度、仍带旧合同或 source 已执行过则拒绝，不能把运行中裸 `/team-task` 硬接管。

稍后 A 读取用户在 `/team-workflow review <文档> [max-round=N]` 中指定的完整文档，写 criteria-input.json；首次 join 才一起冻结基线 hash、轮数和 criteria.json。不能从 B 的任务、完成报告或自述反推整份基线。这只是提取独立验收判据，不重做首轮执行计划，不要求 B 等它才开工：

```json
{"items":[{"id":"D1","requirement":"原始要求的字面内容","source":"需求基线-FROZEN.md §2.4 第3段","verify":"对实际产物怎样检查，什么结果才通过"}]}
```

ID 全局唯一，清单覆盖指定基线完整要求。保留项、例外、明确不做的范围同样不得在拆解中消失。后续每轮重新读基线，但不通过缩短 criteria 来获得通过；发现首轮漏列或原始基线被改，应暂停并请用户明确新的范围，不能静默改 hash。

后续草稿保留「本次任务 + done_when」，带 criteria ID 便于 A 对照，但必须写出待修条款、范围、保留项和验证方法，让 B 仅凭任务即可执行。不能把 A 的基线文件或 criteria 清单作为 B 的必读入口。helper 只附 workflow_run/workflow_round/失败累计，不再向任务注入基线路径/hash/criteria 路径；B P2/P3 正常形成合同。

基线检查只用于 A 的加入、验收、下一轮发布等动作。B 的 init/enter/permit/finish/resume 及首轮发布恢复均不读取基线；A 的文件尚未存在或暂时不可访问，也不妨碍 B 完成合法的当前任务。A 基线变动会阻止其验收/派工，不会把基线职责转给 B。

## 2. B 的交接输入

完成本轮原有 team-task 的验收、收尾及所有 teammate shutdown 后，写 handoff-input.json：

```json
{
  "outcome":"complete",
  "summary":"本轮实际完成内容及尚存事项",
  "artifacts":{"output/result.txt":"真实文件的完整64位sha256"},
  "evidence":["team-progress/team-workflow/<run>/round-01/execution-check.txt"],
  "failure_counts":{}
}
```

`artifacts` 必须覆盖本轮实际交付件及会影响验收的脚本/数据，不用“报告说已通过”代替产物。普通成功至少一件；hash 用 Python/hashlib 等实算。证据路径须为已存在、非空的原始验证记录。helper 检查源块、run/source ID、合同增补链、effective_contract_id 和当前漏斗行 `COMPLETE + P6✓` 后，绑定交接 hash。

遇真实人工门或熔断，用 `outcome=blocked|halted`、progress 写 `WAIT_HUMAN|HALTED|BLOCKED + P6·`，带原始阻断证据；不能先伪造 COMPLETE 再交 A。A 收到这种交接只能 pause，不能把它自动换包装成下一轮以绕门。

`failure_counts` 是**累计全量字典**：稳定 key=`stage|error_family|error_code|unmet_done_when`，值为已发生次数。新 round/session 不能清零或漏掉旧 key。A 判出同一验收失败时也累计；不把同一份 B 已登记失败证据再次计数。首败陪审/第二次未用次选/第三次熔断继续沿用 team-task 规则；换名字不构成新问题。

## 3. A 的验收输入

每条均在本轮直接核验，再写 review-input.json：

```json
{
  "decision":"rework",
  "summary":"D1 尚未满足，下一轮只补这个缺口",
  "failure_counts":{"review|content|missing_field|D1":1},
  "checks":[{"id":"D1","status":"FAIL","evidence":["team-progress/team-workflow/<run>/round-01/acceptance/D1.txt"]}]
}
```

`decision=pass|rework|pause`；checks **必须恰好覆盖所有 criteria ID**。EXEMPT 除 evidence 外还必须有 `clause` 原始豁免条款。PASS_DYNAMIC 证据必须是 A 本轮实际核验所得，不是 B 的自述或旧 reviewer 的结论。脚本能检查“有证据且未变化”，语义独立性由 A 依判据落实。

rework 只有在未达 max_round 且未触发人工门/同 key 三次失败时才递增；全通过则提前 DONE。达到轮次上限是 LIMIT，**不是 COMPLETE/PASS**。暂停列出需要用户处理的具体条件；时间到、低置信或普通默认选择本身不构成人工门。

## 4. 原窗口恢复和实际边界

每次完成通知前先确认对应的后台 task_id；随后 status。B_READY 才可首次 enter；B_RUNNING 只能通过用户显式 resume 的单次 token 恢复原 team_run。permit 不创建任务、不复位进度。PUBLISHING 表示源已冻结但根文件可能只更新了一份，首轮 B/后续 A 重放 publish 会核对旧/新 hash 后完成剩余写入；禁止另写计划压过去。A 未上线时 finish 仍持久化 A_REVIEW；B 续等，A 加入后直接验收。无需为晚加入新增消息队列或另一套状态机。

Windows 事件采用 double-session 的 AutoResetEvent + repo mutex 思路，代码自足，不要求启动 double-workflow。事件只是提示；真正交接条件都在 state。关掉窗口、电脑休眠/退出登录、工具被禁用会中断唤醒；本版不提供独立于 Claude 窗口的后台服务。

依据：Claude 官方 [Bash 工具参考](https://code.claude.com/docs/en/tools-reference) 与 [后台任务](https://code.claude.com/docs/en/interactive-mode)。交互 session 的后台任务可在主 turn 结束后继续运行并通知原会话；`-p` 的进程结束会终止会话内后台任务。技能变量见 [skills 文档](https://code.claude.com/docs/en/skills)。本机检查版本为 2.1.266；不要把文档支持误写成已通过真实 Claude-GLM 两窗口验收。
