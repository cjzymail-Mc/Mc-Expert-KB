# stopfailure-probe.ps1  ——  B 版（探针 + SendKeys 自动续接）
#
# 演进史：
#   v1（探针）：只往日志写一行，验证「黄字 Connection closed mid-response 触不触发 StopFailure」。
#               2026-06-26 已实测 → 触发 ✅（本会话 ff0bf9b5）。
#   v2（B 版）：在 v1 日志基础上，叠加「StopFailure 触发 → 向 Claude Code TUI 敲 continue{Enter}」。
#
# 【定位 · 不可被改成生产兜底】这是「省手敲」便利工具，不是无人值守自动续。
#   依据 KB references/loops-and-automation.md §7（含写操作的 loop 不无人值守）：
#   只在「用户大概率在场」（目标 Claude 窗口正在前台）时才敲键，否则只记日志、放弃敲键。
#   谁要把下面的「前台校验」换成 SetForegroundWindow 强抢焦点 —— 那就把便利工具变成了无人值守兜底，违红线。
#
# 四道安全门（全过才敲键）：
#   ① 账号门：glm（CLAUDE_CONFIG_DIR 叶名 = .claude-glm）不在原生 Anthropic 账号内 → 只记日志不敲键。
#   ② 错误类型门：仅瞬时错误（连接中断/overloaded/server_error/unknown/rate_limit）才续；
#                 auth/billing/invalid_request/model_not_found 续了也白续 → 只记日志。
#   ③ cooldown 门（防自动续死循环）：同 session 300s 内最多自动续 2 次，超限只记日志。
#                 （续上的 turn 若再次中断会再触发本 hook，无此门=无限空捶 API。）
#   ④ 窗口身份门：用 GetConsoleWindow() 锁定「本会话自己的窗口」，仅它==前台才敲；
#                 拿不到自身窗口时仅在"全机唯一 Claude 窗口"无歧义时回退，否则只记日志。
#                 解决多窗口下「continue 敲进另一个 Claude 窗口」的错窗问题；敲键前再复核焦点。
#
# 日志：%USERPROFILE%\claude-stopfailure-probe.log（多账号共享，USERPROFILE 不随账号变）。
# 状态：%USERPROFILE%\claude-autocontinue-state.json（cooldown 计数台账）。
# 回滚：同目录 stopfailure-probe.ps1.bak 即 v1 探针版。

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

# ④ 前台门 + 窗口身份门：仅当「本会话自己的窗口」正在前台时才敲。
#    多窗口（可能同开多个 session）下，所有 Claude 窗口标题都叫 "Claude Code"，
#    只靠标题会把 continue 敲进"恰好在前台的另一个 Claude 窗口" → 错窗。
#    GetConsoleWindow() 返回本 hook 继承的控制台 = 触发会话自己的窗口；只有它 == 前台才敲。
#    拿不到自身窗口（如 ConPTY 下返回 0）时，仅在"全机只有 1 个 Claude 窗口"无歧义时回退，否则只记日志。
Add-Type -Namespace W -Name U -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
[System.Runtime.InteropServices.DllImport("kernel32.dll")] public static extern System.IntPtr GetConsoleWindow();
[System.Runtime.InteropServices.DllImport("user32.dll", CharSet=System.Runtime.InteropServices.CharSet.Unicode)] public static extern int GetWindowText(System.IntPtr h, System.Text.StringBuilder s, int n);
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool IsWindowVisible(System.IntPtr h);
public delegate bool EnumProc(System.IntPtr h, System.IntPtr l);
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, System.IntPtr l);
'@
function Get-Title([long]$h) {
  if ($h -eq 0) { return '' }
  $sb = New-Object System.Text.StringBuilder 512
  [void][W.U]::GetWindowText([IntPtr]::new($h), $sb, 512); return $sb.ToString()
}
# 注意：本机文件夹名含 "Claude Code Workshop"，VS Code / 浏览器标题都会误含 "Claude Code"。
# 故用锚定式：标题须以 "Claude Code" 结尾（TUI 标题如 "? Claude Code"），排掉 "...- Visual Studio Code" / "...- Edge"。
$titlePat = 'Claude Code\s*$'
$global:cwins = New-Object System.Collections.ArrayList
$cb = [W.U+EnumProc]{ param($h,$l)
  if ([W.U]::IsWindowVisible($h)) { $t = Get-Title $h.ToInt64(); if ($t -match $titlePat) { [void]$global:cwins.Add($h.ToInt64()) } }
  return $true
}
[void][W.U]::EnumWindows($cb, [IntPtr]::Zero)

$myWin = [W.U]::GetConsoleWindow().ToInt64()
$fg    = [W.U]::GetForegroundWindow().ToInt64()
$diag  = "myWin=$myWin('$(Get-Title $myWin)') fg=$fg('$(Get-Title $fg)') claudeWins=$($global:cwins.Count)"

# 判定能否安全敲
$canSend = $false; $why = ''; $target = 0
if ($myWin -ne 0 -and $fg -eq $myWin) {
  $canSend = $true; $why = '本会话窗口在前台'; $target = $myWin
} elseif ($myWin -eq 0 -and $global:cwins.Count -eq 1 -and $fg -eq $global:cwins[0]) {
  $canSend = $true; $why = '全机仅1个Claude窗口·无歧义'; $target = $global:cwins[0]
} elseif ($myWin -ne 0) {
  $why = '本会话窗口不在前台'
} else {
  $why = "拿不到自身窗口且Claude窗口数=$($global:cwins.Count)·歧义"
}
if (-not $canSend) { Write-Probe "skip($why) $diag tail=$snip"; exit 0 }

# 小延时让 TUI 回到可输入态，然后复核前台仍是目标窗口（防 ④→敲键之间焦点跳走）
Start-Sleep -Milliseconds 400
if ([W.U]::GetForegroundWindow().ToInt64() -ne $target) {
  Write-Probe "skip(敲键前焦点已离开本会话窗口) $diag tail=$snip"
  exit 0
}

# ====================== 敲键 ======================
try {
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.SendKeys]::SendWait("continue{ENTER}")
  $recent += $now
  if ($sid) { $state[$sid] = $recent }
  try { ($state | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $stateFile -Encoding utf8 } catch {}
  Write-Probe "SENT(continue·$why) $diag tail=$snip"
} catch {
  Write-Probe "skip(SendKeys异常:$($_.Exception.Message)) tail=$snip"
}

# StopFailure 的 stdout/exit code 本就被忽略，无需输出。
exit 0
