一键配置 3 账号 auto-memory NTFS junction 同步：

执行 `python "skills/[memory-junction-for-3-account]/memory_junction_one_shot.py"`（带 `PYTHONIOENCODING=utf-8` 避免乱码；路径含方括号必须加引号防 shell 通配解析），把脚本输出原样反馈给用户。脚本会自动跑 4 个阶段：

- Phase A：union merge（合并 N 账号现有 memory 到 `.claude/auto-memory/`）
- Phase B：从已有该项目的账户复制 `projects/<name>/` 到缺失账户（跳过 memory junction）
- Phase C：setup --apply（建 junction）
- Phase D：verify（端到端测试）

若 verify 通过则全自动完成；不通过则把失败原因清楚汇报给用户。

最后脚本会输出 Phase E 手工验证指引（3 步：在 `.claude/auto-memory/` 写 `_check.md` → 检查 3 个账户路径都看到 → 删除后 3 处都消失）。**不要替用户跑这一步**——按用户要求保留给他们手工执行。把指引中的具体路径列给用户即可。

注意：脚本是幂等的，重复跑不会破坏已有状态（已合并的会跳过 union；已是 junction 的会跳过 setup）。
