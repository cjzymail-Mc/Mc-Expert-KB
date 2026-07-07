# hooks 待修 backlog（攒批一起修，勿单独动线上脚本）

> 用途：记录 `~/.claude/hooks/` 下各 hook 已诊断、暂不修的 bug，下次升级 hook 时一并处理。
> 纪律：每条带【现象 / 根因 / 证据 / 修法 / 状态】，让修的时候不必重新排查。

---

## #1 · stopfailure-autocontinue.ps1 — 偶发 ENTER 丢失，continue 卡输入框未提交 ✅已修

- **登记日期**：2026-06-30
- **现象**：StopFailure 触发后，`continue` 文字进了输入框但**未提交**（截图 `>continue ` 单行、无换行 = ENTER 被整个丢弃，非被当框内换行）。**偶发**，多发生在从「超大/超时响应」恢复时（实例：`Baked for 4m 2s` 后 `API Error: Connection closed mid-response`）。
- **根因**：line 193 `SendKeys::SendWait("continue{ENTER}")` 把文字+回车**一坨快速派发**；line 185 的 250ms settle 在 TUI 正拆解/重渲那条被截断的巨型响应时**不够**——`continue` 字符进了缓冲并渲染，尾随的 `{ENTER}` keydown 落在窗口死区被吞。空闲就绪态下不复现（同日 16:10/16:14/16:29 等 SENT 均跑通）。
- **证据**：
  - `claude-stopfailure-probe.log` 2026-06-30 10:06:46 记 `action=SENT(continue·借还)`，但实际未提交 → **`SENT` 是假成功**：脚本只要 `SendWait` 不抛异常就记 SENT，**从不校验 prompt 是否真提交**。
  - 该条 `F==T==1312360`（本会话窗口本就在前台）→ **排除焦点/借还因素**，纯 ENTER 时序竞态。
- **修法（建议，未实施）**：拆分文字与回车 + 加 settle + 兜底二次 ENTER（只动 line 185 + 193，不碰焦点借还四道安全门）：
  ```powershell
  # line 185：settle 250 → 450（超大响应拆解慢，多给就绪时间）
  Start-Sleep -Milliseconds 450
  # line 193：一坨发 → 拆开 + 兜底
  [System.Windows.Forms.SendKeys]::SendWait("continue")
  Start-Sleep -Milliseconds 150
  [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
  Start-Sleep -Milliseconds 150
  [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")   # 兜底：已提交则空框多敲 Enter 无害；漏提交则补上
  ```
  原理：让 `{ENTER}` 成独立离散按键，即便文字被当 paste 批处理，150ms 后那记单独 Enter 也能被 submit handler 捕获；末尾再补一记空框 Enter 防漏。
- **可选加固**：把 `action=SENT` 改成发完后**回读 transcript 尾**确认产生了新 user turn 再记 SENT，否则记 `SENT?(未确认提交)`——让日志不再假成功。（成本higher，按需。）
- **状态**：✅ 已修 · 2026-06-30。
- **实施记录（2026-06-30）**：本会话（cwd=Hot-Fix, session=af021bfa）复现同一症状（截图 `> continue` 未提交），日志 `2026-06-30 13:44:17 action=SENT(continue·借还) F==T==460942`，再次印证「SENT 假成功 + F==T 纯 ENTER 时序竞态」。已按本条修法落地，改母本 `Mc-Expert-repo/.claude/hooks/stopfailure-autocontinue.ps1`（符号链接，`.claude-mc`/`.claude-xh` 一次改三账号生效；`.claude-glm` 不注册）：
  - line 185 settle `250 → 450ms`（超大/超时响应拆解慢，多给就绪时间）。
  - 敲键处由 `SendWait("continue{ENTER}")` 一坨发 → 拆成：先 `SendWait("continue")` → `Start-Sleep 200ms`（等字符渲进输入框）→ 复核 `GetForegroundWindow()==target` 仍在本会话窗口 → `SendWait("{ENTER}")` → `Start-Sleep 150ms` → 再补一记 `SendWait("{ENTER}")` 兜底（已提交则空框多敲无害，漏提交则补上）。
  - 四道安全门 / 焦点借还逻辑未动；`ParseFile` 语法校验 PASS。
- **遗留（未做，按需再开新条）**：本条「可选加固」——发完回读 transcript 尾确认产生新 user turn 再记 `SENT`，否则记 `SENT?(未确认提交)`，根治日志假成功。当前仍是「发了即记 SENT」，故日志 SENT 不等于真提交，排查后续 ENTER 类问题时勿轻信 SENT。

