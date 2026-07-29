[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('Init', 'Show', 'CheckBudget', 'Consume', 'Handoff', 'Done', 'WaitHuman')]
    [string]$Action,

    [ValidateSet('coder', 'planner', 'claude', 'codex')]
    [string]$Role,

    [ValidateSet('coder', 'planner', 'claude', 'codex')]
    [string]$To,

    [string]$Reason = '',

    [ValidateRange(1, 86400)]
    [int]$BudgetSeconds = 10800
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $repoRoot) {
    throw 'REPO_ROOT_NOT_FOUND'
}
$repoRoot = [System.IO.Path]::GetFullPath(($repoRoot | Select-Object -First 1).Trim())
$statePath = Join-Path $repoRoot '.copilot-state.json'
$taskPath = Join-Path $repoRoot '.copilot-task.md'
$tempPath = Join-Path $repoRoot 'temp.md'
$utf8 = [System.Text.UTF8Encoding]::new($false)

function Write-AtomicText {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Text)
    $tmp = "$Path.tmp.$([guid]::NewGuid().ToString('N'))"
    $bytes = $utf8.GetBytes($Text)
    $stream = [System.IO.FileStream]::new(
        $tmp,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    }
    finally {
        $stream.Dispose()
    }

    if ([System.IO.File]::Exists($Path)) {
        $replaced = "$Path.replace-old.$([guid]::NewGuid().ToString('N')).tmp"
        [System.IO.File]::Replace($tmp, $Path, $replaced, $true)
        if ([System.IO.File]::Exists($replaced)) {
            [System.IO.File]::Delete($replaced)
        }
    }
    else {
        [System.IO.File]::Move($tmp, $Path)
    }
}

function Read-State {
    if (-not [System.IO.File]::Exists($statePath)) {
        throw 'STATE_NOT_FOUND'
    }
    $raw = [System.IO.File]::ReadAllText($statePath, $utf8)
    if ([string]::IsNullOrWhiteSpace($raw)) {
        throw 'STATE_EMPTY'
    }
    try {
        $state = ($raw | ConvertFrom-Json -ErrorAction Stop)
        $version = if ($state.PSObject.Properties.Name -contains 'version') { [int]$state.version } else { 1 }
        if ($version -le 2) {
            if ($state.turn -eq 'claude') { $state.turn = 'coder' }
            elseif ($state.turn -eq 'codex') { $state.turn = 'planner' }
            elseif ($state.turn -notin @('coder', 'planner')) { throw "STATE_ROLE_INVALID: $($state.turn)" }
            if ($state.PSObject.Properties.Name -contains 'version') { $state.version = 3 }
            else { $state | Add-Member -NotePropertyName 'version' -NotePropertyValue 3 }
        }
        elseif ($state.turn -notin @('coder', 'planner')) {
            throw "STATE_ROLE_INVALID: $($state.turn)"
        }
        return $state
    }
    catch {
        throw "STATE_INVALID_JSON: $($_.Exception.Message)"
    }
}

function Write-State {
    param([Parameter(Mandatory)]$State)
    $json = ($State | ConvertTo-Json -Depth 8) + [Environment]::NewLine
    Write-AtomicText -Path $statePath -Text $json
}

function Get-Sha256 {
    param([Parameter(Mandatory)][string]$Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([Convert]::ToHexString($sha.ComputeHash($utf8.GetBytes($Text))).ToLowerInvariant())
    }
    finally {
        $sha.Dispose()
    }
}

function Get-FileSha256 {
    param([Parameter(Mandatory)][string]$Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        return ([Convert]::ToHexString($sha.ComputeHash($stream)).ToLowerInvariant())
    }
    finally {
        $stream.Dispose()
        $sha.Dispose()
    }
}

function Assert-RoleTurn {
    param([Parameter(Mandatory)]$State, [Parameter(Mandatory)][string]$ExpectedRole)
    if ($State.status -ne 'running') {
        throw "STATE_NOT_RUNNING: $($State.status)"
    }
    if ($State.turn -ne $ExpectedRole) {
        throw "TURN_MISMATCH: expected=$ExpectedRole actual=$($State.turn)"
    }
}

