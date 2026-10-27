[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('Config', 'BootstrapProbe', 'ValidateTask', 'ConsumeDraft', 'CommitContract', 'ArchiveRun', 'GoalContract', 'Init', 'ForceInit', 'Show', 'WaitTurn', 'CheckBudget', 'RefreshBudget', 'Consume', 'Handoff', 'RecordGateResult', 'Done', 'WaitHuman', 'ResolveHuman', 'Cancel', 'Recover', 'SafeBootstrapTakeover', 'SafeTakeover', 'Takeover')]
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

    [string]$ExpectedRunId = '',

    [int]$ObservedSeq = -1,

    [int]$TimeoutSeconds = 0,

    [ValidateSet('claude-native', 'codex-native', 'codex-glm', 'claude-glm', 'other', 'unknown')]
    [string]$RuntimeClass = 'unknown',

    [string]$RuntimeEvidence = '',

    [string]$PreparedTaskSha256 = '',

    [ValidateSet('planner', 'mc-expert')]
    [string]$ReviewGateActor,

    [ValidateSet('pass', 'rework', 'fail', 'blocked', 'transport_failure')]
    [string]$ReviewGateResult,

    [string]$ReviewEvidence = '',

    [string]$ReviewFailureKey = '',

    [switch]$CodexJsonEnvelope
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

function Get-TaskSection {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string]$Text,
        [Parameter(Mandatory)][string]$Name,
        [string]$NextName = ''
    )
    $startPattern = "(?im)^##[ \t]+$([regex]::Escape($Name))[ \t]*\r?$"
    $start = [regex]::Match($Text, $startPattern)
    if (-not $start.Success) { return '' }
    $bodyStart = $start.Index + $start.Length
    if ([string]::IsNullOrWhiteSpace($NextName)) {
        return $Text.Substring($bodyStart).Trim()
    }
    $nextPattern = "(?im)^##[ \t]+$([regex]::Escape($NextName))[ \t]*\r?$"
    $next = [regex]::Match($Text, $nextPattern, [System.Text.RegularExpressions.RegexOptions]::None, [TimeSpan]::FromSeconds(1))
    if (-not $next.Success -or $next.Index -le $bodyStart) { return '' }
    return $Text.Substring($bodyStart, $next.Index - $bodyStart).Trim()
}

function Get-TaskField {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Text, [Parameter(Mandatory)][string]$Name)
    $match = [regex]::Match($Text, "(?im)^[ \t]*$([regex]::Escape($Name)):[ \t]*(?<value>[^\r\n]+)")
    if (-not $match.Success) { return '' }
    return $match.Groups['value'].Value.Trim()
}

function Get-TaskValidation {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Text)
    $missing = [System.Collections.Generic.List[string]]::new()
    $marker = [regex]::IsMatch($Text, '(?m)^DOUBLE_TASK_CONTRACT=v1\s*$')
    if (-not $marker) { [void]$missing.Add('DOUBLE_TASK_CONTRACT=v1') }

    $sections = @(
        @{ name = 'original_request'; next = 'authority' },
        @{ name = 'authority'; next = 'terminal_state' },
        @{ name = 'terminal_state'; next = 'scope' },
        @{ name = 'scope'; next = 'guardrails' },
        @{ name = 'guardrails'; next = 'checkpoints' },
        @{ name = 'checkpoints'; next = 'done_when' },
        @{ name = 'done_when'; next = 'runtime' },
        @{ name = 'runtime'; next = '' }
    )
    $sectionBodies = @{}
    foreach ($section in $sections) {
        $body = Get-TaskSection -Text $Text -Name $section.name -NextName $section.next
        $sectionBodies[$section.name] = $body
        if ([string]::IsNullOrWhiteSpace($body)) { [void]$missing.Add("section:$($section.name)") }
    }

    $requiredFields = @(
        @{ section = 'original_request'; fields = @('original_request_sha256', 'original_request_json') },
        @{ section = 'authority'; fields = @('target_repo', 'authority_sources') },
        @{ section = 'terminal_state'; fields = @('result_state') },
        @{ section = 'scope'; fields = @('in_scope', 'out_of_scope', 'read_forbidden', 'write_forbidden') },
        @{ section = 'guardrails'; fields = @('red_lines', 'human_gates', 'authorization_boundary') },
        @{ section = 'runtime'; fields = @('planner_runtime', 'review_gate', 'runtime_evidence') }
    )
    foreach ($group in $requiredFields) {
        $body = [string]$sectionBodies[$group.section]
        foreach ($field in $group.fields) {
            if ([string]::IsNullOrWhiteSpace((Get-TaskField -Text $body -Name $field))) {
                [void]$missing.Add("$($group.section):$field")
            }
        }
    }

    $originalHash = Get-TaskField -Text ([string]$sectionBodies['original_request']) -Name 'original_request_sha256'
    $originalJson = Get-TaskField -Text ([string]$sectionBodies['original_request']) -Name 'original_request_json'
    if (-not [string]::IsNullOrWhiteSpace($originalJson)) {
        try {
            $originalText = $originalJson | ConvertFrom-Json -ErrorAction Stop
            if ($originalText -isnot [string] -or [string]::IsNullOrWhiteSpace($originalText)) {
                [void]$missing.Add('original_request:original_request_json_empty')
            }
            elseif ($originalHash -ne (Get-Sha256 -Text ([string]$originalText))) {
                [void]$missing.Add('original_request:sha256_mismatch')
            }
        }
        catch { [void]$missing.Add('original_request:original_request_json_invalid') }
    }
    if (-not [string]::IsNullOrWhiteSpace($originalHash) -and $originalHash -notmatch '^[0-9a-f]{64}$') {
        [void]$missing.Add('original_request:original_request_sha256_invalid')
    }

    $checkpointMatches = [regex]::Matches([string]$sectionBodies['checkpoints'], '(?im)^\s*-\s+id:\s*[A-Za-z0-9_-]+\s*$')
    if ($checkpointMatches.Count -eq 0) { [void]$missing.Add('checkpoints:item') }

    $targetRepo = Get-TaskField -Text ([string]$sectionBodies['authority']) -Name 'target_repo'
    if (-not [string]::IsNullOrWhiteSpace($targetRepo)) {
        try {
            if ([System.IO.Path]::GetFullPath($targetRepo.Trim('"')) -ne $repoRoot) {
                [void]$missing.Add('authority:target_repo_mismatch')
            }
        }
        catch { [void]$missing.Add('authority:target_repo_invalid') }
    }

    $plannerRuntime = Get-TaskField -Text ([string]$sectionBodies['runtime']) -Name 'planner_runtime'
    $reviewGate = Get-TaskField -Text ([string]$sectionBodies['runtime']) -Name 'review_gate'
    $runtimeEvidence = Get-TaskField -Text ([string]$sectionBodies['runtime']) -Name 'runtime_evidence'
    $runtimeValues = @('claude-native', 'codex-native', 'codex-glm', 'claude-glm', 'other', 'unknown')
    if (-not [string]::IsNullOrWhiteSpace($plannerRuntime) -and $plannerRuntime -notin $runtimeValues) {
        [void]$missing.Add('runtime:planner_runtime_invalid')
    }
    if (-not [string]::IsNullOrWhiteSpace($reviewGate) -and $reviewGate -notin @('planner_only', 'planner_plus_mc_expert')) {
        [void]$missing.Add('runtime:review_gate_invalid')
    }
    if ($plannerRuntime -notin @('claude-native', 'codex-native') -and $reviewGate -eq 'planner_only') {
        [void]$missing.Add('runtime:unknown_or_non_native_requires_double_gate')
    }

    $doneWhen = [string]$sectionBodies['done_when']
    $doneMatches = [regex]::Matches($doneWhen, '(?ms)^\s*-\s+id:\s*(?<id>[A-Za-z0-9_-]+)\s*\r?\n(?<body>.*?)(?=^\s*-\s+id:|\z)')
    if ($doneMatches.Count -eq 0) { [void]$missing.Add('done_when:item') }
    $seenIds = @{}
    foreach ($item in $doneMatches) {
        $id = $item.Groups['id'].Value
        if ($seenIds.ContainsKey($id)) { [void]$missing.Add("done_when:duplicate_id:$id") }
        else { $seenIds[$id] = $true }
        foreach ($field in @('claim', 'verification', 'expected', 'failure_case')) {
            if ([string]::IsNullOrWhiteSpace((Get-TaskField -Text $item.Groups['body'].Value -Name $field))) {
                [void]$missing.Add("done_when:${id}:$field")
            }
        }
    }

    [pscustomobject]@{
        marker = $marker
        valid = $missing.Count -eq 0
        missing = @($missing)
        task_sha256 = if ([string]::IsNullOrEmpty($Text)) { '' } else { Get-Sha256 -Text $Text }
        done_when_count = $doneMatches.Count
        planner_runtime = $plannerRuntime
        declared_review_gate = $reviewGate
        runtime_evidence = $runtimeEvidence
    }
}

