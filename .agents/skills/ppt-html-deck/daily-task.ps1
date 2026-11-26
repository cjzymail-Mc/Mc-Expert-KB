[CmdletBinding()]
param(
    [ValidateSet('Ensure','Use','Record','Run')][string]$Mode = 'Ensure',
    [ValidateSet('codex','codex2')][string]$Launcher,
    [string]$Feedback, [string]$Subject, [string]$Outcome, [string]$Evidence,
    [ValidateSet('automatic','explicit','continued','unclassified')][string]$InvocationSource = 'unclassified',
    [string]$SessionId = $env:CODEX_THREAD_ID
)
$ErrorActionPreference = 'Stop'

# The installed skills directory or the individual skill may be a junction.
function Get-PhysicalDirectory([string]$Path) {
    $dir = Get-Item -LiteralPath $Path -Force
    if ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        $target = @($dir.Target)[0]
        if (-not $target) { throw "Cannot resolve directory link: $Path" }
        if (-not [IO.Path]::IsPathRooted($target)) { $target = Join-Path $dir.Parent.FullName $target }
        return Get-PhysicalDirectory $target
    }
    if (-not $dir.Parent) { return $dir.FullName }
    return Join-Path (Get-PhysicalDirectory $dir.Parent.FullName) $dir.Name
}
$ownDir = Get-Item -Force -LiteralPath (Get-PhysicalDirectory $PSScriptRoot)
$entry = Join-Path $ownDir.Parent.Parent.FullName 'expert-daily\daily-task.ps1'
& $entry -Expert $ownDir.Name @PSBoundParameters
