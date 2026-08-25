# Release candidate handoff contract

coder 成功交接必须包含以下字段；缺一项即不构成可交给 tester 的冻结候选：

```text
RELEASE_CANDIDATE_READY=v1
run_id: <development run id>
release_id: <unique id>
source_skill_root: <absolute path>
release_manifest: <absolute path>
source_tree_sha256: <sha256>
doctor_guard_changed: <true|false>
production_copy_written: false
```

随后列出：

- 修改文件与改动目的；
- 开发测试命令、退出码和证据路径；
- 每条 coder-owned done_when 的动态结果；
- 至少一个可靠失败负例；
- 未关闭的 `AUTONOMOUS_DECISIONS / PENDING_HUMAN_NONBLOCKING / OPEN_BLOCKERS`；
- tester 应执行的第一动作固定为 `DEPLOY_AND_BUILD_YAML`。

manifest 必须来自开发母本，不包含 `.venv`、doctor/skill 本机凭证、缓存、备份或历史输出。任何源码变化都使旧 manifest 和旧 release id 失效。
