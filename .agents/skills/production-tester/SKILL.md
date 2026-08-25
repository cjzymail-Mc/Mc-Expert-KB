---
name: production-tester
description: 在用户明确选择 planner-coder-tester 三会话模式时担任独立生产 tester，启动一次后持续监听生产项目 repo 的接力状态，部署开发候选副本，并按 YAML 人审、PowerPoint 结构与视觉人审、Word 复用验证的顺序自动向 triple-planner 交接。仅在用户显式调用 $production-tester 时使用；不加入或影响普通 double-workflow。
---

# `$production-tester`

这是三会话流程的第三个持久会话。工作目录必须是生产项目 repo；生产 skill 副本 repo 只是部署目标。启动一次后持续等待 planner 请求，不要求用户复制消息或重新启动 tester。

## 加载顺序

每次启动或 Goal continuation 都完整读取：

1. 当前生产项目 repo 的启动链；
2. `../../triple-session-common/protocol.md`；
3. [relay-contract.md](references/relay-contract.md)；
4. `../../triple-session-common/triple-session-config.json` 及其指向的 double 配置；
5. 当前部署候选自己的生产说明，仅在收到首个请求后读取。

状态工具固定为：

```powershell
$relay = "$env:USERPROFILE\.agents\triple-session-common\tester-relay.py"
```

缺公共核心即返回 `TRIPLE_COMMON_MISSING`。不得读取或修改开发 repo 的 `temp.md`、`.copilot-*` 或 double Goal；不得手改 `.triple-tester-state.json`。

启动或恢复调度时先调用 relay `config`，固化 `tester_wait_seconds = role_intervals.tester`。该值必须来自 triple 映射所继承的 `double-session-config.json`，不得使用 skill 内默认值。当前映射把 tester 视为执行方，使用 `coder_interval_seconds`；`max_budget_seconds` 同源返回并写入新 Goal 合同。配置损坏时 fail-loud。

- `WAITTURN_UX=SILENT_UNTIL_RETURN`：同一个 relay `wait-turn` 底层工具 cell 尚未完成时，只允许继续等待。外围 `wait` 即使按约 50 秒临时 yield，只要返回的仍是同一 running cell，就必须立即对同一 cell 再次 `wait`；禁止输出“继续监听 / 仍在运行 / 等待中”等自然语言心跳，禁止仅为播报重读 state。只在合法 Handoff/Done 信号、完整 `timeout-seconds` 到期或异常退出后报告一次。

## 不变量

- 开发目录是 skill 唯一母本；生产目录只接收冻结候选并执行测试。
- tester 只在部署动作中写生产 skill 副本；清单通过后副本转为只读。
- 不在生产副本中修 skill、verifier、Golden、合同或文档换取 PASS。
- 固定顺序为 `YAML → PowerPoint → Word`；前一阶段未获允许，不生成后一阶段。
- Codex-GLM 只能报告结构证据，不能签发视觉通过。
- 不读取人工修订 PowerPoint、开发调试记录、历史正确 YAML 或旧输出。
- 同一路径连续失败两次即返回稳定 failure key，不做第三次原样重试。
- tester 永远不调用人工门；只把 pending 结果 Handoff 给 planner。

## 启动与 Goal

先用 `(Resolve-Path -LiteralPath (Get-Location).Path).Path` 固化 `production_project_root`，再调用 relay `probe`。生成唯一 tester token，调用 `goal-contract --role tester --root <production_project_root> --worker-token <token>`。严格校验 JSON 信封的 `envelope=TRIPLE_TESTER_GOAL_ENVELOPE=v1`、`path_identity=RESOLVED_PATH_IDENTITY_V1`、repo 路径身份与 objective 首行，然后把 `goal_objective` 逐字传给 `create_goal`。路径按公共协议解析后比较；Windows 的斜杠、大小写或末尾分隔符表示差异不得误判为 repo 不同。

relay 尚未初始化时保持 PENDING Goal，调用 `wait-turn --role tester --expected-run-id PENDING --observed-seq -1 --timeout-seconds <tester_wait_seconds>` 等待。state 出现且首次轮到 tester 时调用 `claim`；后续只从 Goal objective 恢复 token，不依赖 `store()`。非完整 Handoff 边界不得换 token 或 takeover。

每次 Goal continuation 都重新读取 live skill、公共协议与 relay `config`；因此配置和等待修复可在原 run 热加载。已有匹配 Goal 必须复用，不因热加载换 token、重新 claim 或重建 relay。

## 自动检查循环

每轮先 `show`：

- `done|cancelled`：结束 Goal；cancelled 不报告生产 PASS。
- `turn=planner`：调用 `wait-turn --role tester --observed-seq <当前 seq> --timeout-seconds <tester_wait_seconds>`；planner Handoff 的 tickle 可提前唤醒，完整超时后才复查。
- `turn=tester + phase=ready`：调用 `consume`，再读取返回路径指向的 `.triple-tester-message.md`；不得直接读取生产 `temp.md`。
- 消息的 `run_id/release_id/relay_seq/hash` 不匹配：返回 `RELAY_MESSAGE_MISMATCH`，不执行生产动作。

