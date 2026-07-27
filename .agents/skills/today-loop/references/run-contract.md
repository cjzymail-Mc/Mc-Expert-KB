# `$today-loop` Run Contract v1.1（PRE-GO authorization）

启动 Goal 前在普通非 Goal 会话冻结 contract、plan list 与 authorization pack；运行中只读，不回写三者。用户发送带 authorization pack SHA-256 的单条 `/goal`，同时完成批准与正式 GO。

## contract.json

必填字段：

```json
{
  "schema_version": 1,
  "run_id": "unique-run-id",
  "mode": "autopilot",
  "plan_file": "repo-relative plans.json",
  "run_dir": "repo-relative run directory",
  "allowed_paths": ["repo-relative/path"],
  "forbidden_actions": ["delete", "push", "external-delivery"],
  "human_gates": ["four-red-lines", "scope-expansion"],
  "unattended": {
    "authorization_pack": "repo-relative authorization-pack.json",
    "objective_token": "UNATTENDED_AUTH_SHA256",
    "goal_is_go": true,
    "interactive_actions": "forbidden",
    "unexpected_approval": "defer-or-wait-human"
  },
  "budgets": {"max_plans": 2, "max_consecutive_failures": 2},
  "terminal_evidence": ["state.json", "events.jsonl"]
}
```

约束：

- `mode` 只能是 `autopilot`。
- `allowed_paths`、`human_gates`、`terminal_evidence` 不得为空。
- `max_consecutive_failures` 必须为 2；不得由模型临时放宽。
- `run_dir`、`plan_file` 与全部 allowed path 必须位于当前 repo；外部路径直接 `WAIT_HUMAN`。
- authorization pack 必须列出允许写路径、只读输入、计划命令类别、reviewer 路由、禁止动作、人工门与意外权限策略；Goal objective 的唯一 `UNATTENDED_AUTH_SHA256` 必须与文件实际小写 SHA-256 相同。
- `goal_is_go=true`：禁止设计“只创建 Goal 后暂停”的第一条消息；一条 `/goal` 即启动。
- 运行中不主动发起 pack 外的新 approval/Computer Use/Office GUI/第三方交互。可延后需求进 `pending-human`；硬依赖转 `WAIT_HUMAN`；四红线即时停。
- 合同哈希应在真实 run manifest 中记录；首件 fixture 只验证结构与状态机。

## Reviewer 等待语义

- `No agents completed yet`、bounded wait 超时且 child 仍 active = `PENDING`，不计 transport attempt。
- 默认 20–30 秒轮询、600 秒 hard deadline；同一 checkpoint 不并发启动第二个 reviewer。
- 只有终态失败、hard deadline 无 `task_complete`、空正文、schema/provenance 缺失才计 transport failure；fresh attempt 总上限 2。

## plans.json

```json
{
  "schema_version": 1,
  "plans": [
    {
      "id": "P-A",
      "title": "first bounded outcome",
      "depends_on": [],
      "done_when": "the first result exists and its required properties are verified",
      "reference": "optional repo-relative reference or example"
    },
    {
      "id": "P-B",
      "title": "second bounded outcome",
      "depends_on": ["P-A"],
      "done_when": "the second result satisfies its stated acceptance properties"
    }
  ]
}
```

约束：plan id 唯一、依赖必须存在、禁止自依赖/循环依赖，plan 数不得超过 contract budget。`done_when` 必填、trim 后非空，描述结果状态而非动作清单；`reference` 可选，省略时 state 统一透传为空串。状态不写回此文件，统一落 run `state.json`。

## 状态迁移

```text
pending -> running -> passed
                  \-> rework -> running
                  \-> wait_human (run terminal)
                  \-> failed (第二次连续失败，run halted)
all passed -> complete
```

只有进入 `passed` 的 attempt 必须 reset/finalizer 各恰好一次；`pass` 会确定性拒绝 0 次或大于 1 次。REWORK/HALTED/WAIT_HUMAN 允许在完整 finalizer 前终止，其必要 handoff 由共同 binding 处理，不伪记 full-finalizer=1。

