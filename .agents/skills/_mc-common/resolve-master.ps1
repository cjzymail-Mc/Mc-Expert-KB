param(
  [Parameter(Mandatory = $true)][string]$SkillName,
  [switch]$Cat
)
$ErrorActionPreference = 'Stop'
function Resolve-MasterPath {
  param([string]$Name)
  if ($env:CLAUDE_SKILL_MASTER_DIR) {
    $p = Join-Path $env:CLAUDE_SKILL_MASTER_DIR ($Name + '\SKILL.md')
    if (Test-Path -LiteralPath $p) { return $p }
  }
  $userMaster = Join-Path $env:USERPROFILE ('.claude\skills\' + $Name + '\SKILL.md')
  if (Test-Path -LiteralPath $userMaster) { return $userMaster }
  $sibling = Join-Path (Split-Path (Get-Location).Path -Parent) ('Mc-Expert-repo\.claude\skills\' + $Name + '\SKILL.md')
  if (Test-Path -LiteralPath $sibling) { return $sibling }
  return $null
}
$path = Resolve-MasterPath -Name $SkillName
if (-not $path) {
  Write-Error ("MASTER_NOT_FOUND: skill='{0}' (tried CLAUDE_SKILL_MASTER_DIR env + user ~/.claude/skills + sibling Mc-Expert-repo)" -f $SkillName)
  exit 1
}
if ($Cat) { Get-Content -LiteralPath $path -Raw } else { Write-Output $path }


