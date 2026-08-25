# Production tester relay contract

## 1. Repo 与文件所有权

| 路径 | 写入者 | 用途 |
|---|---|---|
| 开发 repo `temp.md` | planner/coder | 开发实现与返工 |
| 生产项目 repo `temp.md` | planner/tester | 生产阶段命令与结果 |
| 生产 skill 副本 | tester，仅部署时 | 冻结候选副本 |
| `.triple-tester-state.json` | `tester-relay.py` | turn、seq、run、hash |
| `.triple-tester-message.md` | `tester-relay.py` | 已固化的当前消息 |

planner 是唯一跨两个 repo 的角色。模型不得直接修改两个 relay 隐藏文件。

## 2. 通用消息头

每份消息首行固定为 `TRIPLE_TEST_RELAY=v1`，至少包含：

```text
run_id: <development run id>
relay_seq: <integer>
release_id: <immutable candidate id>
action: <DEPLOY_AND_BUILD_YAML|CONTINUE_PPT|CONTINUE_WORD|RESULT>
source_manifest_sha256: <sha256 or N/A>
approved_artifact_sha256: <sha256 or N/A>
```

首次请求还必须给出开发母本、生产副本、生产项目、manifest、授权部署方式和证据目录的绝对路径。tester 不接受 Golden 路径。

## 3. Planner 请求

### 首次或返工候选

```text
TRIPLE_TEST_RELAY=v1
run_id: <id>
relay_seq: <n>
release_id: <new id>
action: DEPLOY_AND_BUILD_YAML
source_manifest_sha256: <sha256>
approved_artifact_sha256: N/A
source_skill_root: <absolute path>
production_skill_root: <absolute path>
production_project_root: <absolute path>
release_manifest: <absolute path>
deployment_authority: <exact allowed sync/archive action>
evidence_dir: <absolute path>
```

### YAML 批准后

```text
action: CONTINUE_PPT
approved_artifact_kind: YAML
approved_artifact_path: <absolute path>
approved_artifact_sha256: <sha256>
```

### PowerPoint 批准后

```text
action: CONTINUE_WORD
approved_artifact_kind: PPTX
approved_artifact_path: <absolute path>
approved_artifact_sha256: <sha256>
```

批准只绑定当前哈希；文件变化后立即失效。

## 4. Tester 结果

所有结果使用 `action: RESULT`，并包含：

```text
status: <YAML_PENDING_USER_REVIEW|PPT_VISUAL_PENDING|PRODUCTION_TEST_PASS|REWORK_REQUIRED>
stage: <DEPLOY|ENV|YAML|PPT|WORD>
artifact_path: <absolute path or N/A>
artifact_sha256: <sha256 or N/A>
verifier_command: <command>
verifier_exit: <integer or N/A>
verifier_result: <PASS|FAIL|BLOCKED>
production_copy_edited: false
```

失败再追加 `failure_key / expected / actual / unmet_done_when / evidence_paths / next_planner_action`。pending 再追加 `forbidden_next_artifacts_created: false`。

## 5. 防污染与完成门

tester 不得读取人工修订 PowerPoint、开发调试记录、历史正确 YAML、旧 PowerPoint/Word 或 planner 的目标答案。开发 coder 可从 Golden 抽象通用规则，但客户专属答案不得写入通用 skill。

只有部署清单一致、环境门通过、YAML 批准哈希有效、PowerPoint 结构门与人工视觉批准有效、Word 结构门与共享显示数据通过、生产副本未现场修改时，才允许返回 `PRODUCTION_TEST_PASS`。