function Set-StateProperty {
    param(
        [Parameter(Mandatory)]$State,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)]$Value
    )
    if ($State.PSObject.Properties.Name -contains $Name) {
        $State.$Name = $Value
    }
    else {
        $State | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Set-NewBudgetSegment {
    param([Parameter(Mandatory)]$State, [Parameter(Mandatory)][int]$Seconds)
    $now = [DateTimeOffset]::Now
    $nextSegment = if ($State.PSObject.Properties.Name -contains 'segment') {
        [int]$State.segment + 1
    } else {
        1
    }
    Set-StateProperty -State $State -Name 'status' -Value 'running'
    Set-StateProperty -State $State -Name 'version' -Value 3
    Set-StateProperty -State $State -Name 'segment' -Value $nextSegment
    Set-StateProperty -State $State -Name 'budget_seconds' -Value $Seconds
    Set-StateProperty -State $State -Name 'budget_started' -Value $now.ToString('o')
    Set-StateProperty -State $State -Name 'budget_deadline' -Value $now.AddSeconds($Seconds).ToString('o')
    Set-StateProperty -State $State -Name 'updated' -Value $now.ToString('o')
    Set-StateProperty -State $State -Name 'reason' -Value ''
}

function Test-BudgetExpired {
    param([Parameter(Mandatory)]$State)
    if (-not ($State.PSObject.Properties.Name -contains 'budget_deadline')) {
        throw 'BUDGET_DEADLINE_MISSING'
    }
    $deadline = [DateTimeOffset]::Parse(
        [string]$State.budget_deadline,
        [Globalization.CultureInfo]::InvariantCulture
    )
    return ([DateTimeOffset]::Now -ge $deadline)
}

function Convert-ToCanonicalRole {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $Value }
    switch ($Value) {
        'claude' { return 'coder' }
        'codex' { return 'planner' }
        default { return $Value }
    }
}

if ($Role) { $Role = Convert-ToCanonicalRole -Value $Role }
if ($To) { $To = Convert-ToCanonicalRole -Value $To }

