---
name: temp-command
description: "[Codex adapter] 手工 temp 接力模式。用户手工触发 $temp-command 时，硬读取 Claude temp-command 母本并执行同一套读取、立即清空、验空、继续工作和写回交接流程。"
---

# $temp-command（Codex adapter）

这是 Claude `/temp-command` 的 Codex 通用入口。业务流程只维护在 Claude 母本，本文件不复制第二份规则。

## 第一步：读取母本（硬执行，禁止跳过）

```powershell
pwsh -NoProfile -File (Join-Path (Join-Path $env:USERPROFILE '.agents\skills\_mc-common') 'resolve-master.ps1') -SkillName temp-command -Cat
```

定位或读取失败时立即停止并报告 `MASTER_NOT_FOUND`，禁止凭记忆重建流程。

## 第二步：执行母本

完整遵守母本的顺序与边界。Codex 中的手工入口是 `$temp-command`；Claude 入口是 `/temp-command`，两端名称保持一致。

## 边界

- `allow_implicit_invocation: false`：仅用户手工触发 `$temp-command` 时执行。
- 不把单次接力擅自升级为 Goal、loop、后台 Monitor 或双 session 自动编排。
