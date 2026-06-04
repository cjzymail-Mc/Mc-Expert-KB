# reference · Claude Code 权限系统（实测事实手册）

> 配 `settings.local.json` 时跨 repo 复用的事实底本。来源：Mc-emoji `feature-02-auto-Enter` 实测 + `CLAUDE.md`。
> 性质 = reference（factual），非 decision/reflex。改 settings 前先读 + 先备份 `.bak`。

## 当前采用：方案 A
`Bash(*)/PowerShell(*)` 通配进 **allow** + `rm/Remove-Item` 进 **ask** 列表。
效果 = "几乎全通 + rm 仍弹确认"。备份在 `settings.local.json.bak`。**不主动开 bypassPermissions**。

## 6 个反直觉但实测确认的事实（改 settings 前必读）

1. **`bypassPermissions` 不支持"挖洞"**——它完全跳过 allow/deny/ask 三类规则，只保留 `rm -rf /` 和 `rm -rf ~` 两个硬编码兜底。想"几乎全跳但 rm 仍弹"**不能**用 bypass，要用方案 A。
2. **`ask` 规则优先级高于 `allow`**——文档没明说但实测验证。方案 A 就靠这个挖洞（allow 通配 + ask 拦 rm）。
3. **settings.json 不热重载**——改完必须**重启会话**才生效。
4. **`defaultMode` 必须放在 `permissions` 内部**，放外面 CC 不识别。
5. **`acceptEdits` 不覆盖所有 Bash/PowerShell**——只覆盖文件编辑 + 少数文件系统命令（mkdir/rm/mv 等）；`git push`/`curl`/`npm run` 这类仍弹确认。
6. **`ask` 是「命令串开头前缀匹配」，包进脚本/循环/管道即绕过（2026-06-02 双文件对照实测确认）**——`ask` 规则（如 `PowerShell(Remove-Item *)`）只匹配**命令串开头**。实测：裸 `Remove-Item <path>`（开头是 `Remove-Item`）→ **弹确认窗**；`$f=@(...); foreach{ Remove-Item $p }`（开头是 `$f =`）→ 命中 `PowerShell(*)` 的 allow → **静默执行、不弹窗**。即方案 A 的 rm 门只拦"裸的顶层删除"，**拦不住埋在脚本/循环/管道里的删除**（同理 `bash -c "...; rm ..."`）。**硬操作纪律：含销毁性删除时用逐条裸命令、别包脚本；多文件删除先停下请用户确认。** 详见 [[../../Mc-emoji 记忆]] feedback_destructive_delete_confirm。

## 详细背景
`Mc-emoji/[feature-02-auto-Enter]/bypass-plan-discussion.md` + `settings-fix-plan.md`（给其他项目 Claude 改 settings 的指令文档）。

相关：[[../reflexes]]（"改 settings 先 .bak / 不开 bypass" 硬反射）、[[../principles]]
