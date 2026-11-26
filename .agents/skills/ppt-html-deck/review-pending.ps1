[CmdletBinding()]
param([Parameter(Mandatory)][string]$LocalDir, [Parameter(Mandatory)][ValidateSet('codex','codex2')][string]$Launcher)
$ErrorActionPreference = 'Stop'
$root = & git -C $PSScriptRoot rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) { throw 'Cannot locate the expert knowledge repository.' }
& (Join-Path $root '.agents/expert-daily/review-pending.ps1') -Expert ppt-html-deck -LocalDir $LocalDir -Launcher $Launcher
