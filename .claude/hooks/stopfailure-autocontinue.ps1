# stopfailure-autocontinue.ps1 — StopFailure 触发 → SendKeys 敲 continue 自动续接（母本）
#
# 作用：Claude Code 交互式 TUI 里，任务被 API error 真中断（黄字 Connection closed mid-response，
#       10 次内置重试耗尽）后，不用人工手敲 continue —— 由本 hook 帮你敲。
#
# 前提事实（别走回头路）：
#   · StopFailure 是 observ-only（stdout/exit code 被忽略，hook 自身不能注入 continue）；
#     能注入的唯一手段是「外部敲键」SendKeys。本脚本即走这条缝。
#   · 红字 API Error / 529 ＝ 内置重试在跑（retrying x/10），turn 没结束 → 本 hook 不该被触发、也不该插手。
#     只有黄字真中断（重试耗尽）才触发 StopFailure → 唯一介入点。
#
# 【定位 · 2026-06-29 v3 改：默认「焦点借还」】v1/v2 是「只敲前台窗口」的省手敲便利工具；
#   用户实测借还稳定（借到/还回 6/6+3/3、离开约 510ms、零泄漏）后拍板：API error 频率低且多在
#   无人值守时出现，接受借焦点 ~0.5s 的干扰，换「能自动救后台报错会话」。故 v3 默认借焦点。
#   仍守的安全边界：① 只对「aiTitle 唯一命中」的本会话窗口动手（撞名/认不出只记日志、不乱敲）；
#   ② 借完复核 fg==T 才敲、敲完 drain 再还（防 continue 泄漏进别的窗口）；
#   ③ 全局单飞锁串行化借还（防多会话同时报错时两实例抢焦点打架）；④ 借完务必把焦点还回原窗口。
#
# 四道安全门（全过才敲键）：
#   ① 账号门：glm（CLAUDE_CONFIG_DIR 叶名 = .claude-glm）不是原生 Anthropic 账号 → 只记日志不敲键。
#             （deploy 脚本默认也不往 glm 注册；本门是脚本层双保险。）
#   ② 错误类型门：仅瞬时错误（连接中断/overloaded/server_error/unknown/rate_limit）才续；
#                 auth/billing/invalid_request/model_not_found 续了也白续 → 只记日志。
#   ③ cooldown 门（防自动续死循环）：同 session 300s 内最多自动续 2 次，超限只记日志。
#                 （续上的 turn 若再次中断会再触发本 hook，无此门 = 无限空捶 API。）
#   ④ 窗口身份门 + 焦点借还（v3）：读 transcript 的 aiTitle（= 全屏渲染器设的窗口标题）唯一锁定本会话窗口 T，
#                 然后「借还」：存当前前台 F → 借焦点到 T → 复核 fg==T → SendKeys continue → drain → 还回 F。
#                 全局单飞锁串行化（多会话同时报错不抢焦点打架）；撞名/认不出 → 不借不敲，只记日志。
#                 （v1 GetConsoleWindow 2026-06-27 因 ConPTY 返 0 失效；v2「只敲前台」救不了后台报错会话，
#                  2026-06-29 实测借还稳定后改 v3 默认借焦点。）
#
# 日志：%USERPROFILE%\claude-stopfailure-probe.log（多账号共享，USERPROFILE 不随账号变）。
#       每行 action= 字段即本次结果：SENT(continue·借还) / skip(原因) + F/aiTitle/T 诊断（F=原前台,T=本会话窗口）。
# 状态：%USERPROFILE%\claude-autocontinue-state.json（cooldown 计数台账）。
# 卸载：用 deploy-autocontinue-hook.ps1 -Mode rollback（从各账号 settings.json 摘掉登记）。

$ErrorActionPreference = 'SilentlyContinue'

# ---------- 读取 hook 输入 ----------
$raw = [Console]::In.ReadToEnd()
$sid = ''; $cwd = ''; $tp = ''; $evt = ''
try {
  $j   = $raw | ConvertFrom-Json
  $sid = $j.session_id
  $cwd = $j.cwd
  $tp  = $j.transcript_path
  $evt = $j.hook_event_name
} catch {}

$ts  = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$log = Join-Path $env:USERPROFILE 'claude-stopfailure-probe.log'
function Write-Probe([string]$action) {
  $line = "$ts  FIRED  event=$evt  session=$sid  cwd=$cwd  cfg=$env:CLAUDE_CONFIG_DIR  action=$action"
  try { Add-Content -LiteralPath $log -Value $line -Encoding utf8 } catch {}
}