---

## #2 · stopfailure-autocontinue.ps1 — 借焦点被前台锁拒时直接放弃，救不了「用户正操作别窗口」的会话 ✅已修

- **登记日期**：2026-06-30
- **现象**：StopFailure 触发、认窗成功（aiTitle 唯一命中本会话窗口 T），但 `continue` 没敲、窗口也没激活。
- **根因**：`Focus()` 里的 `SetForegroundWindow(t)` 受 **Windows 前台锁**限制——当用户正主动操作别的窗口时，`AttachThreadInput` 那套也抢不过前台 → 借焦点失败。v3 此时只「还原 F + 放弃」，无任何提醒，用户全程不知道有会话卡住了。
- **证据**：本会话 session=120f5cfe（cwd=Mc-emoji）连续两次 `skip(借焦点未命中本会话窗口·已还原)`：`15:30:21 F=5703336('陈晶(XY24)') mid=5703336`（用户在微信）、`15:37:13 F=17041182(VS Code) mid=17041182`（用户在 VS Code）。两次 **`F==mid`** = `SetForegroundWindow` 完全没生效、前台压根没动 → 纯前台锁拒绝，非认窗/借还逻辑错。
- **修法（v3.1，已实施）**：第一次借失败 → `FlashWindowEx(FLASHW_ALL|FLASHW_TIMERNOFG)` 闪任务栏（持续闪到窗口被切前台才停）吸引用户停手 → `Start-Sleep 5000` → **重试借焦点仅 1 次** → 命中则停闪+正常敲键（SENT 行加 `·重试1次`）；仍不中则还原 F + 放弃但**留闪烁**作人工提醒（用户点开窗口=切前台→闪自动停，看到 `>` 空框手敲）。
  - 双管原理：① 闪烁提醒用户；② Windows 前台锁在「前台进程一段时间没收到用户输入」后才放行 → 用户一停手，重试的 `SetForegroundWindow` 就能成功（不一定非要点窗口）。
  - 配套：新增 `Flash()` P/Invoke（`FLASHWINFO` 结构 + `FlashWindowEx`）；单飞锁等待 `8s → 12s` 覆盖「闪+5s+重试」整周期，防并发会话在别人重试窗口内误超时。
  - 失败日志改 `skip(借焦点重试1次后仍未命中·已还原·留闪烁待人工)`。四道安全门其余逻辑未动；`ParseFile` 语法校验 + `Add-Type` C# 编译 PASS。
- **状态**：✅ 已修 · 2026-06-30。改 `~/.claude/hooks/stopfailure-autocontinue.ps1`（junction → `Mc-Expert-repo/.claude/hooks/`，一次改 `.claude-mc`/`.claude-xh` 两账号生效；`.claude-glm` 不注册）+ 同步 Mc-emoji skill 夹副本。settings 命令行未变、脚本每次 fire 重读 → **即时生效不用重启**。
- **遗留**：沿用 #1 的「SENT 假成功」局限不变（v3.1 没动校验逻辑）。另：「最终失败后一直闪到用户点窗口」是默认取舍，若嫌烦可改 `FLASHW_ALL` 定次数自动停。

---

## #3 · stopfailure-autocontinue.ps1 — slash-command 开局的无人值守会话无 aiTitle → 认窗门永久 skip，救不回 🔴未修

- **登记日期**：2026-07-03（用户指示：先查明记录、暂不改代码）
- **现象**：/today 全托管会话（session=76f35441，cfg=.claude-mc，cwd=Mc-emoji）跑批途中黄字真中断（`API Error: Connection closed mid-response`），hook **FIRED 了**但 `action=skip(transcript无aiTitle·暂无法认窗)`——continue 没敲、**也没有任何闪烁提醒**（skip 发生在借焦点/闪烁逻辑之前，用户零感知）。用户完全离席，会话干等 9 分钟（Churned for 9m 0s）直到人回来手动interrupt。同日上午 10:27/10:36/10:44 另有 3 次同款 skip（其中 10:36/10:44 两次 `cfg=` 空、transcript 不在常规项目路径，疑为 headless/schtasks 探针会话——无窗可敲，skip 反而正确；10:27 那次待考）。
- **根因**：CC 的 ai-title 生成器**只在用户发自然语言消息后才产标题**。本会话开局是 `/today`（command-message）→ AskUserQuestion 选项应答（tool result）→ 之后全程自主跑批，**无一条自然语言 prompt** → transcript 里 0 行 aiTitle、窗口标题一直是默认「Claude Code」。hook 第④道认窗门**唯一依赖 aiTitle**（v2 起废弃了旧的默认题匹配）→ 读空 → 按安全设计放弃。
  **结构性盲区：slash-command 开局 + 无人值守（/today 全托管、将来乙-2 定时 /reflect）= 最需要自动续的会话类型，恰好整类落在认窗门外。**
