---
name: triple-planner
description: 在用户明确选择 planner-coder-tester 三会话模式时，跨开发 repo 与生产项目 repo 编排开发 coder 和生产 tester，自动完成候选发布、YAML 人工闸门、PowerPoint 视觉闸门、Word 验证及失败返工闭环。仅在用户显式调用 $triple-planner 时使用；普通两会话任务继续使用 $double-planner。
---

# `$triple-planner`

这是显式启用的三会话 planner，不是 `$double-planner` 的默认升级。两会话模式永远回到 `$double-planner + $double-coder`，不得由本 skill 自动推断复杂度并切换。

## 加载顺序

每次启动或 Goal continuation 都完整读取：

1. 当前开发 repo 的启动链；
2. `../double-planner/SKILL.md`；
3. `../../double-session-common/protocol.md`；
4. `../../triple-session-common/protocol.md`；
5. `../../triple-session-common/triple-session-config.json` 及其指向的 double 配置。

任一文件缺失即返回 `TRIPLE_COMMON_MISSING`。继承 double-planner 的权限硬门、状态动作沙箱纪律、预算、worker token、WaitTurn、审核阶梯、failure ledger 与最终 review gate。只覆盖三点：使用三会话合同、使用双 token Goal、生产测试通过前禁止 Done。

- `WAITTURN_UX=SILENT_UNTIL_RETURN`：对开发通道 `WaitTurn` 或生产 relay `wait-turn`，同一个底层工具 cell 尚未完成时，只允许继续等待。外围 `wait` 即使按约 50 秒临时 yield，只要返回的仍是同一 running cell，就必须立即对同一 cell 再次 `wait`；禁止输出“继续监听 / 仍在运行 / 等待中”等自然语言心跳，禁止仅为播报重读 state。只在合法 Handoff/Done 信号、完整 `TimeoutSeconds` 到期或异常退出后报告一次。

状态工具：

```powershell
$doubleState = "$env:USERPROFILE\.agents\double-session-common\double-session-state.ps1"
$relay = "$env:USERPROFILE\.agents\triple-session-common\tester-relay.py"
```

开发通道仍由 `$doubleState` 管理，生产通道只由 `$relay` 管理。不得手改 `.copilot-state.json` 或 `.triple-tester-state.json`。

启动或恢复调度时调用 relay `config`，固化 `planner_relay_wait_seconds = role_intervals.planner`。triple 配置只保存继承映射，实际数值唯一来自现有 `double-session-config.json`：planner 使用 `planner_interval_seconds`，tester 使用 `coder_interval_seconds`，并共享 `max_budget_seconds` 口径。不得在 triple skill 或 relay 中复制默认秒数。

## 合同准备

工作目录必须是开发 Git 根。先取得 `git rev-parse --show-toplevel`，再用 `(Resolve-Path -LiteralPath <git-output>).Path` 固化 `development_repo`；对合同中的 `production_project_root` 同样先 `Resolve-Path`。沿用 double-planner 的 `BootstrapProbe → ConsumeDraft → 写合同 → CommitContract`；读取该 Git 根的 `temp.md` 必须由 `ConsumeDraft` 完成并在返回前清空、验空。遵守 double/triple 共通规则：交接文件始终是当前协作 repo 根的 `temp.md`。skill 母本另记为 `source_skill_root`，不得在该源码子目录另建或使用交接 `temp.md`。

在标准 `DOUBLE_TASK_CONTRACT=v1` 中追加公共 triple 协议规定的 `## triple_workflow`。冻结前必须验证：

- `workflow_mode` 精确等于 `planner-coder-tester`；
- `development_repo` 等于当前 Git top-level，`source_skill_root` 是其内明确授权的母本目录；生产 skill 副本、生产项目和人工 Golden 均为绝对路径；
- Golden 只允许 planner/coder 读取；
- 部署副本与生产项目写入已获任务授权；
- YAML、PowerPoint 视觉和 Word 阶段顺序已写入 `done_when`；
- tester 不得修改生产副本换取通过；
- coder 不得进入生产 repo。

缺用户独有路径或授权时停在 `TRIPLE_TASK_PREFLIGHT_REQUIRED`，不创建 Goal、state 或 relay。

### 旧终态切换

若 `BootstrapProbe.route=TERMINAL_ARCHIVE_THEN_PREPARE`，先对探针返回的旧 terminal run 调用幂等 `ArchiveRun`，再核对归档路径与 `terminal_archive_sha256`。不要等待探针 route 变成 `CONTRACT_READY`：旧 state 会保留，所以 route 仍为 `TERMINAL_ARCHIVE_THEN_PREPARE`。

改用 `terminal_next_route` 决策：其为 `CONTRACT_READY` 且 `task_validation.valid=true` 时，直接以 `task_validation.task_sha256` 作为 prepared hash 进入双 token Goal；其为 `PREPARE_DRAFT` 时才执行 ConsumeDraft/KO/CommitContract；其他值按对应 preflight 返回。已准备合同不得再次消费或改写。

## 双 token Goal

