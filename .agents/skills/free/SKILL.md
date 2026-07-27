---
name: free
description: "[Codex adapter] 显式 $free 深度授权入口：直读 Claude free 母本，按 repo 共同 runtime binding 使用 native mc-expert、auto_review 边界与 $mc-update→(pin 提案)→$session-new exactly-once 收尾（pin 段产提案+人工门、不调 $pin skill）。仅手工触发。"
---

# $free（Codex adapter）

## 第一步：读共同 binding 与母本

先完整读取 `$env:USERPROFILE/.agents/skills/_mc-common/codex-runtime-bindings.md`，再执行：

```powershell
pwsh -NoProfile -File (Join-Path (Join-Path $env:USERPROFILE '.agents\skills\_mc-common') 'resolve-master.ps1') -SkillName free -Cat
```

任一步失败即按共同 binding fail-loud；不使用硬编码母本绝对路径，不复制母本正文。

## 第二步：执行 free 语义

把母本的通用流程映射到 Codex：

1. `$free` 是用户对当前任务的显式全托管授权，但不扩大 sandbox、网络、工作区或四红线。
2. 母本 `Task(mc-expert)` 按共同 binding 做当前 turn native tool-surface preflight。可用时 spawn 一个只读 reviewer；不可用时 `BLOCKED_TOOL_UNAVAILABLE`，不得用 `codex exec` fallback。
3. 权限请求由 `auto_review` 与 adapter 后置清单双保险处理。无人值守中不主动发起销毁、敏感目录、对外交付等会卡用户的动作。
4. Claude `AskUserQuestion` 映射为人工门；Claude Agent Teams 无同形等价，若任务必须团队拓扑则停人工门。
5. 完成当前阶段后按共同 binding 恰好一次执行 `$mc-update → (pin 提案) → $session-new`；pin 段产结构化提案清单交接给 session-new plan（不调 `$pin` skill、不自动落账），等人工门批量落账；不再提示用户手工补跑 mc-update/session-new。

## 汇报

汇报完成项、待人工项、自主裁决和 finalizer 三段是否执行；不得写“Codex 无 subagent”、营销数字或“深度授权完全等价”。

## 边界

- 只手工 `$free` 触发。
- 不改外部 Claude 母本、全局 Codex config、hook 或正式 memory。
- 同一任务若已经由 `$today`/`$today-loop` 拥有 finalizer，本 skill 不再启动第二次收尾。

