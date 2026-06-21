# autopilot_failcount.ps1 — /today 全托管「连续失败 2 次 → 转人工审」确定性计数器
# 为什么存在:阈值计数不能靠 LLM 自己记(context 压缩会丢计数、"再试一次"会越过阈值)。
# 确定性来自这个计数文件本身——它扛得住上下文压缩。LLM 只负责"认这次成/败",数到没数到 2 由本脚本说了算。
# 计数文件放 C:\Temp(躲 Ldterm 监控盘,避免被透明加密)。
#
# 自愈(2026-06-17):计数文件第 2 行存本轮 CLAUDE_CODE_SESSION_ID。
#   - 新 session 来 fail → 上一轮(异 session)遗留的脏计数自动作废再 +1 → "忘了开跑 reset" 不再毒害下一轮(真·100%,不靠 LLM 记)。
#   - 同 session 内累加照常 → 跑飞仍会持续 STOP,二次拦截不削弱。
#   - 拿不到 session id(空)时退化为旧的纯累加行为,开跑 reset 仍需手动兜(同会话连跑两轮也靠开跑 reset 兜)。
param(
  [ValidateSet('reset','fail','status')]
  [string]$Mode = 'status',
  [int]$Threshold = 2
)

$dir  = 'C:\Temp\today-autopilot'
$file = Join-Path $dir 'failcount.txt'
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

$sid = $env:CLAUDE_CODE_SESSION_ID
if ([string]::IsNullOrWhiteSpace($sid)) { $sid = 'no-session' }

function Get-State {
  # 返回 @{ Count=<int>; Sid=<string> };文件第 1 行=计数,第 2 行=session 戳(旧单行文件兼容:Sid 取空)
  if (Test-Path -LiteralPath $file) {
    $lines = @(Get-Content -LiteralPath $file)
    $c = 0; $s = ''
    if ($lines.Count -ge 1) { [int]::TryParse(($lines[0]).Trim(), [ref]$c) | Out-Null }
    if ($lines.Count -ge 2) { $s = ($lines[1]).Trim() }
    return @{ Count = $c; Sid = $s }
  }
  return @{ Count = 0; Sid = '' }
}

function Set-State([int]$Count, [string]$Sid) {
  Set-Content -LiteralPath $file -Value @("$Count", $Sid)
}

switch ($Mode) {
  'reset' {
    Set-State 0 $sid
    Write-Output "[autopilot] 连续失败计数已清零 (0/$Threshold)"
    exit 0
  }
  'fail' {
    $st = Get-State
    if ($st.Sid -ne $sid) {
      # 异 session 的遗留计数 → 本轮自动作废,从 0 起算(自愈核心)
      if ($st.Count -gt 0) {
        Write-Output "[autopilot] 检测到上一轮(异 session)遗留计数 $($st.Count),已自动作废,本轮从 0 起算。"
      }
      $base = 0
    }
    else {
      $base = $st.Count
    }
    $n = $base + 1
    Set-State $n $sid
    if ($n -ge $Threshold) {
      Write-Output "AUTOPILOT_STOP 🛑 已连续失败 $n 次(阈值 $Threshold)→ 立即停止本次执行,转人工审:把现状+卡点交用户,不得再试。"
      exit 2
    }
    else {
      Write-Output "[autopilot] ⚠️ 连续失败 $n/$Threshold(再失败 1 次即转人工审)"
      exit 0
    }
  }
  'status' {
    $st = Get-State
    # 异 session 的遗留计数对本轮等效于 0(下次 fail 会自动作废)
    $shown = if ($st.Sid -ne $sid) { 0 } else { $st.Count }
    Write-Output "[autopilot] 当前连续失败 $shown/$Threshold"
    exit 0
  }
}