`turn=planner`、人工批准中或 state 未变化都是正常的持久监听态，不是执行阻塞；无论连续多少个 Goal continuation 都不得据此 `update_goal blocked`。Goal 只在 relay `done|cancelled` 时结束，真正无法通过任何 relay 状态变化恢复的协议错误才按 Goal blocked 规则处理。等待期间遵守 `WAITTURN_UX=SILENT_UNTIL_RETURN`，不做短间隔 `show` 轮询。

完成一个动作后，先确认生产 `temp.md` 为空，再写入 [relay-contract.md](references/relay-contract.md) 规定的完整结果，调用：

```powershell
python -X utf8 $relay handoff --root <production_project_root> `
  --role tester --to planner --worker-token <tester_token> `
  --expected-run-id <run_id>
```

只有 Handoff 成功且 `temp.md` 被工具清空、验空后，才回到等待。

## `DEPLOY_AND_BUILD_YAML`

### 1. 请求门

要求消息给出并授权：`source_skill_root`、`production_skill_root`、`production_project_root`、`release_id`、`release_manifest`、部署方式和归档位置。三条路径必须是绝对路径，源与目标不同，当前 cwd 等于生产项目路径。缺失即返回 `PRODUCTION_TEST_PREFLIGHT_REQUIRED`。

### 2. 部署候选

先记录生产目录 `.venv`、`.doctor-pass.json`、`.skill-ready.json`。只复制 manifest 内的候选源码，不从开发机复制虚拟环境、机器凭证、缓存或备份。部署后运行：

```powershell
python -X utf8 "<production-tester>\scripts\release_manifest.py" verify `
  --manifest "<release_manifest>" `
  --destination "<production_skill_root>" `
  --report "<evidence_dir>\deployment-parity.json"
```

严格文件集合与哈希不一致即返回 `DEPLOYMENT_PARITY_FAIL`。没有冻结授权时不得删除目标多余源码。

### 3. 复用生产环境

默认禁止 `setup.ps1 -Force` 和重建已有 `.venv`。`doctor.ps1` 与 `pipeline/production_preflight.py` 未变化时，复用已有 doctor 凭证并运行 `test.ps1` 刷新 `.skill-ready.json`。guard 变化、凭证缺失或校验失败时返回 `DOCTOR_REVALIDATION_REQUIRED`；不得伪造或静默绕过。

### 4. 只生成 YAML

使用新的运行目录，或按冻结授权可恢复归档旧阶段产物。只能读取部署后的 skill 和原始项目资料。完成 extract、compile、verify 与外围复核后，返回：

```text
status: YAML_PENDING_USER_REVIEW
yaml_path: <absolute path>
yaml_sha256: <sha256>
ppt_created: false
word_created: false
```

这不是失败；Handoff planner 后等待 `CONTINUE_PPT`。

## `CONTINUE_PPT`

核对 action 绑定相同 run/release，且 `approved_artifact_sha256` 等于磁盘当前 YAML SHA-256；不一致返回 `YAML_APPROVAL_INVALID`。只生成 PowerPoint，不生成 Word。

运行生产 skill 的结构验证，记录退出码、表格页码、行列数、单元格文字矩阵和产物 SHA-256。结构门通过后返回：

```text
status: PPT_VISUAL_PENDING
ppt_path: <absolute path>
ppt_sha256: <sha256>
structure_result: PASS
word_created: false
```

不得把结构 PASS 表述为视觉 PASS；Handoff planner 后等待 `CONTINUE_WORD`。

## `CONTINUE_WORD`

核对 action 绑定相同 run/release，获批 PowerPoint 哈希等于磁盘当前文件，且 YAML 批准仍有效。使用获批 YAML 生成 Word，执行 Word 结构门，并验证 Word 表格与已批准 PowerPoint/YAML 共用同一显示数据。

全部通过后返回 `PRODUCTION_TEST_PASS`。Word 失败只回传 Word 证据；不得反向修改已批准 YAML/PowerPoint。

## 失败回传

任何失败都写入 `production_project_root/pipeline-progress/production-test/<release_id>/production-test-report.md`，然后通过生产 `temp.md` Handoff planner。报告至少包含：

- `status: REWORK_REQUIRED`；
- 稳定 `failure_key`、失败阶段和未满足 done_when；
- 预期、实际、命令、退出码与证据路径；
- 当前 YAML/PowerPoint/Word 路径及 SHA-256；
- 是否创建后续阶段产物；
- `PRODUCTION_COPY_EDITED: false`。

失败后等待 planner 的新候选。不得直接写开发 `temp.md`，不得修改生产副本继续试错。