# ---------- 嗅 transcript 尾部，认出错误类型 ----------
$snip = ''
try {
  if ($tp -and (Test-Path -LiteralPath $tp)) {
    $tail = Get-Content -LiteralPath $tp -Tail 8 -Encoding utf8
    $hit  = $tail | Select-String -Pattern 'overloaded|rate.?limit|server_error|Connection closed|incomplete|authentication|billing|invalid_request|model_not_found|max_output_tokens|api.?error|"is_error"|"type"\s*:\s*"error"' -AllMatches
    if ($hit)      { $snip = ($hit.Line) -join ' | ' }
    elseif ($tail) { $snip = ($tail | Select-Object -Last 1) }
  }
} catch {}
$snip = ($snip -replace '\s+', ' ').Trim()
if ($snip.Length -gt 300) { $snip = $snip.Substring(0, 300) }

# ====================== 安全门 ======================

# ① 账号门：glm 排除
$cfgLeaf = ''
try { if ($env:CLAUDE_CONFIG_DIR) { $cfgLeaf = (Split-Path -Leaf $env:CLAUDE_CONFIG_DIR).ToLower() } } catch {}
if ($cfgLeaf -eq '.claude-glm') {
  Write-Probe "skip(glm非原生账号) tail=$snip"
  exit 0
}

# ② 错误类型门：终态错误不续
if ($snip -match 'authentication|billing|invalid_request|model_not_found') {
  Write-Probe "skip(终态错误·续也白续) tail=$snip"
  exit 0
}

# ③ cooldown 门：同 session 300s 内最多 2 次
$stateFile = Join-Path $env:USERPROFILE 'claude-autocontinue-state.json'
$win = 300; $max = 2
$now = [int][double]::Parse((Get-Date -UFormat %s))
$state = @{}
if (Test-Path -LiteralPath $stateFile) {
  try { $state = Get-Content -LiteralPath $stateFile -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable } catch { $state = @{} }
}
if ($null -eq $state) { $state = @{} }
$recent = @()
if ($sid -and $state.ContainsKey($sid)) { $recent = @($state[$sid] | Where-Object { ($now - [int]$_) -lt $win }) }
if ($recent.Count -ge $max) {
  Write-Probe "skip(cooldown:${win}s内已续${max}次) tail=$snip"
  exit 0
}