function Get-EffectiveReviewGate {
    param([string]$PlannerRuntime, [string]$CoderRuntime)
    $native = @('claude-native', 'codex-native')
    if ($PlannerRuntime -in $native -and $CoderRuntime -in $native) { return 'planner_only' }
    return 'planner_plus_mc_expert'
}

function New-ReviewGateResults {
    return [pscustomobject]@{
        planner = [pscustomobject]@{ status = 'pending'; evidence_sha256 = ''; updated = '' }
        mc_expert = [pscustomobject]@{ status = 'pending'; evidence_sha256 = ''; updated = ''; transport_failure_key = ''; transport_failure_count = 0 }
    }
}

function Reset-ReviewGateResults {
    param([Parameter(Mandatory)]$State)
    Set-StateProperty -State $State -Name 'review_gate_results' -Value (New-ReviewGateResults)
}

function Get-RunArchivePath {
    param([Parameter(Mandatory)]$State)
    $stamp = [DateTimeOffset]::Parse([string]$State.updated, [Globalization.CultureInfo]::InvariantCulture).ToLocalTime().ToString('yyyyMMdd-HHmmss')
    return Join-Path $repoRoot ("team-progress\double-workflow\$stamp-$($State.run_id).md")
}

function Remove-ArchiveSecrets {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Text)
    return [regex]::Replace(
        $Text,
        '(?im)^.*(?:worker_token|token_sha256|worker_token_hashes|worker_lease_deadlines|human_approval_id).*(?:\r?\n|$)',
        ''
    )
}