- **证据**（复核路径）：
  - `%USERPROFILE%\claude-stopfailure-probe.log`：`2026-07-03 14:47:46 FIRED session=76f35441 action=skip(transcript无aiTitle·暂无法认窗) aiTitle=''`。
  - 事发截图：窗口标题「※ Claude Code」（默认题非对话摘要），与「渲染器从未设过 aiTitle」互证。
  - transcript 复核（邻行时间戳定位，非猜测）：aiTitle 行（`type=ai-title`）共 4 行，行号 133/154/164/179，**全部位于 07:03:22Z（=本地 15:03）之后**——即用户回来发第一条自然语言之后才生成；14:47:46 fire 时刻 0 行。hook 读空 = 忠实读取，**排除解析 bug**。
  - 生成时点旁证：aiTitle 内容 =「调查hook没有生效的原因」= 恰是用户事后那条消息的主题。
- **修法（建议，未实施；下次升级 hook 时一并处理）**：
  - 首选：认窗门加 fallback——aiTitle 为空时，若「标准化标题 == 'Claude Code'（默认题）」的可见窗口**恰好唯一**，视为本会话窗口，照常走借还+敲键；0 个或 ≥2 个照旧 skip（**保持「唯一命中才动手」安全边界**，多开撞默认题时安全放弃）。单会话无人值守（最常见场景）即被覆盖。日志标 `·默认题fallback` 以便区分。
  - 不建议走 PID 链认窗：ConPTY/WindowsTerminal 宿主进程链断裂，`GetConsoleWindow` 返 0 已在 v1 实证。
- **附带发现**：transcript 里 aiTitle 值自带 mojibake 尾巴（截断 UTF-8 → lone surrogate，「原�」）。hook 认窗用 `-eq` 精确比对，若渲染器设窗口标题时对同一串做了不同截断/清洗，可能出现「有 aiTitle 也对不上」的次生失配——修 #3 时顺手核一眼（现 Normalize-Title 只去前缀符号，没处理坏字符）。
- **状态**：🔴 未修 · 仅登记（2026-07-03）。

---

## #4 · guard-delete.ps1 — 命令文本含字面删除词（grep 搜索词/注释/pin 文本）即误弹 ask，误打扰明显 🔴未修

