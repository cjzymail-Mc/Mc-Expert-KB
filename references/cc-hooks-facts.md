# cc-hooks-facts.md — Claude Code hook 机制事实（StopFailure / UserPromptSubmit）

> 性质 = reference（factual），非 decision/reflex。
> **⚠️ 核实日期 2026-07-02 · CLI v2.1.193 · 官方 hooks 文档 + 本机实测。版本敏感、易过期**——CC 若改 hook 事件/退出码语义，回读本卡重评。
> 实现细节（SendKeys 焦点借还 / aiTitle 认窗 / launcher 具体形态）留源 repo，见文末指针。

## StopFailure —— API 错误时唯一触发的 hook，但 observ-only

- **`StopFailure` 是唯一**在「turn 因 API 错误结束」时触发的 hook；`Stop`/`SubagentStop` **不**在 API 错误时触发（别把 Stop 当能接 API 错误的扳机）。
- **observ-only**：stdout 和 exit code 都被官方忽略 → **不能 block、不能注入 continue**。所以「写个 hook 在交互式 TUI 里自动续上」**做不到**——hook 最多告警/记日志/spawn 外部脚本（如 SendKeys 敲 continue 这条缝，非官方注入）。
- **真·自动续只能在 headless**：`claude -p` + `--fallback-model "opus,sonnet,haiku"`（官方限定**仅 `--print`**，主模型 overloaded 时降级、每轮重试主模型）+ 外层 exit-code 重试循环。带写操作的流程禁套自动 continue（撞 [[loops-and-automation]] §7）。
- **matcher 只认 `|` 分隔**（`,` 被当字面量）；错误类型 `overloaded`/`rate_limit`/`server_error`/`unknown` 等共 10 种。
- **换账号躲不了 `overloaded`**（Anthropic 全局容量、跨账号共享一个池）；只对 `rate_limit`（单账号配额）有效。
- 红字 `API Error`/`529` = 内置重试在跑（turn 没结束，StopFailure 不该触发）；黄字 `Connection closed mid-response` = 重试耗尽的真中断（实测会触发）；黄字截断**不保证**触发（那轮未必以 API 错误结束）。

## UserPromptSubmit —— exit-2 是全局变砖 landmine

- **exit 2 = 阻断并擦除该 prompt**（官方退出码表）。而 `python 不存在.py` 的退出码**恰好是 2**。两者一撞：注册命令若直接指向一个**可能移动/删除的脚本**（feature 仓里的高流动脚本），脚本一丢 → `3 账号 × 所有 repo × 每条 prompt` 全被阻断擦除 = **全局变砖**。
- **防砖正解 = launcher 模式**：在**中央稳定层**（`~/.claude/hooks/`，与 stopfailure/guard-delete 同稳定性等级）放一个 <15 行、纯 stdlib、**永不编辑**的 launcher，`runpy.run_path(高流动脚本, "__main__")` 现读现跑（保住「改脚本即时生效」+ 单解释器），顶层 try/except（含 SystemExit）**恒 exit 0**。高流动脚本丢 → launcher `os.path.exists` 假 → 静默 no-op exit 0 = 可接受的「断链」降级、非砖。（更强兜底靠 shell 短路 `python "..." || exit 0`，但用前必实测本机 CC 实际用哪个 shell、fallback 是否 PowerShell 5.1 不支持 `||`。）
- **stdout 必须恒空**：UserPromptSubmit 且 exit 0 时，hook 的 stdout 会被 CC 当 **additionalContext 注入进用户 prompt** → 捕获/观测型 hook 里**任何 print 都不许**（会污染用户输入），诊断只写独立日志文件。这是「捕获型 hook」区别于「阻断型 hook」的硬约束。
- 真实 stdin 字段 = `prompt`（非 `user_message`）；别猜字段名，写 probe-once 落盘坐实。顶层 try/except 全吞 + exit 0 只兜「脚本跑起来之后」，**兜不住「脚本根本没启动」**（那层靠上面的 launcher/短路）。

## PreToolUse / 权限决策类 hook —— 拦截语义（2026-07-03 官方文档核实）

> ⚠️ 核实 2026-07-03 · 官方 hooks 文档 + 本机实测。与上面两个具体 hook 不同轴：这是**权限拦截通用语义**（配 [[cc-permissions]] 一起读）。

- **hook 的 deny 连 `bypassPermissions` 都拦得住**；hook **只能收紧不能放松**（hook 的 allow 不越过 settings 的 deny/ask）。多 hook 合并**取最严**：`deny` > `defer` > `ask` > `allow`。
- **平台 fail-open**：hook exit 1 / 超时 → **照样放行**。强制拦截必须自己 `exit 2` 或返回 `permissionDecision:"ask"/"deny"`。**注意与 StopFailure 的 observ-only 相反**：PreToolUse 的 exit code / JSON **有决策权**，别把两类 hook 的退出码语义混为一谈。
- **覆写守卫范式**（官方 `protect-files.sh`）：PreToolUse `matcher:"Edit|Write"` + 读 `tool_input.file_path` + 保护清单命中 → `permissionDecision:"ask"`；路径先**规范化**（`GetFullPath` 还原 `..`）再比对——官方示例的子串匹配不处理 `..` 穿越，自己补。护 settings/hook 自身社区通行 = deny 规则 + PreToolUse 路径清单**双层**（都非铁墙，最硬是容器只读挂载、Windows 不可用）。

## 通用反射（本卡两半共用）

- **settings 改注册不热重载，但脚本文件内容即时生效**：改 `settings.json` 的 hook 注册命令行要重启会话；改脚本 `.py`/`.ps1` 逻辑不用重启（每次 fire 重读文件）。
- 铺任何「每 prompt/每 turn 触发的全局 hook」前，**先确认「注册命令在其指向物缺失时 CC 看到的退出码」**；exit-2 类事件（UserPromptSubmit 等）尤其致命。
- 呼应 [[../reflexes]]「先查再下结论」：外部 AI/「专家建议」常错说「StopFailure hook 能自动发 continue」——把「hook 能跑脚本」误当「hook 能续会话」，遇到直接纠。

## 原档指针

- StopFailure 认窗/焦点借还/闪窗重试等**实现演进**：`Mc-emoji/.claude/auto-memory/{cc-stopfailure-hook-observ-only,stopfailure-hook-fix}.md` + `[feature-03-take-a-nap]/2026-06-23 API-Error-自动恢复-方案.md`（Tier 0/1/2 分层）；hook 母本 = 本 repo `.claude/hooks/stopfailure-autocontinue.ps1`。
- UserPromptSubmit 捕获口工程坑全景：`Mc-emoji/.claude/auto-memory/cc-userpromptsubmit-hook-pitfalls.md` + `[feature-05-loop-self-improvement]/plan04-hook兜底核实与铺开.md`；launcher 母本 = 本 repo `.claude/hooks/capture_launcher.py`。
- PreToolUse 权限决策类 hook（guard-delete L3 + 覆写守卫）实现：`Mc-emoji/[feature-02-auto-Enter]/plan-权限守卫升级-2026-07-03.md`；hook 母本 = 本 repo `.claude/hooks/{guard-delete,guard-overwrite}.ps1`（四闸/正则表/reparse 检查等实现细节留源，本卡只收官方机制语义）。

相关：[[../reflexes]]（先查再下结论）、[[loops-and-automation]]（含写操作的 loop 不无人值守）、[[cc-permissions]]