switch ($Action) {
    'Init' {
        $existing = $null
        if ([System.IO.File]::Exists($statePath)) {
            $existing = Read-State
            if ($existing.status -eq 'running') {
                if (-not ($existing.PSObject.Properties.Name -contains 'budget_deadline')) {
                    Set-NewBudgetSegment -State $existing -Seconds $BudgetSeconds
                    $existing.version = 3
                    Write-State -State $existing
                }
                elseif ($existing.turn -eq 'coder' -and (Test-BudgetExpired -State $existing)) {
                    # A fresh coder session is the recovery trigger. Rotate an expired
                    # coder-owned segment here so one invocation can resume the run.
                    Set-NewBudgetSegment -State $existing -Seconds $BudgetSeconds
                    Write-State -State $existing
                }
                $existing | ConvertTo-Json -Depth 8
                break
            }
            if ($existing.status -eq 'paused_budget') {
                Set-NewBudgetSegment -State $existing -Seconds $BudgetSeconds
                $existing.version = 3
                Write-State -State $existing
                $existing | ConvertTo-Json -Depth 8
                break
            }
        }

        if (-not [System.IO.File]::Exists($tempPath)) {
            throw 'TEMP_NOT_FOUND'
        }
        if ($null -ne $existing -and $existing.status -in @('done', 'wait_human')) {
            $tempInfo = [System.IO.FileInfo]::new($tempPath)
            $terminalUpdated = [DateTimeOffset]::Parse(
                [string]$existing.updated,
                [Globalization.CultureInfo]::InvariantCulture
            )
            if ($tempInfo.Length -eq 0) {
                throw 'NEW_TASK_NOT_NEWER_THAN_TERMINAL_STATE'
            }
            if ($existing.PSObject.Properties.Name -contains 'terminal_temp_sha256') {
                $currentTempSha256 = Get-FileSha256 -Path $tempPath
                if ($currentTempSha256 -eq [string]$existing.terminal_temp_sha256) {
                    throw 'NEW_TASK_MATCHES_TERMINAL_TEMP'
                }
            }
            if ($tempInfo.LastWriteTimeUtc -le $terminalUpdated.UtcDateTime) {
                throw 'NEW_TASK_NOT_NEWER_THAN_TERMINAL_STATE'
            }
        }
        $task = [System.IO.File]::ReadAllText($tempPath, $utf8)
        if ([string]::IsNullOrWhiteSpace($task)) {
            throw 'INITIAL_TASK_EMPTY'
        }

        Write-AtomicText -Path $taskPath -Text $task
        $state = [ordered]@{
            version = 3
            run_id = [guid]::NewGuid().ToString('N')
            status = 'running'
            turn = 'coder'
            seq = 0
            segment = 1
            budget_seconds = $BudgetSeconds
            budget_started = [DateTimeOffset]::Now.ToString('o')
            budget_deadline = [DateTimeOffset]::Now.AddSeconds($BudgetSeconds).ToString('o')
            task_sha256 = Get-Sha256 -Text $task
            updated = [DateTimeOffset]::Now.ToString('o')
            reason = ''
        }
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }

    'Show' {
        Read-State | ConvertTo-Json -Depth 8
    }

    'CheckBudget' {
        if (-not $Role) { throw 'ROLE_REQUIRED' }
        $state = Read-State
        if ($state.status -ne 'running') {
            $state | ConvertTo-Json -Depth 8
            break
        }
        if ($state.turn -eq $Role -and (Test-BudgetExpired -State $state)) {
            $state.status = 'paused_budget'
            $state.reason = "segment_$($state.segment)_budget_exhausted"
            $state.updated = [DateTimeOffset]::Now.ToString('o')
            Write-State -State $state
        }
        $state | ConvertTo-Json -Depth 8
    }

    'Consume' {
        if (-not $Role) { throw 'ROLE_REQUIRED' }
        $state = Read-State
        Assert-RoleTurn -State $state -ExpectedRole $Role
        if (-not [System.IO.File]::Exists($tempPath)) {
            throw 'TEMP_NOT_FOUND'
        }

        $content = [System.IO.File]::ReadAllText($tempPath, $utf8)
        $stream = [System.IO.FileStream]::new(
            $tempPath,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        try {
            $stream.SetLength(0)
            $stream.Flush($true)
        }
        finally {
            $stream.Dispose()
        }
        if (([System.IO.FileInfo]::new($tempPath)).Length -ne 0) {
            throw 'TEMP_CLEAR_VERIFY_FAILED'
        }
        if ([string]::IsNullOrWhiteSpace($content)) {
            throw 'HANDOFF_EMPTY'
        }
        $content
    }

    'Handoff' {
        if (-not $Role -or -not $To) { throw 'ROLE_AND_TO_REQUIRED' }
        if ($Role -eq $To) { throw 'HANDOFF_TARGET_INVALID' }
        if (($Role -eq 'coder' -and $To -ne 'planner') -or
            ($Role -eq 'planner' -and $To -ne 'coder')) {
            throw 'HANDOFF_DIRECTION_INVALID'
        }
        $state = Read-State
        Assert-RoleTurn -State $state -ExpectedRole $Role
        if (-not [System.IO.File]::Exists($tempPath) -or
            ([System.IO.FileInfo]::new($tempPath)).Length -eq 0) {
            throw 'HANDOFF_BODY_EMPTY'
        }
        $state.turn = $To
        $state.seq = [int]$state.seq + 1
        $state.updated = [DateTimeOffset]::Now.ToString('o')
        if (Test-BudgetExpired -State $state) {
            $state.status = 'paused_budget'
            $state.reason = "segment_$($state.segment)_budget_exhausted"
        }
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }

    'Done' {
        if ($Role -ne 'planner') { throw 'ONLY_PLANNER_CAN_COMPLETE' }
        $state = Read-State
        Assert-RoleTurn -State $state -ExpectedRole 'planner'
        if (-not [System.IO.File]::Exists($tempPath) -or
            ([System.IO.FileInfo]::new($tempPath)).Length -eq 0) {
            throw 'FINAL_REVIEW_EMPTY'
        }
        $state.status = 'done'
        Set-StateProperty -State $state -Name 'terminal_temp_sha256' -Value (Get-FileSha256 -Path $tempPath)
        $state.seq = [int]$state.seq + 1
        $state.updated = [DateTimeOffset]::Now.ToString('o')
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }

    'WaitHuman' {
        if (-not $Role) { throw 'ROLE_REQUIRED' }
        if ([string]::IsNullOrWhiteSpace($Reason)) { throw 'REASON_REQUIRED' }
        $state = Read-State
        Assert-RoleTurn -State $state -ExpectedRole $Role
        if ([System.IO.File]::Exists($tempPath) -and ([System.IO.FileInfo]::new($tempPath)).Length -ne 0) {
            throw 'WAIT_HUMAN_REQUIRES_EMPTY_TEMP'
        }
        $state.status = 'wait_human'
        if ([System.IO.File]::Exists($tempPath)) {
            Set-StateProperty -State $state -Name 'terminal_temp_sha256' -Value (Get-FileSha256 -Path $tempPath)
        }
        $state.reason = $Reason
        $state.seq = [int]$state.seq + 1
        $state.updated = [DateTimeOffset]::Now.ToString('o')
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }
}
