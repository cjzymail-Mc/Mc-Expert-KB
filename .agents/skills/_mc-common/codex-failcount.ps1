# codex-failcount.ps1 — Codex 侧任务/方案第3次失败熔断计数（模拟 Claude autopilot_failcount.ps1，但不硬编码 ~/.claude）
# $today 全托管模式用：-Mode reset(开跑清零)/fail(失败+1)/status(查)。达 3 → AUTOPILOT_STOP + 退出码 2 → 立即停、交用户、不再试第4次。
# 计数文件默认 $env:TEMP\codex-failcount.json（避 ~/.claude + 监控盘；codex sandbox 放行 TEMP）。
# ⚠️ 若 codex sandbox constrained language mode 拦 pwsh -File（同 runner），$today adapter 降级为自维护 json 计数。
param(
  [ValidateSet('reset','fail','status')][string]$Mode = 'status',
  [string]$CountFile = "$env:TEMP\codex-failcount.json",
  [int]$Threshold = 3
)
$ErrorActionPreference = 'Stop'

function Read-Count {
  if (Test-Path -LiteralPath $CountFile) {
    try { return [int](Get-Content -LiteralPath $CountFile -Raw | ConvertFrom-Json).count } catch { return 0 }
  }
  return 0
}
function Write-Count { param([int]$n); @{ count = $n } | ConvertTo-Json -Compress | Set-Content -LiteralPath $CountFile -Encoding UTF8 }

switch ($Mode) {
  'reset' {
    Write-Count 0
    "FAILCOUNT reset -> 0 (count=$CountFile)"
    exit 0
  }
  'status' {
    $c = Read-Count
    "FAILCOUNT status -> $c (threshold $Threshold, count=$CountFile)"
    exit 0
  }
  'fail' {
    $c = (Read-Count) + 1
    Write-Count $c
    if ($c -ge $Threshold) {
      "AUTOPILOT_STOP: 连续失败 $c 次（达阈值 $Threshold），立即停止本次执行、交用户、不再试第 $($Threshold+1) 次。"
      exit 2
    }
    "FAILCOUNT fail -> $c (未达 $Threshold，继续; count=$CountFile)"
    exit 0
  }
}

