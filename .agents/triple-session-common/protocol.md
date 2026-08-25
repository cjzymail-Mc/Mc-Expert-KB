# Triple session extension protocol

本协议只服务显式启用的 `planner-coder-tester` 三会话流程。它是现有 double-session 的旁路扩展，不修改、不替代 `$env:USERPROFILE\.agents\double-session-common\protocol.md`。

## 1. 选择与兼容

- 两会话：用户调用 `$double-planner` 与 `$double-coder`。现有文件、状态、命令和行为保持不变。
- 三会话：用户调用 `$triple-planner`、`$triple-coder` 与 `$production-tester`。
- 三会话合同必须包含 `workflow_mode: planner-coder-tester`；模式在合同提交后冻结，中途不得切换。
- 缺少该字段或值不是精确的 `planner-coder-tester` 时，三个 triple 入口必须拒绝启动，不得自行升级普通 double run。

## 2. 两个 repo、两个 temp.md

统一定位规则：double 与 triple 都只使用“当前协作 repo 根目录下的 `temp.md`”。`temp.md` 不跟随待修改的源码/skill 子目录；子目录即使是本轮主要修改目标，也不得另建交接 `temp.md`。triple 只是同时存在开发协作 repo 与生产测试协作 repo，因此两个 repo 根各有一个 `temp.md`，并不改变根目录规则。

| 通道 | 暂存文件 | 状态所有者 |
|---|---|---|
| planner ↔ coder | 开发 repo 根 `temp.md` | 现有 double-session state |
| planner ↔ tester | 生产项目 repo 根 `temp.md` | `tester-relay.py` |

生产 skill 副本目录只是部署目标，不是协作 repo，不承载接力状态。coder 永远不读写生产项目 `temp.md`；tester 永远不读写开发 repo `temp.md`；planner 是唯一跨 repo 的桥。

每次读取 `temp.md` 都由对应状态工具在锁内完成“读取 → 固化到 message 文件 → 写空 → 验证长度为 0”。模型不得直接模拟该事务。

### 共享调度配置与 tickle

triple 不维护第二套秒数。`triple-session-config.json` 只保存继承映射，数值唯一读取 `../double-session-common/double-session-config.json`：relay planner 使用 `planner_interval_seconds`，production tester 使用 `coder_interval_seconds`，并暴露同一 `max_budget_seconds`。live 配置在每次 Goal continuation 重新读取，旧 Goal/run 不因配置热加载而换 token 或重建 state。

生产 relay 的 `wait-turn` 使用 Windows 命名自动重置事件作为 tickle：`init` 唤醒 tester，`handoff` 唤醒目标角色，`done/cancel` 唤醒等待者。信号只负责提前唤醒，醒后仍以磁盘 state 为准；信号丢失则以共享 JSON 的最长等待周期兜底。不得用 0.25 秒轮询、短周期反复 `show` 或后台循环代替。

轮到对方、等待人工批准、一次完整超时或 state 多轮未变化都是正常调度等待，不构成 Goal blocked 计数；这些状态可由合法 Handoff/tickle 恢复。Goal 只按终态或真实不可恢复协议死路收束。

### 路径身份合同