# ④ 前台门 + 窗口身份门（v2 · 2026-06-27 改）：仅当「本会话自己的窗口」正在前台时才敲。
#    旧法（GetConsoleWindow + 标题以 "Claude Code" 结尾）已失效：新全屏渲染器(tui:fullscreen)把窗口标题
#    改成"对话摘要"(= transcript 的 aiTitle)，且 ConPTY 下 GetConsoleWindow() 返回 0 → 门永远过不去
#    （实测 myWin=0 / claudeWins=0 / 一直 skip）。
#    新法：读本会话 transcript 的最新 aiTitle → 枚举可见窗口 → 标题去掉开头 spinner/符号后 == aiTitle 的
#    那个 = 本会话窗口；唯一命中且它 == 前台才敲。aiTitle 跨会话唯一，多开也不会敲错窗；撞名/取不到只记日志。
Add-Type -Namespace W -Name U -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h);
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool BringWindowToTop(System.IntPtr h);
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool IsIconic(System.IntPtr h);
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int n);
[System.Runtime.InteropServices.DllImport("user32.dll", CharSet=System.Runtime.InteropServices.CharSet.Unicode)] public static extern int GetWindowText(System.IntPtr h, System.Text.StringBuilder s, int n);
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool IsWindowVisible(System.IntPtr h);
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(System.IntPtr h, out uint pid);
[System.Runtime.InteropServices.DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
public delegate bool EnumProc(System.IntPtr h, System.IntPtr l);
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, System.IntPtr l);
// 借焦点到目标窗口：AttachThreadInput 解前台锁；仅最小化才 ShowWindow 还原（不破最大化）。
public static bool Focus(System.IntPtr t){
  System.IntPtr fg = GetForegroundWindow();
  uint tT, fT; GetWindowThreadProcessId(t, out tT); GetWindowThreadProcessId(fg, out fT);
  uint me = GetCurrentThreadId();
  AttachThreadInput(me, tT, true); AttachThreadInput(fT, tT, true);
  if (IsIconic(t)) ShowWindow(t, 9);
  BringWindowToTop(t); bool ok = SetForegroundWindow(t);
  AttachThreadInput(me, tT, false); AttachThreadInput(fT, tT, false);
  return ok;
}
[System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
public struct FLASHWINFO { public uint cbSize; public System.IntPtr hwnd; public uint dwFlags; public uint uCount; public uint dwTimeout; }
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool FlashWindowEx(ref FLASHWINFO pfwi);
// 闪烁任务栏窗口提醒用户：on=持续闪到窗口被切到前台(FLASHW_ALL|FLASHW_TIMERNOFG)；off=停闪(FLASHW_STOP)
public static void Flash(System.IntPtr h, bool on){
  FLASHWINFO fi = new FLASHWINFO();
  fi.cbSize = (uint)System.Runtime.InteropServices.Marshal.SizeOf(typeof(FLASHWINFO));
  fi.hwnd = h; fi.uCount = on ? uint.MaxValue : 0u; fi.dwTimeout = 0u;
  fi.dwFlags = on ? (uint)(0x00000003 | 0x0000000C) : 0u;
  FlashWindowEx(ref fi);
}
'@
function Get-Title([long]$h) {
  if ($h -eq 0) { return '' }
  $sb = New-Object System.Text.StringBuilder 512
  [void][W.U]::GetWindowText([IntPtr]::new($h), $sb, 512); return $sb.ToString()
}
# 去掉标题开头的 spinner/符号 run（如 "✳ "、"⠂ "）+ 收尾空白
function Normalize-Title([string]$t) {
  if (-not $t) { return '' }
  ($t -replace '^[^\p{L}\p{N}]+','').Trim()
}

# 读本会话 transcript 的最新 aiTitle（只解析含 aiTitle 的最后一行，避免整文件 JSON 解析）
$aiTitle = ''
try {
  if ($tp -and (Test-Path -LiteralPath $tp)) {
    $al = Select-String -LiteralPath $tp -Pattern '"aiTitle"' -Encoding utf8
    if ($al) { try { $aiTitle = [string](($al[-1].Line | ConvertFrom-Json).aiTitle) } catch {} }
  }
} catch {}
$aiTitle = ([string]$aiTitle).Trim()

if (-not $aiTitle) { Write-Probe "skip(transcript无aiTitle·暂无法认窗) aiTitle='' tail=$snip"; exit 0 }

# 枚举可见窗口，收集"标题(去前缀后)== aiTitle"的窗口句柄
$global:aiMatch  = $aiTitle
$global:selfWins = New-Object System.Collections.ArrayList
$cb = [W.U+EnumProc]{ param($h,$l)
  if ([W.U]::IsWindowVisible($h)) {
    $n = Normalize-Title (Get-Title $h.ToInt64())
    if ($n -and $n -eq $global:aiMatch) { [void]$global:selfWins.Add($h.ToInt64()) }
  }
  return $true
}
[void][W.U]::EnumWindows($cb, [IntPtr]::Zero)
# 认窗：必须「唯一命中」才动手（撞名/找不到都不敢借焦点）
if ($global:selfWins.Count -eq 0) { Write-Probe "skip(没找到标题匹配本会话的窗口) aiTitle='$aiTitle' selfWins=0 tail=$snip"; exit 0 }
if ($global:selfWins.Count -gt 1) { Write-Probe "skip(标题撞名·命中$($global:selfWins.Count)个窗口·歧义) aiTitle='$aiTitle' tail=$snip"; exit 0 }
$target = [long]$global:selfWins[0]

# ====================== 焦点借还 + 敲键（全局单飞锁串行化）======================
# 单飞锁：多会话 near-simultaneous 报错时只放一个借还进行，其余排队（最多等 12s）→ 防两实例抢焦点打架。
#   （12s：覆盖借失败后「闪烁 + 5s 等用户停手 + 重试」整个周期，免得并发会话在别人重试窗口内就超时放弃。）
$mutex = New-Object System.Threading.Mutex($false, 'Global\ClaudeStopFailureAutoContinueBorrow')
$held  = $false
try { $held = $mutex.WaitOne(12000) } catch [System.Threading.AbandonedMutexException] { $held = $true }
if (-not $held) { Write-Probe "skip(等借还锁超时·另一会话正借还) aiTitle='$aiTitle' tail=$snip"; $mutex.Dispose(); exit 0 }

# 锁内再取「当前前台」作还回点 F（确保拿到前一个借还已还回后的真实前台）
$F    = [W.U]::GetForegroundWindow().ToInt64()
$diag = "F=$F('$(Normalize-Title (Get-Title $F))') aiTitle='$aiTitle' T=$target"

# 借：抢焦点到本会话窗口 T（第一次）
[void][W.U]::Focus([IntPtr]::new($target))
Start-Sleep -Milliseconds 450                  # settle：让 TUI 回到可输入态（250→450：从超大/超时响应恢复时 TUI 还在拆解重渲，250ms 不够）
$mid = [W.U]::GetForegroundWindow().ToInt64()

# 借失败 → 闪烁任务栏窗口提醒用户停手，5s 后重试 1 次（仅 1 次）。2026-06-30 加。
#   原理：① 任务栏闪烁吸引注意 → 用户停下鼠标/键盘；② Windows 前台锁在「前台进程一段时间没收到用户
#   输入」后才放行别的进程抢前台 → 用户一停手，重试的 SetForegroundWindow 就能成功；③ 用户也可直接点
#   闪烁窗口自己切前台，同样让重试命中。FLASHW_TIMERNOFG：持续闪到窗口被切到前台才停。
$retried = 0
if ($mid -ne $target) {
  [void][W.U]::Flash([IntPtr]::new($target), $true)   # 开始闪（持续到窗口被切前台）
  Start-Sleep -Milliseconds 5000                       # 给用户 5s 停手 / 点窗口
  [void][W.U]::Focus([IntPtr]::new($target))           # 重试借焦点（仅 1 次）
  Start-Sleep -Milliseconds 450
  $mid = [W.U]::GetForegroundWindow().ToInt64()
  $retried = 1
}

if ($mid -ne $target) {                         # 重试后仍没借到 → 还原 F、放弃敲键（防 continue 泄漏进别的窗口）
  [void][W.U]::Focus([IntPtr]::new($F))
  # 不停闪：留任务栏闪烁作人工提醒，用户点开窗口（即切前台→闪自动停）后自己手敲 continue
  Write-Probe "skip(借焦点重试${retried}次后仍未命中·已还原·留闪烁待人工) $diag mid=$mid tail=$snip"
} else {
  if ($retried) { [void][W.U]::Flash([IntPtr]::new($target), $false) }  # 借到了 → 停闪
  try {
    Add-Type -AssemblyName System.Windows.Forms
    # 文字与回车分两步发（2026-06-30 修）：合并成 "continue{ENTER}" 一发时，ENTER 常在 TUI
    # 还在吞/重渲 "continue" 字符的那一帧到达被丢，导致文字落了但没提交（症状：> continue 不回车）。
    # 故：先发文字 → settle 让 TUI 把字渲进输入框 → 复核焦点仍在 T → 再单独发 ENTER + 兜底二次 ENTER。
    [System.Windows.Forms.SendKeys]::SendWait("continue")
    Start-Sleep -Milliseconds 200               # settle：等 "continue" 字符渲进输入框再敲回车
    if ([W.U]::GetForegroundWindow().ToInt64() -eq $target) {
      [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
      Start-Sleep -Milliseconds 150
      [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")  # 兜底：已提交则空框多敲 Enter 无害；漏提交则补上
    }
    Start-Sleep -Milliseconds 350               # drain：让键派发进 T 队列后再切回，防泄漏竞态
    [void][W.U]::Focus([IntPtr]::new($F))        # 还：焦点还回原窗口 F
    $recent += $now
    if ($sid) { $state[$sid] = $recent }
    try { ($state | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $stateFile -Encoding utf8 } catch {}
    Write-Probe "SENT(continue·借还$(if ($retried) { '·重试1次' })) $diag tail=$snip"
  } catch {
    [void][W.U]::Focus([IntPtr]::new($F))        # 异常也要把焦点还回去
    Write-Probe "skip(SendKeys异常:$($_.Exception.Message)·已还原) $diag tail=$snip"
  }
}
try { $mutex.ReleaseMutex() } catch {}
$mutex.Dispose()

# StopFailure 的 stdout/exit code 本就被忽略，无需输出。
exit 0
