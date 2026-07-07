# reference · Claude Code 权限系统（实测事实手册）

> 配 `settings.local.json` 时跨 repo 复用的事实底本。来源：Mc-emoji `feature-02-auto-Enter` 实测 + `CLAUDE.md`。
> 性质 = reference（factual），非 decision/reflex。改 settings 前先读 + 先备份 `.bak`。

## 当前采用：方案 A
`Bash(*)/PowerShell(*)` 通配进 **allow** + `rm/Remove-Item` 进 **ask** 列表。
效果 = "几乎全通 + rm 仍弹确认"。备份在 `settings.local.json.bak`。**不主动开 bypassPermissions**。

## 6 个反直觉但实测确认的事实（改 settings 前必读）

1. **`bypassPermissions` 不支持"挖洞"**——它完全跳过 allow/deny/ask 三类规则，只保留 `rm -rf /` 和 `rm -rf ~` 两个硬编码兜底。想"几乎全跳但 rm 仍弹"**不能**用 bypass，要用方案 A。
2. **规则顺序 = `deny` → `ask` → `allow`（`ask` 优先级高于 `allow`）**——**2026-07-03 官方权限文档已明文确认**（原为"文档没明说但实测验证"，现升级为官方白纸黑字）。方案 A 就靠这个挖洞（allow 通配 + ask 拦 rm）。
3. **settings.json 不热重载**——改完必须**重启会话**才生效。
4. **`defaultMode` 必须放在 `permissions` 内部**，放外面 CC 不识别。
5. **`acceptEdits` 不覆盖所有 Bash/PowerShell**——只覆盖文件编辑 + 少数文件系统命令（mkdir/rm/mv 等）；`git push`/`curl`/`npm run` 这类仍弹确认。
6. **`ask` 是「命令串开头前缀匹配」，包进脚本/循环/管道即绕过（2026-06-02 双文件对照实测确认）**——`ask` 规则（如 `PowerShell(Remove-Item *)`）只匹配**命令串开头**。实测：裸 `Remove-Item <path>`（开头是 `Remove-Item`）→ **弹确认窗**；`$f=@(...); foreach{ Remove-Item $p }`（开头是 `$f =`）→ 命中 `PowerShell(*)` 的 allow → **静默执行、不弹窗**。即方案 A 的 rm 门只拦"裸的顶层删除"，**拦不住埋在脚本/循环/管道里的删除**（同理 `bash -c "...; rm ..."`）。**硬操作纪律：含销毁性删除时用逐条裸命令、别包脚本；多文件删除先停下请用户确认。** 详见 [[../../Mc-emoji 记忆]] feedback_destructive_delete_confirm。

## 2026-07-03 官方文档核实补强（3 subagent 核官方 permissions/hooks 文档 + 社区实战 + 本机实测）

> ⚠️ 核实 2026-07-03 · 官方权限文档 + 本机 CLI v2.1.159 实测。**版本敏感、易过期**——CC 若改权限模式/受保护路径语义，回读重评。

- **Windows 原生不支持沙箱**（官方原文 "Native Windows is not supported"，仅 macOS/Linux/WSL2）→ 官方"少弹窗+防删除"的沙箱正解在本机堵死，**方案 A + hook 是 Windows 原生唯一可行路线，不是权宜之计**（承重上面"方案 A"定位）。
- **内置「受保护路径」机制**：`.git`/`.claude`/`.vscode`/shell 配置等在除 `bypass` 外所有模式**不被 allow 规则自动放行**——免配置的第二层保险。**但本机 V1 实测：user-scope `~/.claude` 写入未被覆盖**（Write `.claude/hooks/*.ps1` 静默通过）→ 别以为受保护路径全包了，护 settings/hook 自身仍要自建覆写守卫（见 [[cc-hooks-facts]]）。
- **模式辨别（补充/收紧事实 #5）**：`dontAsk` = 未预批准的**静默拒绝**（非弹窗，不适合挖洞）；`auto`（v2.1.83+ 研究预览，分类器拦 `git reset --hard`/`git clean -fd`）方向对但官方自认 **17% 假阴性**、非人审替代 → 观望不采用；`acceptEdits` 会**自动放行工作目录内 Remove-Item**（比事实 #5 更松）→ 继续不用。
- **黑名单必被绕已被 CVE 坐实**（Flatt CVE-2025-66032、Adversa 50 子命令绕过，均已在近版修复）→ 共识：别靠 pattern 卡参数，靠 hook 做 AST 解析 + 分层防御。守卫守「防误操作」不守「故意混淆」是**正确边界**（追后者 = 无底洞）。

原档：`Mc-emoji/[feature-02-auto-Enter]/plan-权限守卫升级-2026-07-03.md`（3 subagent 调研全汇总 + guard-delete L3 四闸实现；实现细节留源 repo）。

## 详细背景
`Mc-emoji/[feature-02-auto-Enter]/bypass-plan-discussion.md` + `settings-fix-plan.md`（给其他项目 Claude 改 settings 的指令文档）。

相关：[[../reflexes]]（"改 settings 先 .bak / 不开 bypass" 硬反射）、[[../principles]]