生成两个互不相同的随机 token：`double_worker_token` 绑定开发 planner；`relay_worker_token` 绑定生产 relay planner。调用 relay `goal-contract --role planner`，传已经 `Resolve-Path` 的开发 repo、生产项目 repo、prepared task SHA-256 与两个 token。严格校验 JSON 信封的 `envelope=TRIPLE_PLANNER_GOAL_ENVELOPE=v1`、`path_identity=RESOLVED_PATH_IDENTITY_V1`、两个路径身份及 objective 首行，然后把 `goal_objective` 逐字传给 `create_goal`。

两个路径必须按公共协议的“解析后路径身份”比较，禁止直接比较原始字符串。Windows 下 `D:/x` 与 `D:\x`、盘符大小写或末尾分隔符差异不构成失败；解析后目录不同才 fail-loud。路径核验失败时报告规范化前后四个值，便于定位，但不得回显 token。

本入口不得调用 double-planner 的 `GoalContract`，因为单 repo objective 无法持久化生产 relay token；这是 triple 入口唯一的 Goal 覆盖。两个 token 只能从 Goal objective 恢复，不得依赖 `store()`，不得回显给用户。

## 自动检查循环

### A. 开发阶段

沿用 double-planner 的预启动监视：等待 `$triple-coder` 调用现有 `Init`。state 出现后核对开发 repo、prepared task SHA-256 和 run id。开发 turn 行为保持：

- `turn=coder`：用现有 `WaitTurn` 等待；
- `turn=planner`：`CheckBudget → Consume`，读取真实文件和 coder 交接；
- 开发候选不合格：写可执行 REWORK 到开发 `temp.md`，Handoff 给 coder；
- 开发候选合格：核对 release id、manifest、源码树哈希、测试证据和 doctor guard 变化，再进入生产阶段；此时禁止 `Done`。

### B. 首次交给 tester

先用 relay `probe` 确认生产项目 `temp.md` 为空且没有 active relay。把 `DEPLOY_AND_BUILD_YAML` 自足请求写入生产项目 `temp.md`，随后调用：

```powershell
python -X utf8 $relay init --root <production_project_root> `
  --run-id <development_run_id> --dev-repo <development_repo> `
  --release-id <release_id> --worker-token <relay_worker_token>
```

只有 `INIT` 成功且 `temp.length=0` 才算交棒完成。tester 未启动只是正常等待；保持 Goal，用 relay `wait-turn --role planner --observed-seq <当前 seq> --timeout-seconds <planner_relay_wait_seconds>` 等待。tester Handoff 的 tickle 可提前唤醒；无信号才在完整配置周期到期后复查，不要求用户重启。

### C. 处理 tester 返回

relay 显示 `turn=planner + phase=ready` 时，先 `consume --role planner`，再读取返回的 `.triple-tester-message.md`；不得直接读取生产 `temp.md`。

- `YAML_PENDING_USER_REVIEW`：独立核对 YAML 路径、结构门、哈希及未生成 PowerPoint/Word，然后调用 relay `wait-human --approval-kind yaml --artifact-path ... --artifact-sha256 ...`。用户批准后，用返回的 approval id 调 `resolve-human --decision approve`；工具复核磁盘哈希后，向生产 `temp.md` 写 `CONTINUE_PPT` 并 Handoff tester。不得调用 double 的失败熔断 `WaitHuman`。
- `PPT_VISUAL_PENDING`：核对结构证据与当前 PowerPoint 哈希，再用 relay `wait-human --approval-kind ppt` 等待用户视觉批准。批准后先 `resolve-human` 复核哈希，再写 `CONTINUE_WORD` 并 Handoff tester。
- `PRODUCTION_TEST_PASS`：独立核对 Word、共用表格数据、批准哈希和生产副本未编辑证据；满足全部冻结 done_when 后才进入最终 gate。
- `REWORK_REQUIRED`：把 tester 的自足失败报告、failure key、release id 与证据原样写入开发 `temp.md`，通过现有 planner→coder Handoff 开启下一轮。relay 保持 planner working；新候选达标后用新的 release id 写下一份 `DEPLOY_AND_BUILD_YAML` 并 Handoff tester。

向 tester 的所有后续交棒固定使用：

```powershell
python -X utf8 $relay handoff --root <production_project_root> `
  --role planner --to tester --worker-token <relay_worker_token> `
  --expected-run-id <development_run_id> --release-id <current_release_id>
```

## 完成、取消与恢复

最终先按 double 协议记录 planner/mc-expert review gate。全部通过后：先对 relay `done --role planner`，再对开发 state `Done -Role planner`；任一步失败都不得宣称完成。

取消 active triple run 时，先保持证据并取消生产 relay，再取消开发 run。人工批准只存在于 relay，不改变 double failure ledger。终态 relay 必须 `archive` 后才允许同一生产项目创建新 run。

原 session 恢复时，从 `TRIPLE_PLANNER_GOAL_CONTRACT=v1` 恢复两个 repo、两个 token、prepared hash 与 run 绑定，先读 live 文件，再分别 `Show/probe`。状态冲突时 fail-loud，不自动 takeover。用户仅负责人工批准；不得要求其复制 tester 报告或重新启动三个角色。

生产 relay 正轮到 tester、等待人工批准或 state 未变化都是正常监听态，不得因连续 Goal continuation 相同而把 planner Goal 标成 blocked。每次 continuation 热加载 live config；只有 `done|cancelled` 或无法由合法 Handoff/tickle 恢复的真实协议死路才结束或阻塞 Goal。
