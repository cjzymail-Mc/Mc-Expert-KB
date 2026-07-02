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