Goal 信封使用 `RESOLVED_PATH_IDENTITY_V1`。严格路径校验比较的是解析后的路径身份，不是原始字符串：先确认路径为已存在的绝对目录，再解析完整路径并去除末尾分隔符；Windows 下比较时忽略盘符/目录大小写以及 `/` 与 `\` 的表示差异。只有解析后指向不同目录才是 `REPO_MISMATCH`。例如 `D:/repo` 与 `D:\repo` 不得因斜杠不同而触发熔断。

调用 relay 前，PowerShell 入口先用 `(Resolve-Path -LiteralPath <path>).Path` 固化开发 repo 与生产项目 repo，再把同一组值用于合同、命令参数和信封核验。Goal 信封必须同时满足 `path_identity=RESOLVED_PATH_IDENTITY_V1`，且 objective 内含同值 `PATH_IDENTITY`；不得以放宽 marker、role、objective 首行或 token 校验来规避路径问题。

## 3. 三会话合同追加段

`$triple-planner` 在既有 `DOUBLE_TASK_CONTRACT=v1` 后追加：

```markdown
## triple_workflow
workflow_mode: planner-coder-tester
development_repo: <absolute Git top-level used by double-session state>
source_skill_root: <absolute skill mother path; may be a subdirectory of development_repo>
production_skill_root: <absolute path>
production_project_root: <absolute path>
golden_reference: <absolute path; planner/coder only>
tester_may_read_golden: false
yaml_gate: user_sha256_approval
ppt_visual_gate: user_sha256_approval
word_gate: after_ppt_approval
doctor_policy: preserve_runtime_unless_guard_changed
```

`development_repo` 与 `source_skill_root` 是两个不同概念：前者承载开发 `temp.md/.copilot-*`，必须等于 `git rev-parse --show-toplevel`；后者才是 coder 可以修改的 skill 母本。路径、人工门或部署授权缺失时，planner 必须在合同冻结前停下；不得让 tester 猜路径。Golden 只供 planner/coder 抽象规则与验收，tester 不得读取。

## 4. 开发通道

`triple-planner` 与 `triple-coder` 复用现有 double-session 的 `BootstrapProbe / ConsumeDraft / CommitContract / Init / Show / WaitTurn / Consume / Handoff / WaitHuman / ResolveHuman / Done`。开发状态仍只有 `planner|coder` 两个 turn；tester 永远不进入 `.copilot-state.json`。

差异只有职责边界：

- coder 只修改开发母本、运行开发验证、冻结候选版本和 manifest；不得进入生产 repo。
- planner 在开发候选达标后不 `Done`，而是向生产通道发 `DEPLOY_AND_BUILD_YAML`。
- tester 失败后，planner 把自足失败报告写入开发 `temp.md` 并 Handoff 给 coder；同一开发 run 继续。
- 只有生产测试最终通过且冻结 `done_when` 全部有证据时，planner 才执行最终 gate 与 `Done`。

### 已归档终态切换

`ArchiveRun` 只固化旧 run 证据，不删除 `.copilot-state.json`。因此旧终态归档成功后，`BootstrapProbe` 仍会返回 `route=TERMINAL_ARCHIVE_THEN_PREPARE`；这是预期行为，不会自动变成 `CONTRACT_READY`。后续入口必须读取 `terminal_next_route`，禁止等待一个不会发生的 route 变化。

- planner：对旧终态调用幂等 `ArchiveRun` 后，核对 `archive_path` 存在且 SHA-256 等于 `terminal_archive_sha256`。若同一次探针的 `terminal_next_route=CONTRACT_READY` 且合同校验有效，直接用 `task_validation.task_sha256` 创建 PENDING triple Goal；不得重复 ConsumeDraft、重写合同或等待 route 改名。
- coder：除普通 `route=CONTRACT_READY` 外，也接受 `route=TERMINAL_ARCHIVE_THEN_PREPARE + terminal_next_route=CONTRACT_READY`，但必须同时确认旧 state 为 `done|cancelled`、归档文件及哈希匹配、当前合同校验有效。随后调用现有 `Init`；由状态工具再次机械检查新任务时间/哈希、归档存在和 prepared hash，并原子替换旧终态 state。
- 其余 terminal_next_route、归档缺失或哈希不符一律 fail-loud。coder 不得自行调用 `ArchiveRun`，double 两会话入口行为保持不变。

## 5. 生产接力消息

每份生产接力正文首行固定为 `TRIPLE_TEST_RELAY=v1`，并包含：

```text
run_id: <development run id>
relay_seq: <integer>
release_id: <immutable candidate id>
action: <DEPLOY_AND_BUILD_YAML|CONTINUE_PPT|CONTINUE_WORD|RESULT>
source_manifest_sha256: <sha256 or N/A>
approved_artifact_sha256: <sha256 or N/A>
```

正文随后写绝对路径、允许动作、退出码、证据和阶段结果。relay 工具机械校验 marker、`run_id/release_id/relay_seq/action/hash` 必填字段；任一不匹配即 fail-loud，旧消息不得重放。planner→tester Handoff 必须显式传当前 `release_id`；返工后的新候选由该动作原子更新 state 中的版本绑定。

## 6. 自动接力顺序

1. planner 审核 coder 的冻结候选。
2. planner 把 `DEPLOY_AND_BUILD_YAML` 写入生产项目 `temp.md`，首次调用 relay `init`，后续调用 `handoff --role planner --to tester`。
3. tester `consume` 后部署、做清单一致性检查、复用生产环境并只生成 YAML。
4. tester 把 `YAML_PENDING_USER_REVIEW` 结果写回生产 `temp.md`，Handoff 给 planner。
5. planner `consume`、独立核对哈希，然后用生产 relay 的 `wait-human` 暂停并绑定当前 YAML 哈希；不得调用 double 的失败熔断 `WaitHuman`。
6. 用户批准后，planner 用 relay `resolve-human` 复核磁盘哈希，再写 `CONTINUE_PPT` 并 Handoff tester。
7. tester 只生成 PowerPoint、做结构检查，返回 `PPT_VISUAL_PENDING`。
8. planner 用同一 relay 人工门取得绑定当前 PowerPoint 哈希的批准后，写 `CONTINUE_WORD`。
9. tester 生成 Word、验证共享表格数据，返回 `PRODUCTION_TEST_PASS`。
10. planner 独立复核全部 done_when 后，先完成既有 review gate，再对生产 relay `done`，最后对开发 run `Done`。

用户只负责批准，不负责复制消息、重新启动角色或转写失败报告。

## 7. 失败与恢复

- tester 的任何失败都必须返回 `REWORK_REQUIRED`、稳定 failure key、实际证据、未满足 done_when 和 `PRODUCTION_COPY_EDITED: false`。
- planner 收到失败后必须把完整报告转入开发通道；不得在生产副本现场修复。
- 新候选必须使用新 `release_id` 和新 manifest 哈希；旧人工批准全部失效。
- tester session 启动早于首个请求时，持有 PENDING Goal 并使用 relay `wait-turn`；不得要求用户重启。
- tester 或 planner 原 session 恢复时，从 Goal objective 恢复 repo、run、role 与 token；临时缓存不是跨 turn 真相源。
- `claim` 只用于角色首次绑定。Goal objective 丢失 token 时 fail-loud；不得让第二个同角色会话抢占 active relay。
- 开发 run 取消时，planner 同时取消生产 relay。终态 relay 归档后才允许同一生产项目开启新 run。

## 8. 冷启动隔离

tester 只能读取：生产 skill 副本、原始项目资料、planner 写入的冻结请求、候选 manifest 与本轮证据。不得读取人工修订 PowerPoint、开发调试记录、历史正确 YAML 或旧输出。视觉通过必须来自用户；纯文本 Codex-GLM 不得自行签发。

## 9. 完成定义

三会话只有同时满足以下条件才完成：候选清单一致；生产环境测试通过；YAML 批准绑定当前哈希；PowerPoint 结构门与人工视觉批准绑定当前哈希；Word 结构门通过；生产副本部署后未被就地修改；planner 的既有最终 review gate 通过。
