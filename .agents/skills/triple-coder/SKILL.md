---
name: triple-coder
description: 在用户明确选择 planner-coder-tester 三会话模式时担任开发 coder，只修改开发 skill 母本、运行开发验证并冻结可部署候选版本，再通过现有开发通道自动交还 triple-planner。仅在用户显式调用 $triple-coder 时使用；普通两会话任务继续使用 $double-coder。
---

# `$triple-coder`

这是三会话流程的开发 coder。它复用现有 double-session 状态机，但不承担生产部署、YAML 人工批准、PowerPoint 视觉批准或 Word 生产验收。

## 加载顺序

每次启动或 Goal continuation 都完整读取：

1. 当前开发 repo 的启动链；
2. `../double-coder/SKILL.md`；
3. `../../double-session-common/protocol.md`；
4. `../../triple-session-common/protocol.md`；
5. [release-candidate-contract.md](references/release-candidate-contract.md)。

继承 double-coder 的权限硬门、`BootstrapProbe`、现有 GoalContract、Init、WaitTurn、预算、token、Consume/Handoff、失败 ledger 和零普通人工门规则。开发 state 的角色仍精确为 `coder`；不得接触 `.triple-tester-state.json`。

- `WAITTURN_UX=SILENT_UNTIL_RETURN`：同一个 `WaitTurn` 底层工具 cell 尚未完成时，只允许继续等待。外围 `wait` 即使按约 50 秒临时 yield，只要返回的仍是同一 running cell，就必须立即对同一 cell 再次 `wait`；禁止输出“继续监听 / 仍在运行 / 等待中”等自然语言心跳，禁止仅为播报重读 state。只在合法 Handoff/Done 信号、完整 `TimeoutSeconds` 到期或异常退出后报告一次。

## 启动门

只有冻结合同同时满足以下条件才允许 Init：

- 标准 `DOUBLE_TASK_CONTRACT=v1` 有效；
- `## triple_workflow` 存在；
- `workflow_mode: planner-coder-tester`；
- 当前 Git top-level 等于合同的 `development_repo`；
- `source_skill_root` 是独立字段，修改范围只覆盖该开发母本与开发证据路径。

交接文件只使用 `development_repo/temp.md`。不得因为 `source_skill_root` 是主要修改目标，就在 skill 母本子目录创建或读取另一份 `temp.md`。

否则返回 `TRIPLE_CONTRACT_REQUIRED`，不创建或接管普通 double run。

### 终态归档后的 route 覆盖

本入口仅覆盖 double-coder 的一个启动分支。以下两种探针结果都可进入上述合同启动门：

1. `route=CONTRACT_READY`；
2. `route=TERMINAL_ARCHIVE_THEN_PREPARE` 且 `terminal_next_route=CONTRACT_READY`，同时旧 state 为 `done|cancelled`、`archive_path` 存在、归档文件 SHA-256 等于 `terminal_archive_sha256`、`task_validation.valid=true`。

第二种是已归档终态后的正常新 run，不要等待 route 自动变成 `CONTRACT_READY`；`ArchiveRun` 不删除旧 state，因此该变化不会发生。使用探针的 `task_validation.task_sha256` 作为 `PreparedTaskSha256` 调用现有 `Init`，让状态工具再次验证新任务哈希/时间和归档门。coder 不调用 `ArchiveRun`，任一条件不满足仍返回 `TASK_PREFLIGHT_REQUIRED`。此覆盖只适用于 `$triple-coder`，不得改写或放宽 `$double-coder`。

## 开发轮

沿用 `$double-coder` 的正常检查循环。每次轮到 coder：

1. `CheckBudget → Consume`；
2. 读取冻结 task 和 planner 的最新交接；
3. 只在开发 repo 修改 skill 母本；
4. 以人工 Golden 为目标参照抽象通用规则，但不得把客户答案硬编码进 skill 或测试 fixture；
5. 运行范围内静态测试、动态正例和可靠失败负例；
6. 生成不可复用的 `release_id`；
7. 用 production-tester 自带的 `release_manifest.py create` 冻结完整源码清单；
8. 写入 [release-candidate-contract.md](references/release-candidate-contract.md) 规定的候选报告；
9. 把报告写入开发 `temp.md`，调用现有 `Handoff -Role coder -To planner`。

不得把复制到生产副本、运行真实生产项目或修改生产 YAML/PowerPoint/Word 当作 coder 验证。tester 返回的失败只能由 planner 通过开发 Handoff 交给 coder；coder 不读取生产项目 `temp.md`。

## 返工

收到 tester 失败回流时，逐项核对 failure key、release id、实际证据与未满足 done_when。只修开发母本；每个实质变化都生成新的 release id 与 manifest，旧候选、旧 YAML/PowerPoint 批准全部失效。

失败交接继续使用现有 `HandoffKind failure + FailureKey`。coder 永远不得 `WaitHuman` 或 `Done`，也不得因 tester 未启动而结束 Goal。
