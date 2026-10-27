# Claude `/today-loop` 台账 schema v1

## 文件

- `state.json`：当前真相，确定性脚本原子替换。
- `events.jsonl`：append-only 迁移审计。
- `contract.json`、`plans.json`：启动前冻结，运行中只读。

`state.json` 额外持久化完整授权面 `allowed_paths/read_only_paths/forbidden_actions/human_gates/terminal_evidence`，以及 `frozen_inputs` 中合同/plan 路径与 SHA-256。`last_event_seq` 必须与 events 最后序号一致。

## run 字段

| 字段 | 类型 | 约束 |
|---|---|---|
| `schema_version` | integer | 固定 1 |
| `run_id` | string | 非空 |
| `status` | string | `running/complete/halted/wait_human` |
| `phase` | string | `select/preflight/build/self_check/jury/checkpoint/terminal` |
| `current_plan` | string/null | 至多一个；终态可为空 |
| `last_verdict` | string/null | `PASS/REWORK/WAIT_HUMAN/PENDING` 或空 |
| `consecutive_failures` | integer | 0..3；到 3 时必须 halted |
| `plans` | array | id 唯一；状态见下 |

plan 字段：`id/title/depends_on/**done_when**/**reference(可选)**/status/attempts/evidence/review_evidence/last_error`。plan 状态只允许 `pending/running/rework/passed/failed/wait_human`。

**冻结输入 plan 字段（静态定义，来自 plans.json，运行中只读）**：`id/title/depends_on/done_when/reference`。
- `done_when`：做完长什么样——**结果状态，非动作清单**（如"X 文件存在且首字节为 50 4B"，不是"改 X 文件"）。它是 plan 级客观尺度：JURY 判 PASS 时必须核对它是否满足（见 SKILL.md §3.5）。脚本 `init` 对 `done_when` 做**非空 fail-fast 校验**（纯空白/缺失直接 reject），不判语义质量（语义仍归 reviewer）。
- `reference`：参照物路径或描述（标准样板/目标格式）。长链/批量任务价值高，低风险单点可省略——故**可选、缺省空串**，脚本不强制。

**运行时 plan 字段（由状态机在 state.json 维护，不进冻结输入）**：`status/attempts/evidence/review_evidence/last_error`。

## 合法迁移

| 动作 | 前置 | 结果 |
|---|---|---|
| `init` | 无 state；合同和 plans 校验通过 | run=`running`, phase=`select` |
| `select` | run running | 返回 active plan、下一个 eligible plan 或 all-pass，不写状态 |
| `start` | plan pending/rework；依赖全 passed；无其他 running | plan=`running`, attempts+1, phase=`preflight` |
| `preflight-check` | phase preflight；target/action 非空 | 合法则写 `preflight_passed`；越界/禁止动作/人工门则 `wait_human` |
| `advance` | plan running；phase 与 `From` 一致 | `preflight→build→self_check→jury`；preflight 必须已有机械检查证据 |
| `pending-review` | phase jury | verdict=`PENDING`，不计失败 |
| `review-pass` | phase jury；独立 reviewer PASS 文件有效 | verdict=`PASS`，phase=`checkpoint` |
| `pass` | phase checkpoint；review PASS；证据文件存在 | plan=`passed`，failure=0，回 select |
| `fail` | plan running；原因非空 | 第一次/第二次 plan=`rework`；第三次 plan=`failed`, run=`halted` |
| `wait-human` | run running；原因非空 | plan/run=`wait_human`，终态 |
| `redline` | run running；原因非空 | run=`halted`，终态，不计普通失败 |
| `complete` | 所有 plan passed；全部终态证据文件位于 run dir 且存在 | run=`complete`，终态 |

## 不变量与恢复

1. 至多一个 `running` plan；`current_plan` 必须与其一致。
2. `passed` plan 必有 evidence，且不会再次 start。
3. 依赖图必须无环；未通过依赖的 plan 不可 start。
4. 三终态不可变；后续动作只能 show/select，不得恢复写入。
5. context 压缩或新 turn 时只读合同与台账即可恢复：running plan 按 `phase` 续；rework 重新 start；passed 跳过。
6. `PENDING` 只表示 reviewer 尚未形成有效终态，不计失败、不启动第二 reviewer。
7. plan 最多 start 三次；第三次失败后 run 终态化，第四次 start 在状态机层拒绝。
8. event-first 提交：event 带连续序号及完整 `state_after`，随后原子替换 state；中断恢复只允许 event 比 state 领先，并从最后 event 重放。序号相等时规范化比较 state 与最后 event 的 `state_after`；内容漂移、缺号、坏行、state 超前均停止人工检查。
9. 冻结输入每个可变动作前重算 hash；路径必须 repo-relative，并对已存在祖先解析 reparse target，防 repo 内 junction/symlink 逃逸。
