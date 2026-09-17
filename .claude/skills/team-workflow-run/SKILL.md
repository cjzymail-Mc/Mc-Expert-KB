---
name: team-workflow-run
description: team-workflow 已绑定 B 窗口的内部单轮执行适配器。仅处理当前 workflow run/round 的授权接棒，复用 team-task P0-P6；没有有效状态时立即拒绝。
user-invocable: false
argument-hint: "run=<workflow-run> round=<N> [resume_token=<token>]"
---

# team-workflow-run（内部入口）

本 skill 在 B **当前主会话**运行，不 fork subagent。唯一正常调用者是用户已显式启动的 `/team-workflow run`。本次 session=`${CLAUDE_SESSION_ID}`。不要调用 `Skill(team-task)`，因为该公共入口明确禁用 model invocation；下面是 team-task 正式允许的受控委托入口。

1. 解析 `$ARGUMENTS`，仅接受 `run/round` 和可选 `resume_token`；缺失、重复、其它参数立即拒绝。helper 位于本包同级 `../team-workflow/scripts/workflow.py`。在碰业务文件前执行：

   ```text
   python "<skills>/team-workflow/scripts/workflow.py" enter --repo "<repo>" --session "<本窗口ID>" --run <run> --round <N> [--resume-token <token>]
   ```

   只有成功接棒才能继续。已有 B_RUNNING、错误窗口、旧通知、旧 round 均不得重新执行；拒绝后返回调度器，不自行补造 resume_token。用户明确 `/team-workflow resume` 所获 token 仅消费一次。

2. `permit --run ... --round N` 核对同一状态，取 `team_run/source_id/source_sha256/runtime_evidence/failures`。需求输入仅为 `team-task.md`；另读 repo 的环境/权限硬规则、本轮执行必要资料和**同级 `../team-task/SKILL.md` 全文**，P0-P6 细则从其 funnel-gate 读取。正式执行同一正文，不维护缩减版流程。**不寻找或读取 A 的独立基线、criteria 清单，不把它们列为 B 冷启动或执行前置**；原始需求覆盖由 A 负责，本轮必要条款须已写在任务中。

3. 本轮映射：`run_id=state.team_run`，`source_block_id=state.source_id`。首轮 P0 用这两个已分配值初始化，不另造时间戳；恢复沿用已有 progress/合同和阶段标记。记录 `workflow_run/workflow_round/entry=team-workflow-run`、任务 source hash、真实 GLM runtime 证据、B 的 run 启动授权和累积失败字典。A 未加入时没有基线路径/hash、criteria 或总轮数，均不阻止 B 完成首轮，不能补造或猜测；finish 后等 A，不自行派第二轮。仅 GLM 常设 MEDIUM + B/AUTO 授权可沿用；HIGH、真正阻断 FACT、四红线、陪审不可用等仍按 team-task 停。

4. 按现行 team-task 完整执行 P0.5-P6，包括 chop-task、冻结合同/增补、生产 skill、失败陪审、fresh ENHANCED_FINAL 和收尾。B 及其本轮 reviewer 的 REQUIREMENTS 来自当前 task source + 生效合同，验本轮 done_when；不代 A 判全局基线。不得改 source、降低判据或自加下一轮。每个检查点及最终冻结前先 `status`：若 stop_requested，停止新增工作，完成在途写入并关闭团队，留可恢复 progress 后 `pause --reason ...` 返回；不硬杀进程。

5. 达标后正常跑 team-task 的 mc-update→pin→session-new 预判/收尾；这些内部记忆/交接动作不负责跨窗口消息。session-new 沿母本仅固化文件，不真的清空、关闭或重开 B。收尾完成再原子写 `COMPLETE + P6✓`，shutdown 所有 teammate / Clean up the team，确保没有仍在写产物的执行体。

6. 按 [../team-workflow/references/relay.md](../team-workflow/references/relay.md) §2 写 handoff-input.json，执行 `finish`。正常完成必须绑定真实产物/证据 hash；阻断写 blocked/halted 和真实 WAIT_HUMAN/HALTED，不能伪装成功。脚本失败则保留现场、静止后 `pause --reason <错误>`，只报告一次，不自己修改 state 续命。

7. `finish` 已负责归档、提交 A_REVIEW 与事件通知；A 尚未加入时同样提交，结果留盘供它晚到验收。返回 team-workflow 主调度器，再根据最新状态挂一小时后台 wait。不直接编辑 A 的验收报告，不对 A 发送“你应当判 PASS”等结论，不自动重跑本轮，不再开自己的循环。