function Write-RunArchive {
    param(
        [Parameter(Mandatory)]$State,
        [string]$ArchiveOutcome = '',
        [string]$ReplacementRunId = ''
    )
    $archivePath = Get-RunArchivePath -State $State
    if ([System.IO.File]::Exists($archivePath)) {
        return [pscustomobject]@{ archive_path = $archivePath; created = $false; sha256 = (Get-FileSha256 -Path $archivePath) }
    }
    if (-not [System.IO.File]::Exists($taskPath)) { throw 'ARCHIVE_TASK_NOT_FOUND' }
    $taskText = Remove-ArchiveSecrets -Text ([System.IO.File]::ReadAllText($taskPath, $utf8))
    $messageText = if ([System.IO.File]::Exists($messagePath)) { Remove-ArchiveSecrets -Text ([System.IO.File]::ReadAllText($messagePath, $utf8)) } else { '' }
    $outcome = if ([string]::IsNullOrWhiteSpace($ArchiveOutcome)) { [string]$State.status } else { $ArchiveOutcome }
    $replacementLine = if ([string]::IsNullOrWhiteSpace($ReplacementRunId)) { '' } else { "- replacement_run_id: $ReplacementRunId`n" }
    $archiveText = @"
# double-workflow run archive

- run_id: $($State.run_id)
- terminal_status: $($State.status)
- outcome: $outcome
- updated: $($State.updated)
$replacementLine
## frozen_task

$taskText

## planner_final_message

$messageText
"@
    [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($archivePath)) | Out-Null
    Write-AtomicText -Path $archivePath -Text $archiveText
    return [pscustomobject]@{ archive_path = $archivePath; created = $true; sha256 = (Get-FileSha256 -Path $archivePath) }
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
        if ($version -le 5 -or -not ($state.PSObject.Properties.Name -contains 'effective_review_gate')) {
            Set-StateProperty -State $state -Name 'version' -Value 6
            Set-StateProperty -State $state -Name 'prepared_task_sha256' -Value $(if ($state.PSObject.Properties.Name -contains 'task_sha256') { [string]$state.task_sha256 } else { '' })
            Set-StateProperty -State $state -Name 'planner_runtime' -Value 'unknown'
            Set-StateProperty -State $state -Name 'coder_runtime' -Value 'unknown'
            Set-StateProperty -State $state -Name 'runtime_evidence' -Value ([pscustomobject]@{ planner = 'legacy_state_provider_not_proven'; coder = 'legacy_state_provider_not_proven' })
            Set-StateProperty -State $state -Name 'effective_review_gate' -Value 'planner_plus_mc_expert'
            Set-StateProperty -State $state -Name 'review_gate_results' -Value (New-ReviewGateResults)
            Set-StateProperty -State $state -Name 'archive_path' -Value ''
            Set-StateProperty -State $state -Name 'terminal_archive_sha256' -Value ''
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

function Get-TurnWakeEventName {
    param(
        [Parameter(Mandatory)][string]$RunId,
        [Parameter(Mandatory)][string]$WakeRole
    )
    $identity = "$repoRoot|$RunId|$WakeRole"
    return "Local\mc_double_session_wake_$((Get-Sha256 -Text $identity).Substring(0, 32))"
}

function Send-TurnWakeSignal {
    param(
        [Parameter(Mandatory)][string]$RunId,
        [Parameter(Mandatory)][string]$WakeRole
    )
    $wakeEvent = $null
    try {
        $createdNew = $false
        $wakeEvent = [System.Threading.EventWaitHandle]::new(
            $false,
            [System.Threading.EventResetMode]::AutoReset,
            (Get-TurnWakeEventName -RunId $RunId -WakeRole $WakeRole),
            [ref]$createdNew
        )
        [void]$wakeEvent.Set()
    }
    catch {
        # Wake-up is advisory. The configured timeout remains the fail-safe.
    }
    finally {
        if ($null -ne $wakeEvent) { $wakeEvent.Dispose() }
    }
}

function Read-WaitTurnState {
    param(
        [Parameter(Mandatory)][System.Threading.Mutex]$RepoMutex,
        [Parameter(Mandatory)][System.Diagnostics.Stopwatch]$Clock,
        [Parameter(Mandatory)][int]$TimeoutMilliseconds
    )
    $remaining = $TimeoutMilliseconds - [int]$Clock.ElapsedMilliseconds
    if ($remaining -le 0) { return $null }

    $lockTaken = $false
    try {
        try {
            $lockTaken = $RepoMutex.WaitOne($remaining)
        }
        catch [System.Threading.AbandonedMutexException] {
            $lockTaken = $true
        }
        if (-not $lockTaken) { return $null }
        $state = Read-State
        Assert-RunBinding -State $state
        return $state
    }
    finally {
        if ($lockTaken) { $RepoMutex.ReleaseMutex() }
    }
}

function Test-WaitTurnActionable {
    param(
        [Parameter(Mandatory)]$State,
        [Parameter(Mandatory)][string]$WaitRole,
        [Parameter(Mandatory)][int]$AfterSeq
    )
    $actualSeq = [int]$State.seq
    if ($actualSeq -lt $AfterSeq) {
        throw "STATE_SEQ_REGRESSION: expected_at_least=$AfterSeq actual=$actualSeq"
    }
    if ($actualSeq -gt $AfterSeq) { return $true }
    if ([string]$State.status -in @('done', 'cancelled')) { return $true }
    return [string]$State.status -eq 'running' -and [string]$State.turn -eq $WaitRole
}

function Write-WaitTurnResult {
    param(
        [Parameter(Mandatory)][string]$Result,
        [Parameter(Mandatory)][System.Diagnostics.Stopwatch]$Clock,
        [Parameter(Mandatory)]$State,
        [Parameter(Mandatory)][int]$SpuriousSignals
    )
    [pscustomobject]@{
        wait_result = $Result
        elapsed_ms = [int]$Clock.ElapsedMilliseconds
        spurious_signals = $SpuriousSignals
        state = $State
    } | ConvertTo-Json -Depth 9
}

function Invoke-WaitTurn {
    if (-not $Role) { throw 'ROLE_REQUIRED' }
    if ([string]::IsNullOrWhiteSpace($ExpectedRepo)) { throw 'EXPECTED_REPO_REQUIRED' }
    if ([string]::IsNullOrWhiteSpace($ExpectedRunId)) { throw 'EXPECTED_RUN_ID_REQUIRED' }
    if ($ObservedSeq -lt 0) { throw 'OBSERVED_SEQ_REQUIRED' }
    if ($TimeoutSeconds -lt 1 -or $TimeoutSeconds -gt 3600) {
        throw "WAIT_TIMEOUT_OUT_OF_RANGE: expected=1..3600 actual=$TimeoutSeconds"
    }
    $expected = [System.IO.Path]::GetFullPath($ExpectedRepo)
    if ($expected -ne $repoRoot) {
        throw "REPO_MISMATCH: expected=$expected actual=$repoRoot"
    }

    $timeoutMilliseconds = $TimeoutSeconds * 1000
    $clock = [System.Diagnostics.Stopwatch]::StartNew()
    $wakeEvent = $null
    $repoMutex = $null
    $lastState = $null
    $spuriousSignals = 0
    try {
        $createdNew = $false
        $wakeEvent = [System.Threading.EventWaitHandle]::new(
            $false,
            [System.Threading.EventResetMode]::AutoReset,
            (Get-TurnWakeEventName -RunId $ExpectedRunId -WakeRole $Role),
            [ref]$createdNew
        )
        $mutexName = "Local\mc_double_session_$((Get-Sha256 -Text $repoRoot).Substring(0, 24))"
        $repoMutex = [System.Threading.Mutex]::new($false, $mutexName)

        $lastState = Read-WaitTurnState -RepoMutex $repoMutex -Clock $clock -TimeoutMilliseconds $timeoutMilliseconds
        if ($null -eq $lastState) {
            throw 'WAIT_TURN_INITIAL_STATE_TIMEOUT'
        }
        if (Test-WaitTurnActionable -State $lastState -WaitRole $Role -AfterSeq $ObservedSeq) {
            Write-WaitTurnResult -Result 'state_ready' -Clock $clock -State $lastState -SpuriousSignals 0
            return
        }

        while ($clock.ElapsedMilliseconds -lt $timeoutMilliseconds) {
            $remaining = $timeoutMilliseconds - [int]$clock.ElapsedMilliseconds
            if ($remaining -le 0 -or -not $wakeEvent.WaitOne($remaining)) { break }

            $current = Read-WaitTurnState -RepoMutex $repoMutex -Clock $clock -TimeoutMilliseconds $timeoutMilliseconds
            if ($null -eq $current) { break }
            $lastState = $current
            if (Test-WaitTurnActionable -State $lastState -WaitRole $Role -AfterSeq $ObservedSeq) {
                Write-WaitTurnResult -Result 'signaled' -Clock $clock -State $lastState -SpuriousSignals $spuriousSignals
                return
            }
            $spuriousSignals++
        }

        Write-WaitTurnResult -Result 'timeout' -Clock $clock -State $lastState -SpuriousSignals $spuriousSignals
    }
    finally {
        $clock.Stop()
        if ($null -ne $repoMutex) { $repoMutex.Dispose() }
        if ($null -ne $wakeEvent) { $wakeEvent.Dispose() }
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
    Set-StateProperty -State $State -Name 'version' -Value 6
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

function Get-TempInspection {
    param([switch]$IncludeContent)
    if (-not [System.IO.File]::Exists($tempPath)) {
        return [pscustomobject]@{ exists = $false; length = 0; mtime_utc = ''; sha256 = ''; content = '' }
    }
    $info = [System.IO.FileInfo]::new($tempPath)
    $content = if ($IncludeContent) { [System.IO.File]::ReadAllText($tempPath, $utf8) } else { '' }
    [pscustomobject]@{
        exists = $true
        length = [long]$info.Length
        mtime_utc = $info.LastWriteTimeUtc.ToString('o')
        sha256 = if ($info.Length -eq 0) { '' } else { Get-FileSha256 -Path $tempPath }
        content = $content
    }
}

function Test-TerminalNewTask {
    param([Parameter(Mandatory)]$State, [Parameter(Mandatory)]$Temp)
    if (-not $Temp.exists -or [long]$Temp.length -eq 0) { return $false }
    if (($State.PSObject.Properties.Name -contains 'terminal_temp_sha256') -and
        -not [string]::IsNullOrWhiteSpace([string]$State.terminal_temp_sha256) -and
        [string]$Temp.sha256 -eq [string]$State.terminal_temp_sha256) { return $false }
    $terminalUpdated = [DateTimeOffset]::Parse([string]$State.updated, [Globalization.CultureInfo]::InvariantCulture)
    return [DateTime]::Parse([string]$Temp.mtime_utc, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind) -gt $terminalUpdated.UtcDateTime
}

function Assert-DraftPreparationAllowed {
    param([switch]$RequireNewTask)
    if (-not [string]::IsNullOrWhiteSpace($ExpectedRepo) -and [System.IO.Path]::GetFullPath($ExpectedRepo) -ne $repoRoot) {
        throw "REPO_MISMATCH: expected=$ExpectedRepo actual=$repoRoot"
    }
    $existing = $null
    if ([System.IO.File]::Exists($statePath)) {
        $existing = Read-State
        Assert-RunBinding -State $existing
        if ($existing.status -in @('running', 'paused_budget', 'wait_human')) {
            throw "DRAFT_PREPARATION_ACTIVE_STATE: $($existing.status)"
        }
        if ($existing.status -notin @('done', 'cancelled')) {
            throw "DRAFT_PREPARATION_STATE_INVALID: $($existing.status)"
        }
        if ($RequireNewTask) {
            $temp = Get-TempInspection
            if (-not (Test-TerminalNewTask -State $existing -Temp $temp)) { throw 'NEW_TASK_NOT_DETECTED' }
        }
        $archivePath = Get-RunArchivePath -State $existing
        if (-not [System.IO.File]::Exists($archivePath)) { throw 'TERMINAL_ARCHIVE_REQUIRED' }
    }
    return $existing
}

if ($Action -eq 'ValidateTask') {
    $temp = Get-TempInspection -IncludeContent
    $validation = Get-TaskValidation -Text ([string]$temp.content)
    [pscustomobject]@{ temp = $temp; validation = $validation } | ConvertTo-Json -Depth 8
    exit 0
}

if ($Action -eq 'GoalContract') {
    if (-not $Role) { throw 'ROLE_REQUIRED' }
    if ([string]::IsNullOrWhiteSpace($WorkerToken)) { throw 'WORKER_TOKEN_REQUIRED' }
    if ([string]::IsNullOrWhiteSpace($ExpectedRepo)) { throw 'EXPECTED_REPO_REQUIRED' }
    $expected = [System.IO.Path]::GetFullPath($ExpectedRepo)
    if ($expected -ne $repoRoot) {
        throw "REPO_MISMATCH: expected=$expected actual=$repoRoot"
    }
    $config = Get-DoubleSessionConfig
    $waitSeconds = if ($Role -eq 'coder') {
        [int]$config.coder_interval_seconds
    }
    else {
        [int]$config.planner_interval_seconds
    }
    $runBinding = if ([string]::IsNullOrWhiteSpace($ExpectedRunId)) { 'PENDING' } else { $ExpectedRunId }
    if ($runBinding -eq 'PENDING' -and [string]::IsNullOrWhiteSpace($PreparedTaskSha256)) {
        throw 'PREPARED_TASK_SHA256_REQUIRED'
    }
    $skillPath = Join-Path $env:USERPROFILE ".agents\skills\double-$Role\SKILL.md"
    $protocolPath = Join-Path $env:USERPROFILE '.agents\double-session-common\protocol.md'
    $goalContract = @(
        'DOUBLE_SESSION_GOAL_CONTRACT=v2'
        "repo=$repoRoot"
        "run_id=$runBinding"
        "role=$Role"
        "worker_token=$WorkerToken"
        "prepared_task_sha256=$PreparedTaskSha256"
        "wait_seconds_at_creation=$waitSeconds"
        "live_skill=$skillPath"
        "live_protocol=$protocolPath"
        'CONTINUATION_BOOTSTRAP=Before every Goal continuation and before every state action, fully re-read live_skill and live_protocol, then call BootstrapProbe. The live files override stale workflow prose in this Goal.'
        'TOKEN_RULE=worker_token above is the durable source of truth. Reconstruct it from this objective every turn; tool store() is cache only and may be empty after restart.'
        'RUN_RULE=Reuse repo, role and worker_token exactly. If run_id=PENDING, bind only to the first running or paused_budget run observed in repo; otherwise require the exact run_id.'
        'RESUME_RULE=An explicit Continue Goal, goal resume, Chinese 继续, or re-entered double skill may Recover paused_budget with the bound token, then immediately recheck state.'
        'TERMINAL_RULE=Never complete or block this Goal merely for paused_budget, wait_human, the other role turn, unchanged state, or a missing store cache. Complete only for done or cancelled with no newer task.'
    ) -join [Environment]::NewLine
    if ($CodexJsonEnvelope) {
        [ordered]@{
            envelope       = 'DOUBLE_SESSION_CODEX_GOAL_ENVELOPE=v1'
            repo           = $repoRoot
            run_id         = $runBinding
            role           = $Role
            worker_token   = $WorkerToken
            goal_objective = $goalContract
        } | ConvertTo-Json -Compress
    }
    else {
        $goalContract
    }
    exit 0
}

if ($Action -eq 'WaitTurn') {
    Invoke-WaitTurn
    exit 0
}

$mutexName = "Local\mc_double_session_$((Get-Sha256 -Text $repoRoot).Substring(0, 24))"
$repoMutex = [System.Threading.Mutex]::new($false, $mutexName)
$lockTaken = $false
$wakeRoles = [System.Collections.Generic.List[string]]::new()
$wakeRunId = ''
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
    'BootstrapProbe' {
        $overallClock = [System.Diagnostics.Stopwatch]::StartNew()
        $clock = [System.Diagnostics.Stopwatch]::StartNew()
        $config = Get-DoubleSessionConfig
        $clock.Stop()
        $configMs = [int]$clock.ElapsedMilliseconds

        $clock.Restart()
        $state = $null
        $stateFound = [System.IO.File]::Exists($statePath)
        if ($stateFound) {
            $state = Read-State
            Assert-RunBinding -State $state
        }
        $clock.Stop()
        $stateMs = [int]$clock.ElapsedMilliseconds

        $tempSummary = [pscustomobject]@{ inspected = $false; exists = $false; length = 0; mtime_utc = ''; sha256 = '' }
        $validation = [pscustomobject]@{ marker = $false; valid = $false; missing = @(); task_sha256 = ''; done_when_count = 0; planner_runtime = ''; declared_review_gate = ''; runtime_evidence = '' }
        $route = ''
        $terminalNextRoute = ''
        $tempMs = 0
        $validationMs = 0

        if ($stateFound -and $state.status -in @('running', 'paused_budget', 'wait_human')) {
            $route = switch ([string]$state.status) {
                'wait_human' { 'WAIT_HUMAN_DECISION' }
                default { 'RESUME_RUN' }
            }
        }
        else {
            $clock.Restart()
            $temp = Get-TempInspection -IncludeContent
            $clock.Stop()
            $tempMs = [int]$clock.ElapsedMilliseconds
            $tempSummary = [pscustomobject]@{ inspected = $true; exists = $temp.exists; length = $temp.length; mtime_utc = $temp.mtime_utc; sha256 = $temp.sha256 }
            if ($temp.exists -and [long]$temp.length -gt 0) {
                $clock.Restart()
                $validation = Get-TaskValidation -Text ([string]$temp.content)
                $clock.Stop()
                $validationMs = [int]$clock.ElapsedMilliseconds
            }

            if (-not $stateFound) {
                if (-not $temp.exists -or [long]$temp.length -eq 0) { $route = 'TASK_DRAFT_EMPTY' }
                elseif ($validation.marker -and $validation.valid) { $route = 'CONTRACT_READY' }
                elseif ($validation.marker) { $route = 'TASK_PREFLIGHT_REQUIRED' }
                else { $route = 'PREPARE_DRAFT' }
            }
            elseif ($state.status -in @('done', 'cancelled')) {
                if (-not (Test-TerminalNewTask -State $state -Temp $temp)) { $route = 'TERMINAL_NO_NEW_TASK' }
                else {
                    $route = 'TERMINAL_ARCHIVE_THEN_PREPARE'
                    if ($validation.marker -and $validation.valid) { $terminalNextRoute = 'CONTRACT_READY' }
                    elseif ($validation.marker) { $terminalNextRoute = 'TASK_PREFLIGHT_REQUIRED' }
                    else { $terminalNextRoute = 'PREPARE_DRAFT' }
                }
            }
            else { throw "BOOTSTRAP_STATE_INVALID: $($state.status)" }
        }
        $overallClock.Stop()
        [pscustomobject]@{
            route = $route
            terminal_next_route = $terminalNextRoute
            config = $config
            state_found = $stateFound
            state = $state
            temp = $tempSummary
            task_validation = $validation
            timings_ms = [pscustomobject]@{ config = $configMs; state = $stateMs; temp = $tempMs; validation = $validationMs; total = [int]$overallClock.ElapsedMilliseconds }
        } | ConvertTo-Json -Depth 10
    }

    'ConsumeDraft' {
        [void](Assert-DraftPreparationAllowed -RequireNewTask)
        if (-not [System.IO.File]::Exists($tempPath)) { throw 'TEMP_NOT_FOUND' }
        $draft = [System.IO.File]::ReadAllText($tempPath, $utf8)
        if ([string]::IsNullOrWhiteSpace($draft)) { throw 'TASK_DRAFT_EMPTY' }
        $validation = Get-TaskValidation -Text $draft
        if ($validation.marker) { throw 'CONTRACT_DRAFT_MUST_NOT_BE_CONSUMED' }
        $stream = [System.IO.FileStream]::new($tempPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        try { $stream.SetLength(0); $stream.Flush($true) }
        finally { $stream.Dispose() }
        if (([System.IO.FileInfo]::new($tempPath)).Length -ne 0) { throw 'TEMP_CLEAR_VERIFY_FAILED' }
        $draft
    }

    'CommitContract' {
        [void](Assert-DraftPreparationAllowed)
        if (-not [System.IO.File]::Exists($tempPath)) { throw 'TEMP_NOT_FOUND' }
        $contract = [System.IO.File]::ReadAllText($tempPath, $utf8)
        $validation = Get-TaskValidation -Text $contract
        if (-not $validation.valid) { throw "TASK_PREFLIGHT_REQUIRED: $($validation.missing -join ',')" }
        Write-AtomicText -Path $tempPath -Text $contract
        [pscustomobject]@{ prepared_task_sha256 = (Get-FileSha256 -Path $tempPath); validation = $validation } | ConvertTo-Json -Depth 8
    }

    'ArchiveRun' {
        $state = Read-State
        Assert-RunBinding -State $state
        if ($state.status -notin @('done', 'cancelled')) { throw "ARCHIVE_NOT_TERMINAL: $($state.status)" }
        $archive = Write-RunArchive -State $state
        Set-StateProperty -State $state -Name 'archive_path' -Value ([string]$archive.archive_path)
        Set-StateProperty -State $state -Name 'terminal_archive_sha256' -Value ([string]$archive.sha256)
        Write-State -State $state
        [pscustomobject]@{ archive = $archive; state = $state } | ConvertTo-Json -Depth 9
    }

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
                    $existing.version = 6
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
                $existing.version = 6
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
            $archivePath = Get-RunArchivePath -State $existing
            if (-not [System.IO.File]::Exists($archivePath)) { throw 'TERMINAL_ARCHIVE_REQUIRED' }
        }
        $task = [System.IO.File]::ReadAllText($tempPath, $utf8)
        if ([string]::IsNullOrWhiteSpace($task)) {
            throw 'INITIAL_TASK_EMPTY'
        }
        $taskValidation = Get-TaskValidation -Text $task
        if (-not $taskValidation.valid) { throw "TASK_PREFLIGHT_REQUIRED: $($taskValidation.missing -join ',')" }
        $taskHash = Get-Sha256 -Text $task
        if ([string]::IsNullOrWhiteSpace($PreparedTaskSha256)) { throw 'PREPARED_TASK_SHA256_REQUIRED' }
        if ($PreparedTaskSha256 -ne $taskHash) {
            throw "PREPARED_TASK_MISMATCH: expected=$PreparedTaskSha256 actual=$taskHash"
        }
        if ([string]::IsNullOrWhiteSpace($RuntimeEvidence)) { throw 'RUNTIME_EVIDENCE_REQUIRED' }
        $effectiveReviewGate = Get-EffectiveReviewGate -PlannerRuntime ([string]$taskValidation.planner_runtime) -CoderRuntime $RuntimeClass

        Write-AtomicText -Path $taskPath -Text $task
        Write-AtomicText -Path $messagePath -Text $task
        $state = [ordered]@{
            version = 6
            owner_repo = $repoRoot
            run_id = [guid]::NewGuid().ToString('N')
            status = 'running'
            turn = 'coder'
            seq = 0
            segment = 1
            budget_seconds = $budgetSeconds
            budget_started = [DateTimeOffset]::Now.ToString('o')
            budget_deadline = [DateTimeOffset]::Now.AddSeconds($budgetSeconds).ToString('o')
            task_sha256 = $taskHash
            prepared_task_sha256 = $PreparedTaskSha256
            message_sha256 = $taskHash
            message_seq = 0
            updated = [DateTimeOffset]::Now.ToString('o')
            reason = ''
            resume_turn = ''
            allowed_resolutions = @()
            outcome = ''
            decision_by = ''
            human_approval_id = ''
            failure_ledger = $null
            planner_runtime = [string]$taskValidation.planner_runtime
            coder_runtime = $RuntimeClass
            runtime_evidence = [ordered]@{ planner = [string]$taskValidation.runtime_evidence; coder = $RuntimeEvidence }
            effective_review_gate = $effectiveReviewGate
            review_gate_results = New-ReviewGateResults
            archive_path = ''
            terminal_archive_sha256 = ''
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

    'RefreshBudget' {
        if (-not $Role) { throw 'ROLE_REQUIRED' }
        $state = Read-State
        Assert-RunBinding -State $state
        if ($state.status -notin @('running', 'paused_budget')) {
            throw "REFRESH_BUDGET_NOT_ALLOWED: $($state.status)"
        }
        Assert-WorkerLease -State $state -LeaseRole $Role -Token $WorkerToken
        $config = Get-DoubleSessionConfig
        $nextBudgetSeconds = [int]$config.max_budget_seconds
        if ([int]$state.budget_seconds -eq $nextBudgetSeconds) {
            $state | ConvertTo-Json -Depth 8
            break
        }
        Start-Mutation -State $state -Name 'RefreshBudget' -MutationRole $Role -Token $WorkerToken
        Set-NewBudgetSegment -State $state -Seconds $nextBudgetSeconds
        Set-WorkerLease -State $state -LeaseRole $Role -Token $WorkerToken
        Complete-Mutation -State $state
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }

    'Consume' {
        if (-not $Role) { throw 'ROLE_REQUIRED' }
        $state = Read-State
        Assert-RunBinding -State $state
        Assert-WorkerLease -State $state -LeaseRole $Role -Token $WorkerToken
        if (Test-LastActionReplay -State $state -Name 'Consume' -ActionRole $Role -Token $WorkerToken) {
            Assert-RoleTurn -State $state -ExpectedRole $Role
            if (-not [System.IO.File]::Exists($tempPath)) { throw 'TEMP_NOT_FOUND' }
            if ([int]$state.last_action_seq -ne [int]$state.seq) {
                throw "CONSUME_REPLAY_SEQ_MISMATCH: last_action_seq=$($state.last_action_seq) seq=$($state.seq)"
            }
            $messageSequence = if ($state.PSObject.Properties.Name -contains 'message_seq') { [int]$state.message_seq } else { -1 }
            if ($messageSequence -ne [int]$state.seq) {
                throw "CONSUME_REPLAY_MESSAGE_SEQ_MISMATCH: message_seq=$messageSequence seq=$($state.seq)"
            }
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
            $wakeRunId = [string]$state.run_id
            [void]$wakeRoles.Add([string]$state.turn)
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
        Reset-ReviewGateResults -State $state
        $state.updated = [DateTimeOffset]::Now.ToString('o')
        if (Test-BudgetExpired -State $state) {
            $state.status = 'paused_budget'
            $state.reason = "segment_$($state.segment)_budget_exhausted"
        }
        Complete-Mutation -State $state
        Set-LastAction -State $state -Name 'Handoff' -ActionRole $Role -Token $WorkerToken
        Write-State -State $state
        $wakeRunId = [string]$state.run_id
        [void]$wakeRoles.Add($To)
        $state | ConvertTo-Json -Depth 8
    }

    'RecordGateResult' {
        if ($Role -ne 'planner') { throw 'ONLY_PLANNER_CAN_RECORD_GATE' }
        if (-not $ReviewGateActor) { throw 'REVIEW_GATE_ACTOR_REQUIRED' }
        if (-not $ReviewGateResult) { throw 'REVIEW_GATE_RESULT_REQUIRED' }
        if ([string]::IsNullOrWhiteSpace($ReviewEvidence)) { throw 'REVIEW_EVIDENCE_REQUIRED' }
        if ($ReviewGateResult -eq 'transport_failure' -and $ReviewGateActor -ne 'mc-expert') {
            throw 'TRANSPORT_FAILURE_MC_EXPERT_ONLY'
        }
        if ($ReviewGateResult -eq 'transport_failure' -and [string]::IsNullOrWhiteSpace($ReviewFailureKey)) {
            throw 'REVIEW_FAILURE_KEY_REQUIRED'
        }
        $state = Read-State
        Assert-RunBinding -State $state
        Assert-WorkerLease -State $state -LeaseRole 'planner' -Token $WorkerToken
        Assert-RoleTurn -State $state -ExpectedRole 'planner'
        Assert-FrozenTask -State $state
        if ($ReviewGateActor -eq 'mc-expert' -and $ReviewGateResult -eq 'pass' -and
            [string]$state.review_gate_results.planner.status -ne 'pass') {
            throw 'PLANNER_PASS_REQUIRED_BEFORE_MC_EXPERT'
        }
        Start-Mutation -State $state -Name 'RecordGateResult' -MutationRole 'planner' -Token $WorkerToken
        $now = [DateTimeOffset]::Now.ToString('o')
        $evidenceHash = Get-Sha256 -Text $ReviewEvidence
        if ($ReviewGateActor -eq 'planner') {
            $state.review_gate_results.planner.status = $ReviewGateResult
            $state.review_gate_results.planner.evidence_sha256 = $evidenceHash
            $state.review_gate_results.planner.updated = $now
        }
        else {
            $mc = $state.review_gate_results.mc_expert
            if ($ReviewGateResult -eq 'transport_failure') {
                if ([string]$mc.transport_failure_key -eq $ReviewFailureKey) {
                    $mc.transport_failure_count = [int]$mc.transport_failure_count + 1
                }
                else {
                    $mc.transport_failure_key = $ReviewFailureKey
                    $mc.transport_failure_count = 1
                }
            }
            else {
                $mc.transport_failure_key = ''
                $mc.transport_failure_count = 0
            }
            $mc.status = $ReviewGateResult
            $mc.evidence_sha256 = $evidenceHash
            $mc.updated = $now
        }
        $state.updated = $now
        if ($ReviewGateActor -eq 'mc-expert' -and $ReviewGateResult -eq 'transport_failure' -and
            [int]$state.review_gate_results.mc_expert.transport_failure_count -ge 2) {
            $state.status = 'wait_human'
            $state.resume_turn = 'planner'
            $state.allowed_resolutions = @('continue', 'rework', 'pass', 'cancel')
            $state.human_approval_id = [guid]::NewGuid().ToString('N')
            $state.reason = "mc_expert_transport_failure_fuse:$ReviewFailureKey"
            $state.seq = [int]$state.seq + 1
        }
        Complete-Mutation -State $state
        Set-LastAction -State $state -Name 'RecordGateResult' -ActionRole 'planner' -Token $WorkerToken
        Write-State -State $state
        $state | ConvertTo-Json -Depth 9
    }

    'Done' {
        if ($Role -ne 'planner') { throw 'ONLY_PLANNER_CAN_COMPLETE' }
        $state = Read-State
        Assert-RunBinding -State $state
        Assert-WorkerLease -State $state -LeaseRole $Role -Token $WorkerToken
        if (Test-LastActionReplay -State $state -Name 'Done' -ActionRole $Role -Token $WorkerToken) {
            $wakeRunId = [string]$state.run_id
            [void]$wakeRoles.Add('coder')
            $state | ConvertTo-Json -Depth 8
            break
        }
        Assert-RoleTurn -State $state -ExpectedRole 'planner'
        Assert-FrozenTask -State $state
        if ([string]$state.review_gate_results.planner.status -ne 'pass') {
            throw 'PLANNER_GATE_PASS_REQUIRED'
        }
        if ([string]$state.effective_review_gate -eq 'planner_plus_mc_expert' -and
            [string]$state.review_gate_results.mc_expert.status -ne 'pass') {
            throw 'MC_EXPERT_GATE_PASS_REQUIRED'
        }
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
        $wakeRunId = [string]$state.run_id
        [void]$wakeRoles.Add('coder')
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
        $taskValidation = Get-TaskValidation -Text $task
        if (-not $taskValidation.valid) { throw "TASK_PREFLIGHT_REQUIRED: $($taskValidation.missing -join ',')" }
        if ([string]::IsNullOrWhiteSpace($PreparedTaskSha256)) { throw 'PREPARED_TASK_SHA256_REQUIRED' }
        if ($PreparedTaskSha256 -ne $taskHash) {
            throw "PREPARED_TASK_MISMATCH: expected=$PreparedTaskSha256 actual=$taskHash"
        }
        if ([string]::IsNullOrWhiteSpace($RuntimeEvidence)) { throw 'RUNTIME_EVIDENCE_REQUIRED' }
        $effectiveReviewGate = Get-EffectiveReviewGate -PlannerRuntime ([string]$taskValidation.planner_runtime) -CoderRuntime $RuntimeClass
        if (($existing.PSObject.Properties.Name -contains 'message_sha256') -and
            $taskHash -eq [string]$existing.message_sha256) { throw 'NEW_TASK_NOT_DETECTED' }
        $oldUpdated = [DateTimeOffset]::Parse([string]$existing.updated, [Globalization.CultureInfo]::InvariantCulture)
        if ($tempInfo.LastWriteTimeUtc -le $oldUpdated.UtcDateTime) { throw 'NEW_TASK_NOT_DETECTED' }

        $now = [DateTimeOffset]::Now
        $state = [ordered]@{
            version = 6
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
            prepared_task_sha256 = $PreparedTaskSha256
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
            planner_runtime = [string]$taskValidation.planner_runtime
            coder_runtime = $RuntimeClass
            runtime_evidence = [ordered]@{ planner = [string]$taskValidation.runtime_evidence; coder = $RuntimeEvidence }
            effective_review_gate = $effectiveReviewGate
            review_gate_results = New-ReviewGateResults
            archive_path = ''
            terminal_archive_sha256 = ''
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

    'SafeBootstrapTakeover' {
        if ($Role -ne 'coder') { throw 'SAFE_BOOTSTRAP_TAKEOVER_CODER_ONLY' }
        if ([string]::IsNullOrWhiteSpace($ExpectedRepo)) { throw 'EXPECTED_REPO_REQUIRED' }
        if ([string]::IsNullOrWhiteSpace($ExpectedRunId)) { throw 'EXPECTED_RUN_ID_REQUIRED' }
        $state = Read-State
        Assert-RunBinding -State $state
        if ([string]::IsNullOrWhiteSpace($WorkerToken)) { throw 'WORKER_TOKEN_REQUIRED' }
        $messageSequence = if ($state.PSObject.Properties.Name -contains 'message_seq') { [int]$state.message_seq } else { -1 }
        $coderTokenHash = [string]$state.worker_token_hashes.coder
        $plannerTokenHash = [string]$state.worker_token_hashes.planner
        $safeBoundary =
            [string]$state.status -eq 'running' -and
            [string]$state.turn -eq 'coder' -and
            [int]$state.seq -eq 0 -and
            [string]$state.phase -eq 'ready' -and
            [string]::IsNullOrWhiteSpace([string]$state.last_action) -and
            [string]::IsNullOrWhiteSpace([string]$state.last_action_role) -and
            [string]::IsNullOrWhiteSpace([string]$state.last_action_token_sha256) -and
            [int]$state.last_action_seq -eq -1 -and
            $messageSequence -eq 0 -and
            -not [string]::IsNullOrWhiteSpace($coderTokenHash) -and
            [string]::IsNullOrWhiteSpace([string]$state.mutation_action) -and
            [string]::IsNullOrWhiteSpace([string]$state.mutation_role) -and
            [string]::IsNullOrWhiteSpace([string]$state.mutation_token_sha256) -and
            [string]::IsNullOrWhiteSpace($plannerTokenHash)
        if (-not $safeBoundary) {
            throw "SAFE_BOOTSTRAP_TAKEOVER_BOUNDARY_REQUIRED: status=$($state.status) turn=$($state.turn) seq=$($state.seq) last_action=$($state.last_action) last_role=$($state.last_action_role) last_seq=$($state.last_action_seq) message_seq=$messageSequence phase=$($state.phase)"
        }
        Assert-FrozenTask -State $state
        Assert-MessageSnapshot -State $state
        if ([string]$state.task_sha256 -ne [string]$state.message_sha256) {
            throw "SAFE_BOOTSTRAP_TAKEOVER_SNAPSHOT_MISMATCH: task=$($state.task_sha256) message=$($state.message_sha256)"
        }
        if (-not [System.IO.File]::Exists($tempPath) -or ([System.IO.FileInfo]::new($tempPath)).Length -eq 0) {
            throw 'SAFE_BOOTSTRAP_TAKEOVER_TASK_BODY_MISSING'
        }
        $tempHash = Get-FileSha256 -Path $tempPath
        if ($tempHash -ne [string]$state.message_sha256) {
            throw "SAFE_BOOTSTRAP_TAKEOVER_TASK_MISMATCH: expected=$($state.message_sha256) actual=$tempHash"
        }
        Start-Mutation -State $state -Name 'SafeBootstrapTakeover' -MutationRole 'coder' -Token $WorkerToken
        Set-WorkerLease -State $state -LeaseRole 'coder' -Token $WorkerToken
        $state.updated = [DateTimeOffset]::Now.ToString('o')
        Complete-Mutation -State $state
        Write-State -State $state
        $state | ConvertTo-Json -Depth 8
    }

    'SafeTakeover' {
        if (-not $Role) { throw 'ROLE_REQUIRED' }
        $state = Read-State
        Assert-RunBinding -State $state
        if ([string]::IsNullOrWhiteSpace($WorkerToken)) { throw 'WORKER_TOKEN_REQUIRED' }
        if ($state.status -notin @('running', 'paused_budget')) {
            throw "SAFE_TAKEOVER_NOT_ALLOWED: $($state.status)"
        }
        if ([string]$state.turn -ne $Role) {
            throw "SAFE_TAKEOVER_NOT_ROLE_TURN: expected=$Role actual=$($state.turn)"
        }
        $otherRole = if ($Role -eq 'coder') { 'planner' } else { 'coder' }
        $messageSequence = if ($state.PSObject.Properties.Name -contains 'message_seq') { [int]$state.message_seq } else { -1 }
        $safeBoundary =
            [string]$state.phase -eq 'ready' -and
            [string]$state.last_action -eq 'Handoff' -and
            [string]$state.last_action_role -eq $otherRole -and
            [int]$state.last_action_seq -eq [int]$state.seq -and
            $messageSequence -eq [int]$state.seq
        if (-not $safeBoundary) {
            throw "SAFE_TAKEOVER_BOUNDARY_REQUIRED: turn=$($state.turn) seq=$($state.seq) last_action=$($state.last_action) last_role=$($state.last_action_role) last_seq=$($state.last_action_seq) message_seq=$messageSequence phase=$($state.phase)"
        }
        Assert-FrozenTask -State $state
        Assert-MessageSnapshot -State $state
        if (-not [System.IO.File]::Exists($tempPath) -or ([System.IO.FileInfo]::new($tempPath)).Length -eq 0) {
            throw 'SAFE_TAKEOVER_HANDOFF_BODY_MISSING'
        }
        $tempHash = Get-FileSha256 -Path $tempPath
        if ($tempHash -ne [string]$state.message_sha256) {
            throw "SAFE_TAKEOVER_HANDOFF_MISMATCH: expected=$($state.message_sha256) actual=$tempHash"
        }
        Start-Mutation -State $state -Name 'SafeTakeover' -MutationRole $Role -Token $WorkerToken
        Set-WorkerLease -State $state -LeaseRole $Role -Token $WorkerToken
        $state.updated = [DateTimeOffset]::Now.ToString('o')
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
        $storedTokenHash = [string]$state.worker_token_hashes.$Role
        $presentedTokenHash = Get-Sha256 -Text $WorkerToken
        $tokenMatches =
            -not [string]::IsNullOrWhiteSpace($storedTokenHash) -and
            $storedTokenHash -eq $presentedTokenHash
        if ($Action -eq 'Recover' -and -not $tokenMatches) { throw 'RECOVER_TOKEN_MISMATCH' }
        if ($Action -eq 'Takeover' -and -not $leaseExpired -and -not $explicitTakeover -and -not $tokenMatches) { throw 'WORKER_ACTIVE' }
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
foreach ($wakeRole in @($wakeRoles | Select-Object -Unique)) {
    Send-TurnWakeSignal -RunId $wakeRunId -WakeRole $wakeRole
}
