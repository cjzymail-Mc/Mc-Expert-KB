[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('Config', 'Init', 'ForceInit', 'Show', 'CheckBudget', 'Consume', 'Handoff', 'Done', 'WaitHuman', 'ResolveHuman', 'Cancel', 'Recover', 'Takeover')]
    [string]$Action,

    [ValidateSet('coder', 'planner', 'claude', 'codex')]
    [string]$Role,

    [ValidateSet('coder', 'planner', 'claude', 'codex')]
    [string]$To,

    [string]$Reason = '',

    [ValidateSet('success', 'failure')]
    [string]$HandoffKind = 'success',

    [string]$FailureKey = '',

    [ValidateSet('continue', 'rework', 'pass', 'cancel')]
    [string]$Decision,

    [string]$WorkerToken = '',

    [string]$HumanApprovalId = '',

    [string]$ExpectedRepo = '',

    [string]$ExpectedRunId = ''
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
$messagePath = Join-Path $repoRoot '.copilot-message.md'
$utf8 = [System.Text.UTF8Encoding]::new($false)
$configPath = Join-Path $PSScriptRoot 'double-session-config.json'

function Get-DoubleSessionConfig {
    if (-not [System.IO.File]::Exists($configPath)) {
        throw "CONFIG_NOT_FOUND: $configPath"
    }
    $raw = [System.IO.File]::ReadAllText($configPath, $utf8)
    if ([string]::IsNullOrWhiteSpace($raw)) {
        throw 'CONFIG_EMPTY'
    }
    try {
        $parsed = $raw | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "CONFIG_INVALID_JSON: $($_.Exception.Message)"
    }

    $required = @('coder_interval_seconds', 'planner_interval_seconds', 'max_budget_seconds')
    $actual = @($parsed.PSObject.Properties.Name)
    $missing = @($required | Where-Object { $_ -notin $actual })
    $extra = @($actual | Where-Object { $_ -notin $required })
    if ($missing.Count -gt 0 -or $extra.Count -gt 0) {
        throw "CONFIG_FIELDS_INVALID: missing=$($missing -join ',') extra=$($extra -join ',')"
    }

    $normalized = [ordered]@{}
    foreach ($name in $required) {
        $value = $parsed.$name
        if ($value -is [bool] -or ($value -isnot [int] -and $value -isnot [long])) {
            throw "CONFIG_VALUE_NOT_INTEGER: $name"
        }
        $number = [long]$value
        $minimum = if ($name -eq 'max_budget_seconds') { 1 } else { 60 }
        $maximum = if ($name -eq 'max_budget_seconds') { 86400 } else { 3600 }
        if ($number -lt $minimum -or $number -gt $maximum) {
            throw "CONFIG_VALUE_OUT_OF_RANGE: $name expected=$minimum..$maximum actual=$number"
        }
        if ($name -ne 'max_budget_seconds' -and ($number % 60) -ne 0) {
            throw "CONFIG_INTERVAL_NOT_WHOLE_MINUTE: $name actual=$number"
        }
        $normalized[$name] = [int]$number
    }
    return [pscustomobject]$normalized
}

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
        if ($version -le 3) {
            Set-StateProperty -State $state -Name 'version' -Value 4
            Set-StateProperty -State $state -Name 'owner_repo' -Value $repoRoot
            $legacyWait = $state.status -eq 'wait_human'
            Set-StateProperty -State $state -Name 'resume_turn' -Value $(if ($legacyWait) { [string]$state.turn } else { '' })
            Set-StateProperty -State $state -Name 'allowed_resolutions' -Value $(if ($legacyWait) { @('continue', 'rework', 'pass', 'cancel') } else { @() })
            Set-StateProperty -State $state -Name 'outcome' -Value ''
            Set-StateProperty -State $state -Name 'decision_by' -Value ''
            $legacyApproval = if ($legacyWait) { (Get-Sha256 -Text "v3-wait:$($state.run_id):$($state.task_sha256)").Substring(0, 32) } else { '' }
            Set-StateProperty -State $state -Name 'human_approval_id' -Value $legacyApproval
            Set-StateProperty -State $state -Name 'worker_token_hashes' -Value ([pscustomobject]@{ coder = ''; planner = '' })
            Set-StateProperty -State $state -Name 'worker_lease_deadlines' -Value ([pscustomobject]@{ coder = ''; planner = '' })
        }
        if ($version -le 4 -or -not ($state.PSObject.Properties.Name -contains 'failure_ledger')) {
            Set-StateProperty -State $state -Name 'version' -Value 5
            Set-StateProperty -State $state -Name 'failure_ledger' -Value $null
        }
        if (-not ($state.PSObject.Properties.Name -contains 'phase')) {
            Set-StateProperty -State $state -Name 'phase' -Value 'ready'
            Set-StateProperty -State $state -Name 'mutation_action' -Value ''
            Set-StateProperty -State $state -Name 'mutation_role' -Value ''
            Set-StateProperty -State $state -Name 'mutation_token_sha256' -Value ''
        }
        if (-not ($state.PSObject.Properties.Name -contains 'last_action')) {
            Set-StateProperty -State $state -Name 'last_action' -Value ''
            Set-StateProperty -State $state -Name 'last_action_role' -Value ''
            Set-StateProperty -State $state -Name 'last_action_token_sha256' -Value ''
            Set-StateProperty -State $state -Name 'last_action_seq' -Value -1
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

function Assert-RunBinding {
    param([Parameter(Mandatory)]$State)
    if ($ExpectedRepo) {
        $expected = [System.IO.Path]::GetFullPath($ExpectedRepo)
        if ($expected -ne $repoRoot -or [string]$State.owner_repo -ne $repoRoot) {
            throw "REPO_MISMATCH: expected=$expected actual=$repoRoot owner=$($State.owner_repo)"
        }
    }
    if ($ExpectedRunId -and [string]$State.run_id -ne $ExpectedRunId) {
        throw "RUN_MISMATCH: expected=$ExpectedRunId actual=$($State.run_id)"
    }
}

function Assert-FrozenTask {
    param([Parameter(Mandatory)]$State)
    if (-not [System.IO.File]::Exists($taskPath)) { throw 'FROZEN_TASK_NOT_FOUND' }
    if (-not ($State.PSObject.Properties.Name -contains 'task_sha256')) { throw 'FROZEN_TASK_HASH_MISSING' }
    $actual = Get-FileSha256 -Path $taskPath
    if ($actual -ne [string]$State.task_sha256) { throw "FROZEN_TASK_MISMATCH: expected=$($State.task_sha256) actual=$actual" }
}

function Write-MessageSnapshot {
    param([Parameter(Mandatory)]$State, [Parameter(Mandatory)][string]$Text, [Parameter(Mandatory)][int]$Sequence)
    Write-AtomicText -Path $messagePath -Text $Text
    Set-StateProperty -State $State -Name 'message_sha256' -Value (Get-Sha256 -Text $Text)
    Set-StateProperty -State $State -Name 'message_seq' -Value $Sequence
}

function Assert-MessageSnapshot {
    param([Parameter(Mandatory)]$State)
    if (-not ($State.PSObject.Properties.Name -contains 'message_sha256')) { return }
    if (-not [System.IO.File]::Exists($messagePath)) { throw 'MESSAGE_SNAPSHOT_NOT_FOUND' }
    $actual = Get-FileSha256 -Path $messagePath
    if ($actual -ne [string]$State.message_sha256) { throw "MESSAGE_SNAPSHOT_MISMATCH: expected=$($State.message_sha256) actual=$actual" }
}

function Start-Mutation {
    param([Parameter(Mandatory)]$State, [Parameter(Mandatory)][string]$Name, [string]$MutationRole = '', [string]$Token = '')
    $tokenHash = if ([string]::IsNullOrWhiteSpace($Token)) { '' } else { Get-Sha256 -Text $Token }
    if ($State.phase -eq 'working') {
        if ([string]$State.mutation_action -ne $Name -or [string]$State.mutation_role -ne $MutationRole -or [string]$State.mutation_token_sha256 -ne $tokenHash) {
            throw "INCOMPLETE_MUTATION: action=$($State.mutation_action) role=$($State.mutation_role)"
        }
    }
    elseif ($State.phase -ne 'ready') { throw "STATE_PHASE_INVALID: $($State.phase)" }
    $State.phase = 'working'
    $State.mutation_action = $Name
    $State.mutation_role = $MutationRole
    $State.mutation_token_sha256 = $tokenHash
    Write-State -State $State
}

function Complete-Mutation {
    param([Parameter(Mandatory)]$State)
    $State.phase = 'ready'
    $State.mutation_action = ''
    $State.mutation_role = ''
    $State.mutation_token_sha256 = ''
}

function Set-LastAction {
    param([Parameter(Mandatory)]$State, [Parameter(Mandatory)][string]$Name, [string]$ActionRole = '', [string]$Token = '')
    $State.last_action = $Name
    $State.last_action_role = $ActionRole
    $State.last_action_token_sha256 = if ([string]::IsNullOrWhiteSpace($Token)) { '' } else { Get-Sha256 -Text $Token }
    $State.last_action_seq = [int]$State.seq
}

function Test-LastActionReplay {
    param([Parameter(Mandatory)]$State, [Parameter(Mandatory)][string]$Name, [string]$ActionRole = '', [string]$Token = '')
    $tokenHash = if ([string]::IsNullOrWhiteSpace($Token)) { '' } else { Get-Sha256 -Text $Token }
    return $State.phase -eq 'ready' -and [string]$State.last_action -eq $Name -and
        [string]$State.last_action_role -eq $ActionRole -and [string]$State.last_action_token_sha256 -eq $tokenHash
}

function Set-WorkerLease {
    param([Parameter(Mandatory)]$State, [Parameter(Mandatory)][string]$LeaseRole, [Parameter(Mandatory)][string]$Token)
    if ([string]::IsNullOrWhiteSpace($Token)) { throw 'WORKER_TOKEN_REQUIRED' }
    $State.worker_token_hashes.$LeaseRole = Get-Sha256 -Text $Token
    $State.worker_lease_deadlines.$LeaseRole = [DateTimeOffset]::Now.AddSeconds($State.budget_seconds).ToString('o')
}

function Assert-WorkerLease {
    param([Parameter(Mandatory)]$State, [Parameter(Mandatory)][string]$LeaseRole, [Parameter(Mandatory)][string]$Token)
    if ([string]::IsNullOrWhiteSpace($Token)) { throw 'WORKER_TOKEN_REQUIRED' }
    $current = [string]$State.worker_token_hashes.$LeaseRole
    if ([string]::IsNullOrWhiteSpace($current)) {
        Set-WorkerLease -State $State -LeaseRole $LeaseRole -Token $Token
        return
    }
    if ($current -ne (Get-Sha256 -Text $Token)) { throw 'WORKER_ACTIVE' }
    Set-WorkerLease -State $State -LeaseRole $LeaseRole -Token $Token
}

function Set-StateProperty {
    param(
        [Parameter(Mandatory)]$State,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][AllowNull()]$Value
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
    Set-StateProperty -State $State -Name 'version' -Value 5
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

if ($Action -eq 'Config') {
    (Get-DoubleSessionConfig) | ConvertTo-Json -Depth 4
    exit 0
}

$mutexName = "Local\mc_double_session_$((Get-Sha256 -Text $repoRoot).Substring(0, 24))"
$repoMutex = [System.Threading.Mutex]::new($false, $mutexName)
$lockTaken = $false
try {
try {
    $lockTaken = $repoMutex.WaitOne(0)
}
catch [System.Threading.AbandonedMutexException] {
    # The previous holder crashed. Windows grants this process ownership;
    # continue under the recovered lock and always release it below.
    $lockTaken = $true
}
if (-not $lockTaken) { throw 'REPO_BUSY' }
switch ($Action) {
    'Init' {
        $config = Get-DoubleSessionConfig
        $budgetSeconds = [int]$config.max_budget_seconds
        if ([string]::IsNullOrWhiteSpace($WorkerToken)) { throw 'WORKER_TOKEN_REQUIRED' }
        $existing = $null
        if ([System.IO.File]::Exists($statePath)) {
            $existing = Read-State
            Assert-RunBinding -State $existing
            if ($existing.status -eq 'running') {
                if (-not ($existing.PSObject.Properties.Name -contains 'budget_deadline')) {
                    Set-NewBudgetSegment -State $existing -Seconds $budgetSeconds
                    $existing.version = 5
                    Write-State -State $existing
                }
                elseif ($existing.turn -eq 'coder' -and (Test-BudgetExpired -State $existing)) {
                    # A fresh coder session is the recovery trigger. Rotate an expired
                    # coder-owned segment here so one invocation can resume the run.
                    Set-NewBudgetSegment -State $existing -Seconds $budgetSeconds
                    Write-State -State $existing
                }
                Assert-WorkerLease -State $existing -LeaseRole 'coder' -Token $WorkerToken
                Write-State -State $existing
                $existing | ConvertTo-Json -Depth 8
                break
            }
            if ($existing.status -eq 'paused_budget') {
                Set-NewBudgetSegment -State $existing -Seconds $budgetSeconds
                $existing.version = 5
                Set-WorkerLease -State $existing -LeaseRole 'coder' -Token $WorkerToken
                Write-State -State $existing
                $existing | ConvertTo-Json -Depth 8
                break
            }
        }

        if (-not [System.IO.File]::Exists($tempPath)) {
            throw 'TEMP_NOT_FOUND'
        }
        if ($null -ne $existing -and $existing.status -eq 'wait_human') {
            throw 'WAIT_HUMAN_REQUIRES_RESOLUTION'
        }
        if ($null -ne $existing -and $existing.status -in @('done', 'cancelled')) {
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
        Write-AtomicText -Path $messagePath -Text $task
        $state = [ordered]@{
            version = 5
            owner_repo = $repoRoot
            run_id = [guid]::NewGuid().ToString('N')
            status = 'running'
            turn = 'coder'
            seq = 0
            segment = 1
            budget_seconds = $budgetSeconds
            budget_started = [DateTimeOffset]::Now.ToString('o')
            budget_deadline = [DateTimeOffset]::Now.AddSeconds($budgetSeconds).ToString('o')
            task_sha256 = Get-Sha256 -Text $task
            message_sha256 = Get-Sha256 -Text $task
            message_seq = 0
            updated = [DateTimeOffset]::Now.ToString('o')
            reason = ''
            resume_turn = ''
            allowed_resolutions = @()
            outcome = ''
            decision_by = ''
            human_approval_id = ''
            failure_ledger = $null
            phase = 'ready'
            mutation_action = ''
            mutation_role = ''
            mutation_token_sha256 = ''
            last_action = ''
            last_action_role = ''
            last_action_token_sha256 = ''
            last_action_seq = -1
            worker_token_hashes = [ordered]@{ coder = (Get-Sha256 -Text $WorkerToken); planner = '' }
            worker_lease_deadlines = [ordered]@{ coder = [DateTimeOffset]::Now.AddSeconds($budgetSeconds).ToString('o'); planner = '' }
        }
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }

    'Show' {
        $state = Read-State
        Assert-RunBinding -State $state
        $state | ConvertTo-Json -Depth 8
    }

    'CheckBudget' {
        if (-not $Role) { throw 'ROLE_REQUIRED' }
        $state = Read-State
        Assert-RunBinding -State $state
        Assert-WorkerLease -State $state -LeaseRole $Role -Token $WorkerToken
        Start-Mutation -State $state -Name 'CheckBudget' -MutationRole $Role -Token $WorkerToken
        if ($state.status -ne 'running') {
            Complete-Mutation -State $state
            Write-State -State $state
            $state | ConvertTo-Json -Depth 8
            break
        }
        if ($state.turn -eq $Role -and (Test-BudgetExpired -State $state)) {
            $state.status = 'paused_budget'
            $state.reason = "segment_$($state.segment)_budget_exhausted"
            $state.updated = [DateTimeOffset]::Now.ToString('o')
        }
        Complete-Mutation -State $state
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }

    'Consume' {
        if (-not $Role) { throw 'ROLE_REQUIRED' }
        $state = Read-State
        Assert-RunBinding -State $state
        Assert-WorkerLease -State $state -LeaseRole $Role -Token $WorkerToken
        if ((Test-LastActionReplay -State $state -Name 'Consume' -ActionRole $Role -Token $WorkerToken) -and
            [System.IO.File]::Exists($tempPath) -and ([System.IO.FileInfo]::new($tempPath)).Length -eq 0) {
            Assert-FrozenTask -State $state
            Assert-MessageSnapshot -State $state
            [System.IO.File]::ReadAllText($messagePath, $utf8)
            break
        }
        Assert-RoleTurn -State $state -ExpectedRole $Role
        $consumeRetry = $state.phase -eq 'working' -and $state.mutation_action -eq 'Consume'
        Assert-FrozenTask -State $state
        Assert-MessageSnapshot -State $state
        if (-not [System.IO.File]::Exists($tempPath)) {
            throw 'TEMP_NOT_FOUND'
        }
        Start-Mutation -State $state -Name 'Consume' -MutationRole $Role -Token $WorkerToken
        if ($consumeRetry -and ([System.IO.FileInfo]::new($tempPath)).Length -eq 0) {
            $content = [System.IO.File]::ReadAllText($messagePath, $utf8)
            Complete-Mutation -State $state
            Write-State -State $state
            $content
            break
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
        Complete-Mutation -State $state
        Set-LastAction -State $state -Name 'Consume' -ActionRole $Role -Token $WorkerToken
        Write-State -State $state
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
        Assert-RunBinding -State $state
        Assert-WorkerLease -State $state -LeaseRole $Role -Token $WorkerToken
        if (Test-LastActionReplay -State $state -Name 'Handoff' -ActionRole $Role -Token $WorkerToken) {
            $state | ConvertTo-Json -Depth 8
            break
        }
        Assert-RoleTurn -State $state -ExpectedRole $Role
        Assert-FrozenTask -State $state
        if ($Role -eq 'planner' -and $HandoffKind -ne 'success') { throw 'PLANNER_HANDOFF_KIND_INVALID' }
        if ($Role -eq 'coder' -and $HandoffKind -eq 'failure' -and [string]::IsNullOrWhiteSpace($FailureKey)) {
            throw 'FAILURE_KEY_REQUIRED'
        }
        if ($Role -eq 'coder' -and $HandoffKind -eq 'success' -and -not [string]::IsNullOrWhiteSpace($FailureKey)) {
            throw 'FAILURE_KEY_NOT_ALLOWED_FOR_SUCCESS'
        }
        if (-not [System.IO.File]::Exists($tempPath) -or
            ([System.IO.FileInfo]::new($tempPath)).Length -eq 0) {
            throw 'HANDOFF_BODY_EMPTY'
        }
        Start-Mutation -State $state -Name 'Handoff' -MutationRole $Role -Token $WorkerToken
        $state.turn = $To
        $state.seq = [int]$state.seq + 1
        $handoffText = [System.IO.File]::ReadAllText($tempPath, $utf8)
        Write-MessageSnapshot -State $state -Text $handoffText -Sequence ([int]$state.seq)
        if ($Role -eq 'coder') {
            if ($HandoffKind -eq 'success') {
                $state.failure_ledger = $null
            }
            else {
                $messageHash = Get-Sha256 -Text $handoffText
                $previous = $state.failure_ledger
                if ($null -ne $previous -and [string]$previous.failure_key -eq $FailureKey) {
                    $state.failure_ledger = [pscustomobject]@{
                        failure_key = $FailureKey
                        count = [int]$previous.count + 1
                        first_coder_seq = [int]$previous.first_coder_seq
                        last_coder_seq = [int]$state.seq
                        last_message_sha256 = $messageHash
                    }
                }
                else {
                    $state.failure_ledger = [pscustomobject]@{
                        failure_key = $FailureKey
                        count = 1
                        first_coder_seq = [int]$state.seq
                        last_coder_seq = [int]$state.seq
                        last_message_sha256 = $messageHash
                    }
                }
            }
        }
        $state.updated = [DateTimeOffset]::Now.ToString('o')
        if (Test-BudgetExpired -State $state) {
            $state.status = 'paused_budget'
            $state.reason = "segment_$($state.segment)_budget_exhausted"
        }
        Complete-Mutation -State $state
        Set-LastAction -State $state -Name 'Handoff' -ActionRole $Role -Token $WorkerToken
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }

    'Done' {
        if ($Role -ne 'planner') { throw 'ONLY_PLANNER_CAN_COMPLETE' }
        $state = Read-State
        Assert-RunBinding -State $state
        Assert-WorkerLease -State $state -LeaseRole $Role -Token $WorkerToken
        if (Test-LastActionReplay -State $state -Name 'Done' -ActionRole $Role -Token $WorkerToken) {
            $state | ConvertTo-Json -Depth 8
            break
        }
        Assert-RoleTurn -State $state -ExpectedRole 'planner'
        Assert-FrozenTask -State $state
        if (-not [System.IO.File]::Exists($tempPath) -or
            ([System.IO.FileInfo]::new($tempPath)).Length -eq 0) {
            throw 'FINAL_REVIEW_EMPTY'
        }
        Start-Mutation -State $state -Name 'Done' -MutationRole $Role -Token $WorkerToken
        $state.status = 'done'
        Set-StateProperty -State $state -Name 'terminal_temp_sha256' -Value (Get-FileSha256 -Path $tempPath)
        $state.seq = [int]$state.seq + 1
        $doneText = [System.IO.File]::ReadAllText($tempPath, $utf8)
        Write-MessageSnapshot -State $state -Text $doneText -Sequence ([int]$state.seq)
        $state.updated = [DateTimeOffset]::Now.ToString('o')
        Complete-Mutation -State $state
        Set-LastAction -State $state -Name 'Done' -ActionRole $Role -Token $WorkerToken
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }

    'WaitHuman' {
        if (-not $Role) { throw 'ROLE_REQUIRED' }
        if ($Role -eq 'coder') { throw 'CODER_WAIT_HUMAN_FORBIDDEN' }
        if ([string]::IsNullOrWhiteSpace($Reason)) { throw 'REASON_REQUIRED' }
        $state = Read-State
        Assert-RunBinding -State $state
        Assert-WorkerLease -State $state -LeaseRole $Role -Token $WorkerToken
        Assert-RoleTurn -State $state -ExpectedRole $Role
        Assert-FrozenTask -State $state
        if ($null -eq $state.failure_ledger -or [int]$state.failure_ledger.count -lt 2) {
            throw 'PLANNER_GATE_REQUIRES_TWO_CODER_REPORTS'
        }
        if ([System.IO.File]::Exists($tempPath) -and ([System.IO.FileInfo]::new($tempPath)).Length -ne 0) {
            throw 'WAIT_HUMAN_REQUIRES_EMPTY_TEMP'
        }
        Start-Mutation -State $state -Name 'WaitHuman' -MutationRole $Role -Token $WorkerToken
        $state.status = 'wait_human'
        Set-StateProperty -State $state -Name 'resume_turn' -Value $Role
        Set-StateProperty -State $state -Name 'allowed_resolutions' -Value @('continue', 'rework', 'pass', 'cancel')
        Set-StateProperty -State $state -Name 'human_approval_id' -Value ([guid]::NewGuid().ToString('N'))
        if ([System.IO.File]::Exists($tempPath)) {
            Set-StateProperty -State $state -Name 'terminal_temp_sha256' -Value (Get-FileSha256 -Path $tempPath)
        }
        $state.reason = $Reason
        $state.seq = [int]$state.seq + 1
        $state.updated = [DateTimeOffset]::Now.ToString('o')
        Complete-Mutation -State $state
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }

    'ForceInit' {
        $config = Get-DoubleSessionConfig
        $budgetSeconds = [int]$config.max_budget_seconds
        if ([string]::IsNullOrWhiteSpace($WorkerToken)) { throw 'WORKER_TOKEN_REQUIRED' }
        if ([string]::IsNullOrWhiteSpace($ExpectedRunId)) { throw 'EXPECTED_RUN_ID_REQUIRED' }
        if ([string]::IsNullOrWhiteSpace($HumanApprovalId)) { throw 'HUMAN_APPROVAL_ID_REQUIRED' }
        $existing = Read-State
        Assert-RunBinding -State $existing
        if ($existing.status -ne 'wait_human') { throw "FORCE_INIT_NOT_ALLOWED: $($existing.status)" }
        if ([string]$existing.human_approval_id -ne $HumanApprovalId) { throw 'HUMAN_APPROVAL_ID_MISMATCH' }
        if (-not [System.IO.File]::Exists($tempPath)) { throw 'TEMP_NOT_FOUND' }
        $tempInfo = [System.IO.FileInfo]::new($tempPath)
        if ($tempInfo.Length -eq 0) { throw 'NEW_TASK_NOT_DETECTED' }
        $task = [System.IO.File]::ReadAllText($tempPath, $utf8)
        if ([string]::IsNullOrWhiteSpace($task)) { throw 'NEW_TASK_NOT_DETECTED' }
        $taskHash = Get-Sha256 -Text $task
        if (($existing.PSObject.Properties.Name -contains 'message_sha256') -and
            $taskHash -eq [string]$existing.message_sha256) { throw 'NEW_TASK_NOT_DETECTED' }
        $oldUpdated = [DateTimeOffset]::Parse([string]$existing.updated, [Globalization.CultureInfo]::InvariantCulture)
        if ($tempInfo.LastWriteTimeUtc -le $oldUpdated.UtcDateTime) { throw 'NEW_TASK_NOT_DETECTED' }

        $now = [DateTimeOffset]::Now
        $state = [ordered]@{
            version = 5
            owner_repo = $repoRoot
            run_id = [guid]::NewGuid().ToString('N')
            status = 'running'
            turn = 'coder'
            seq = 0
            segment = 1
            budget_seconds = $budgetSeconds
            budget_started = $now.ToString('o')
            budget_deadline = $now.AddSeconds($budgetSeconds).ToString('o')
            task_sha256 = $taskHash
            message_sha256 = $taskHash
            message_seq = 0
            updated = $now.ToString('o')
            reason = ''
            resume_turn = ''
            allowed_resolutions = @()
            outcome = ''
            decision_by = 'control_entry'
            human_approval_id = ''
            failure_ledger = $null
            replaced_run_id = [string]$existing.run_id
            replaced_status = 'wait_human'
            replaced_at = $now.ToString('o')
            phase = 'ready'
            mutation_action = ''
            mutation_role = ''
            mutation_token_sha256 = ''
            last_action = ''
            last_action_role = ''
            last_action_token_sha256 = ''
            last_action_seq = -1
            worker_token_hashes = [ordered]@{ coder = (Get-Sha256 -Text $WorkerToken); planner = '' }
            worker_lease_deadlines = [ordered]@{ coder = $now.AddSeconds($budgetSeconds).ToString('o'); planner = '' }
        }

        $oldStateText = [System.IO.File]::ReadAllText($statePath, $utf8)
        $oldTaskText = if ([System.IO.File]::Exists($taskPath)) { [System.IO.File]::ReadAllText($taskPath, $utf8) } else { $null }
        $oldMessageText = if ([System.IO.File]::Exists($messagePath)) { [System.IO.File]::ReadAllText($messagePath, $utf8) } else { $null }
        try {
            Write-AtomicText -Path $taskPath -Text $task
            Write-AtomicText -Path $messagePath -Text $task
            Write-State -State $state
        }
        catch {
            Write-AtomicText -Path $statePath -Text $oldStateText
            if ($null -ne $oldTaskText) { Write-AtomicText -Path $taskPath -Text $oldTaskText }
            if ($null -ne $oldMessageText) { Write-AtomicText -Path $messagePath -Text $oldMessageText }
            throw
        }
        $state | ConvertTo-Json -Depth 8
    }

    'ResolveHuman' {
        if (-not $Decision) { throw 'DECISION_REQUIRED' }
        if ([string]::IsNullOrWhiteSpace($HumanApprovalId)) { throw 'HUMAN_APPROVAL_ID_REQUIRED' }
        $state = Read-State
        Assert-RunBinding -State $state
        if ($state.status -ne 'wait_human') { throw "STATE_NOT_WAIT_HUMAN: $($state.status)" }
        if ([string]$state.human_approval_id -ne $HumanApprovalId) { throw 'HUMAN_APPROVAL_ID_MISMATCH' }
        if ($Decision -notin @($state.allowed_resolutions)) { throw "DECISION_NOT_ALLOWED: $Decision" }
        if ($Decision -in @('continue', 'rework')) { Assert-FrozenTask -State $state }
        Start-Mutation -State $state -Name 'ResolveHuman'
        switch ($Decision) {
            'continue' { $state.status = 'running'; $state.turn = [string]$state.resume_turn }
            'rework' { $state.status = 'running'; $state.turn = 'coder' }
            'pass' { $state.status = 'done'; $state.outcome = 'approval_pass'; $state.decision_by = 'approval_entry' }
            'cancel' { $state.status = 'cancelled'; $state.outcome = 'cancelled'; $state.decision_by = 'approval_entry' }
        }
        $state.reason = $Reason
        $state.human_approval_id = ''
        $state.seq = [int]$state.seq + 1
        $state.updated = [DateTimeOffset]::Now.ToString('o')
        if ($Decision -in @('continue', 'rework')) {
            $resolutionMessage = "HUMAN_RESOLUTION`ndecision: $Decision`nreason: $Reason`nrun_id: $($state.run_id)`nseq: $($state.seq)`n"
            Write-AtomicText -Path $tempPath -Text $resolutionMessage
            Write-MessageSnapshot -State $state -Text $resolutionMessage -Sequence ([int]$state.seq)
        }
        if ($Decision -in @('continue', 'rework')) { $state.failure_ledger = $null }
        $state.worker_token_hashes.coder = ''
        $state.worker_token_hashes.planner = ''
        Complete-Mutation -State $state
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }

    'Cancel' {
        $state = Read-State
        Assert-RunBinding -State $state
        if ($state.status -eq 'cancelled') { $state | ConvertTo-Json -Depth 8; break }
        if ($state.status -eq 'done') { throw 'CANCEL_NOT_ALLOWED_DONE' }
        if ($state.status -notin @('running', 'paused_budget', 'wait_human')) { throw "CANCEL_NOT_ALLOWED: $($state.status)" }
        Start-Mutation -State $state -Name 'Cancel'
        $state.status = 'cancelled'
        $state.outcome = 'cancelled'
        $state.decision_by = 'control_entry'
        if ([System.IO.File]::Exists($tempPath)) {
            Set-StateProperty -State $state -Name 'terminal_temp_sha256' -Value (Get-FileSha256 -Path $tempPath)
        }
        $state.reason = $Reason
        $state.seq = [int]$state.seq + 1
        $state.updated = [DateTimeOffset]::Now.ToString('o')
        $state.worker_token_hashes.coder = ''
        $state.worker_token_hashes.planner = ''
        Complete-Mutation -State $state
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }

    { $_ -in @('Recover', 'Takeover') } {
        if (-not $Role) { throw 'ROLE_REQUIRED' }
        $state = Read-State
        Assert-RunBinding -State $state
        if ([string]::IsNullOrWhiteSpace($WorkerToken)) { throw 'WORKER_TOKEN_REQUIRED' }
        if ($state.status -notin @('running', 'paused_budget')) { throw "TAKEOVER_NOT_ALLOWED: $($state.status)" }
        $deadline = [string]$state.worker_lease_deadlines.$Role
        $leaseExpired = [string]::IsNullOrWhiteSpace($deadline) -or
            ([DateTimeOffset]::Now -ge [DateTimeOffset]::Parse($deadline, [Globalization.CultureInfo]::InvariantCulture))
        $explicitTakeover = $Action -eq 'Takeover' -and $HumanApprovalId -eq "takeover:$($state.run_id)"
        if (-not $leaseExpired -and -not $explicitTakeover -and [string]$state.worker_token_hashes.$Role -ne (Get-Sha256 -Text $WorkerToken)) { throw 'WORKER_ACTIVE' }
        Start-Mutation -State $state -Name $Action -MutationRole $Role -Token $WorkerToken
        if ($Action -eq 'Recover' -and $state.status -eq 'paused_budget') {
            $config = Get-DoubleSessionConfig
            Set-NewBudgetSegment -State $state -Seconds ([int]$config.max_budget_seconds)
        }
        Set-WorkerLease -State $state -LeaseRole $Role -Token $WorkerToken
        if ($explicitTakeover) { $state.decision_by = 'control_entry' }
        $state.updated = [DateTimeOffset]::Now.ToString('o')
        Complete-Mutation -State $state
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }
}
}
finally {
    if ($lockTaken) { $repoMutex.ReleaseMutex() }
    $repoMutex.Dispose()
}
