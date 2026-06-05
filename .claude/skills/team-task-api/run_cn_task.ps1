#requires -Version 7
<#
run_cn_task.ps1 — coder-api 的确定性门脚本【观察模式：默认放行、只记录】
职责（确定性、不靠模型判断）：首字节检测路由 + 注入 guardrail + 调 cn + 产物落 C:\Temp\ + 退出码 + 调用日志。
不负责：2 次熔断计数 / 逻辑成功判断 / promote —— 这些由 coder-api(Claude) 侧编排。
模型选择走 -ConfigPath（每模型一个 config 文件），不用 cn --model（只接 hub slug）。

【2026-06-05 观察模式改造】目标 = 最大化探测 cn 能力边界，cn 犯错是要记录的实验数据、不是要拦的事故。
  门脚本不再硬拦 cn：① 首字节 unknown 不再 exit 2，警告后放行让 cn 撞墙；
  ② 后置禁库扫描命中不再改写 exit 9，只把 violation 记进日志、保留 cn 真实退出码。
  数据可公开+已备份，崩了可恢复。承重核验（明文 magic / promote）仍在 Claude 侧人工把关，与本脚本无关。
#>
param(
  [Parameter(Mandatory)][string]$Task,
  [Parameter(Mandatory)][string]$WorkDir,
  [string]$ConfigPath  = "$HOME\.continue\config.yaml",   # 默认 = GLM-5.1
  [string[]]$TargetFiles = @(),
  [string]$GuardrailPath = "$HOME\.claude\skills\team-task-api\cn-guardrail.md",
  [string]$OutDir = 'C:\Temp'
)

function Get-OfficeMagic([string]$Path) {
  $b = [System.IO.File]::ReadAllBytes($Path) | Select-Object -First 8
  $hex = ($b | ForEach-Object { '{0:X2}' -f $_ }) -join ' '
  if     ($hex -like '50 4B*')     { return 'plaintext' }  # PK = 明文 OOXML
  elseif ($hex -like '88 7D 1C*')  { return 'cipher'    }  # Ldterm 密文
  else                             { return 'unknown'   }
}

$officeExt = '.xlsx','.pptx','.docx'
$cipherOfficeSeen = $false   # 任一密文 Office 目标 → 开启后置禁库扫描
foreach ($f in $TargetFiles) {
  if (-not (Test-Path -LiteralPath $f)) { Write-Error "目标文件不存在: $f"; exit 3 }
  $ext = [System.IO.Path]::GetExtension($f).ToLower()
  if ($officeExt -contains $ext) {
    switch (Get-OfficeMagic $f) {
      'plaintext' { Write-Host "[route] $f -> 明文，python helper 可用" }
      'cipher'    { Write-Host "[route] $f -> 密文，自动直穿 COM helper（已授权）"; $cipherOfficeSeen = $true }
      'unknown'   { Write-Warning "[observe] $f 首字节未知（既非明文 50 4B 也非密文 88 7D 1C）—— 观察模式放行，让 cn 自行尝试，结果看日志/实时输出" }
    }
  }
}

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

# guardrail 直接拼进 prompt（最稳；不依赖 --rule 解析）
$guardrail = if (Test-Path -LiteralPath $GuardrailPath) { Get-Content -LiteralPath $GuardrailPath -Raw } else { '' }
$prompt = @"
$guardrail

=== 本次任务 ===
$Task

（产物一律写到 $OutDir 下）
"@

$sw = [System.Diagnostics.Stopwatch]::StartNew()
Push-Location -LiteralPath $WorkDir
try {
  # Tee：既实时显示给人看，又把全文捕获进 $cnOut 供后置禁库扫描
  cn -p --silent --auto --config $ConfigPath $prompt 2>&1 | Tee-Object -Variable cnOut
  $code = $LASTEXITCODE
} finally {
  Pop-Location
}
$sw.Stop()

# ── 观察探针：禁库使用扫描（只记录、不拦截）──────────────────────────────
# 【观察模式】原为硬拦（命中改写 exit 9），现降级为纯观察：仍扫描，但只把命中写进日志的
# violation 字段、保留 cn 真实退出码，不再判失败。目的 = 看见 cn 何时破软门用禁库直读密文，
# 把"GLM 守不守 helper-only 软门"刻画成可统计的数据。
# 仅当「涉及密文 Office + cn 自称成功(result:ok)」才扫禁库**真实调用语法**——
# 先要求 result:ok 再扫，避免误伤拒绝信息（cn 拒绝时常说"我不能用 openpyxl"，含词不算违规）。
# 承重保证仍在 Claude 侧人工核验（明文 magic / promote），不依赖本探针。
$violation = ''
$cnText = ($cnOut | Out-String)
if ($cipherOfficeSeen -and $cnText -match '"result"\s*:\s*"ok"') {
  $banned = @(
    'import\s+openpyxl', 'load_workbook\s*\(', 'read_excel\s*\(',
    'import\s+xlrd', 'import\s+olefile', 'import\s+pptx', 'from\s+pptx',
    'import\s+docx', 'from\s+docx'
  )
  foreach ($pat in $banned) { if ($cnText -match $pat) { $violation = $pat; break } }
  # 裸 win32com（疑似自写 COM）：出现 win32com 但全程未经 office_com_helpers
  if (-not $violation -and $cnText -match 'win32com' -and $cnText -notmatch 'office_com_helpers') {
    $violation = '裸 win32com（疑似自写 COM，未经 helper）'
  }
}
if ($violation) {
  Write-Warning "[observe] cn 在密文 Office 任务里疑似用禁库直读/自写COM：$violation —— 观察模式只记录、不判失败；Claude 侧 promote 前仍须人工核验产物"
}

# 调用日志（模型对比 / 迭代用）—— 每行一条 JSON，append 到 $OutDir\cn-calls.log
$log = [ordered]@{
  ts      = (Get-Date).ToString('s')
  config  = [System.IO.Path]::GetFileName($ConfigPath)   # 哪个模型
  workdir = $WorkDir
  task    = if ($Task.Length -gt 80) { $Task.Substring(0,80) } else { $Task }
  targets = $TargetFiles
  exit    = $code
  ms      = $sw.ElapsedMilliseconds
  violation = $violation   # 非空 = 禁库扫描命中（观察模式：只记录，exit 保留 cn 真实退出码）
}
($log | ConvertTo-Json -Compress) | Add-Content -LiteralPath (Join-Path $OutDir 'cn-calls.log') -Encoding utf8

exit $code