- **登记日期**：2026-07-04（用户指示：记 backlog、新 session 想办法修）
- **现象**：`guard-delete.ps1` 对**根本没有真实删除**的 Bash 命令也强制弹 `ask`——只要命令串文本里出现 `rm`/`del`/`rd` 等删除词的**字面**（如 `grep -c "rm"` 的搜索词、`echo "含 rm"` 的注释标签、pin 命令 `--note "...rm/删除类..."` 的文本）。2026-07-04 plan10 会话里，因 forensic 主题正好是一条 **rm** 事件、多条命令含字面 rm → 连弹多次，打断 /free「全程无打扰」，用户明确不满。
- **根因**：L3 的**回退全文正则路径**过粗。命令走 PowerShell AST 解析：**bash 语法命令（`for/do/done`、heredoc、`\` 续行、部分重定向）让 AST 解析失败**（`$errors.Count>0`）→ 落 `$fallbackPatterns` 全文正则（含 `'\brm\b'`/`'\bdel\b'`/`'\brd\b'`）→ 对**整条命令字符串**裸匹配，不区分"删除动词在命令位置"还是"只是引号里的搜索词/注释"。AST 解析**成功**的干净命令不受影响（走结构化路径、只在命令名/包装参数处判）。属注释里「误判只朝『多弹』掉」的 fail-safe 代价，但对"搜索/处理删除相关文本"这类正常工作误伤突出。
- **证据**（喂命令给 hook 实测，2026-07-04）：
  - STEP1 `for p in "rm" ...; do grep -c "$p" ...; done`（bash 语法 + 字面 rm）→ 返回 `permissionDecision:ask`，reason 原文「命令含删除/破坏动作(AST 解析失败，全文正则兜底匹配 /\brm\b/)，强制确认。」——**证实走 fallback 且匹配裸 rm**。
  - STEP2 `cat CLAUDE.md | head -2`（无删除词）→ 空输出=放行。
  - STEP3 `python pin_capture.py --note "harness 只对 rm/删除类硬编码弹窗兜底"`（干净 PS 语法 + 引号内 rm）→ **不弹**：AST 解析成功走结构化路径，`python` 包装只扫 `rmtree/os.remove/...` 不扫裸 rm → arg 里的 rm 不命中。三条对照直接定位「AST 失败 fallback + 裸 rm 正则」是误触发源。
  - 旁证：本会话用来「测试 rm 会不会弹窗」的命令，因 echo 标签写了「含字面 rm」三字被自身弹窗、用户手动拒绝——即注释里的 rm 也触发。
- **修法（建议，未实施；保持『真删除仍拦』不放松）**：AST 解析失败时别对**整条原始字符串**裸跑删除正则，择一或组合——
  1. **剥字符串字面量再匹配**：先用轻量分词把引号内内容（grep pattern / 注释 / --note 文本）摘出、只对"命令位置 token"跑删除词正则（grep 搜索词、echo/printf/pin 文本多在引号内，剥掉即消大部分误报）；
  2. **纯读命令白名单**：`grep/rg/cat/head/tail/echo/printf/less/awk/sed(无 -i)` 等确定不删的命令，即便参数含删除词也放行（但注意 `sed -i`/`xargs` 等要排除）；
  3. **改进 bash 解析**：AST 失败时改用一个 bash-aware 的轻量 tokenizer（而非 PowerShell AST）判命令位置，从根上对齐结构化路径的判据。
  - ⚠️ 边界：别过度放宽到「引号包裹的真删除」能绕过（如 `bash -c "rm x"`）——包装命令内嵌删除仍要抓（现 `wrapperPatterns` 已覆盖 sh/bash/xargs，改分词时别把这层丢了）。
- **对工作方式的即时缓解（已入 memory `guard-delete-hook-pops-on-literal-rm`）**：搜索/读取优先用原生 Grep/Read/Glob 工具（hook matcher 只含 `Bash|PowerShell`，原生工具不触发），少用 Bash `grep/cat`——尤其搜索词含删除词时。
- **状态**：✅ 已修 · 2026-07-04（L3.1）。
- **实施记录（2026-07-04）**：按修法 ①+③ 组合落地（②纯读白名单未做——被 ①+③ 吸收，单独维护 sed -i/xargs 例外性价比低）。改母本 `Mc-Expert-repo/.claude/hooks/guard-delete.ps1`（`~/.claude/hooks` 是 Junction，三账号一次生效；脚本每次 fire 重读→即时生效不用重启）+ 同步 Mc-emoji skill 夹副本（hash 核验一致）。备份 `guard-delete.ps1.bak-20260704`。
  - AST 失败分支改为：`Get-StrippedCommand` 剥引号字面量（`'...'`/`"..."` 含 `\"` 转义，未闭合吞到尾）→ 按 `; & | ( ) { } `` 换行` 切段 → 每段跳过控制关键字（do/then/for/sudo/…）/`VAR=x` 前缀/游离 flag 取**命令位置 token**（剥路径+`.exe`）→ 只对该 token 判 `$deleteVerbs`；命中包装命令（bash/sh/xargs/python/…）时**连引号内容一起**对原始全文跑 `wrapperPatterns`（守住 ⚠️ 边界）；git 段对剥引号文本跑 `gitPatterns`；另对剥引号全文补扫 `.NET Delete / rmtree / find -delete`。分词自身抛错 → catch 回落旧全文裸正则（误判仍只朝"多弹"掉）。
  - 实测 7 探针全过：阴性③（STEP1 同款 for+grep 引号 rm/del/rd、for+echo **未引号**裸 rm 标签、STEP3 同款 pin --note 引号 rm）全放行；阳性④（for 循环内真 `rm "$f"`、`bash -c "rm $f"` 内嵌、裸 `Remove-Item -Recurse`（结构化路径回归）、for 循环内 `git reset --hard`）全弹 ask——阳性对照过关，非假阴性。
- **遗留（已知取舍，按需再开新条）**：① 包装命令在场时对**原始全文**扫删除词——`bash -c "echo hi"` 同串里别处引号内恰有 rm 时会多弹（宁多弹不漏拦）；② heredoc 正文不剥——正文里行首恰为 `rm xxx` 形态仍会误弹（罕见，同向 fail-safe）；③ 兜底路径的删除动词**不走临时目录白名单放行**（bash 语法无 AST、静态判不了路径字面量）。
