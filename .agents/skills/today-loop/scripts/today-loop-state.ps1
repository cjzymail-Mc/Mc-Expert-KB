[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('init', 'show', 'select', 'start', 'record-reset', 'record-finalizer', 'pass', 'fail', 'wait-human', 'complete')]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [string]$RunDir,

    [string]$PlanFile,
    [string]$ContractFile,
    [string]$PlanId,
    [string]$Evidence,
    [string]$Reason
)

$ErrorActionPreference = 'Stop'

function Get-UtcNow {
    return [DateTime]::UtcNow.ToString('o')
}

function Resolve-FullPath([string]$PathValue) {
    if ([IO.Path]::IsPathRooted($PathValue)) {
        return [IO.Path]::GetFullPath($PathValue)
    }
    return [IO.Path]::GetFullPath((Join-Path (Get-Location) $PathValue))
}

function Assert-InRepo([string]$FullPath) {
    $repoRoot = (& git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repoRoot)) {
        throw 'REPO_ROOT_NOT_FOUND'
    }
    $repoFull = [IO.Path]::GetFullPath($repoRoot.Trim()).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $candidate = [IO.Path]::GetFullPath($FullPath)
    if (-not $candidate.StartsWith($repoFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "RUN_DIR_OUTSIDE_REPO: $candidate"
    }
}

$runFull = Resolve-FullPath $RunDir
Assert-InRepo $runFull
$statePath = Join-Path $runFull 'state.json'
$eventsPath = Join-Path $runFull 'events.jsonl'

function Write-State([System.Collections.IDictionary]$State) {
    $State.updated_at = Get-UtcNow
    $tempPath = Join-Path $runFull 'state.json.tmp'
    $State | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $tempPath -Encoding utf8NoBOM
    Move-Item -LiteralPath $tempPath -Destination $statePath -Force
}

function Add-Event([string]$Event, [System.Collections.IDictionary]$Data) {
    $record = [ordered]@{
        at = Get-UtcNow
        event = $Event
        data = $Data
    }
    ($record | ConvertTo-Json -Depth 10 -Compress) | Add-Content -LiteralPath $eventsPath -Encoding utf8NoBOM
}

function Read-State {
    if (-not (Test-Path -LiteralPath $statePath)) {
        throw "STATE_NOT_FOUND: $statePath"
    }
    return (Get-Content -Raw -Encoding UTF8 -LiteralPath $statePath | ConvertFrom-Json -AsHashtable)
}

function Find-Plan([System.Collections.IDictionary]$State, [string]$Id) {
    if ([string]::IsNullOrWhiteSpace($Id)) {
        throw 'PLAN_ID_REQUIRED'
    }
    $matches = @($State.plans | Where-Object { $_.id -eq $Id })
    if ($matches.Count -ne 1) {
        throw "PLAN_NOT_FOUND: $Id"
    }
    return $matches[0]
}

function Assert-RunMutable([System.Collections.IDictionary]$State) {
    if ($State.status -ne 'running') {
        throw "RUN_NOT_MUTABLE: $($State.status)"
    }
}

if ($Action -eq 'init') {
    if ([string]::IsNullOrWhiteSpace($PlanFile) -or [string]::IsNullOrWhiteSpace($ContractFile)) {
        throw 'INIT_REQUIRES_PLAN_AND_CONTRACT'
    }
    if (Test-Path -LiteralPath $statePath) {
        throw "STATE_ALREADY_EXISTS: $statePath"
    }

    $planFull = Resolve-FullPath $PlanFile
    $contractFull = Resolve-FullPath $ContractFile
    Assert-InRepo $planFull
    Assert-InRepo $contractFull
    $planSpec = Get-Content -Raw -Encoding UTF8 -LiteralPath $planFull | ConvertFrom-Json -AsHashtable
    $contract = Get-Content -Raw -Encoding UTF8 -LiteralPath $contractFull | ConvertFrom-Json -AsHashtable

    if ($planSpec.schema_version -ne 1 -or $contract.schema_version -ne 1) { throw 'SCHEMA_VERSION_UNSUPPORTED' }
    if ([string]::IsNullOrWhiteSpace([string]$contract.run_id)) { throw 'RUN_ID_REQUIRED' }
    if ($contract.mode -ne 'autopilot') { throw 'CONTRACT_MODE_INVALID' }
    if (@($contract.allowed_paths).Count -eq 0) { throw 'ALLOWED_PATHS_REQUIRED' }
    if (@($contract.human_gates).Count -eq 0) { throw 'HUMAN_GATES_REQUIRED' }
    if (@($contract.terminal_evidence).Count -eq 0) { throw 'TERMINAL_EVIDENCE_REQUIRED' }
    if ($contract.budgets.max_consecutive_failures -ne 2) { throw 'FAILURE_BUDGET_MUST_EQUAL_2' }
    if (@($planSpec.plans).Count -eq 0) { throw 'PLANS_REQUIRED' }
    if (@($planSpec.plans).Count -gt [int]$contract.budgets.max_plans) { throw 'PLAN_BUDGET_EXCEEDED' }

    $contractRunFull = Resolve-FullPath ([string]$contract.run_dir)
    $contractPlanFull = Resolve-FullPath ([string]$contract.plan_file)
    Assert-InRepo $contractRunFull
    Assert-InRepo $contractPlanFull
    if (-not $contractRunFull.Equals($runFull, [StringComparison]::OrdinalIgnoreCase)) { throw 'CONTRACT_RUN_DIR_MISMATCH' }
    if (-not $contractPlanFull.Equals($planFull, [StringComparison]::OrdinalIgnoreCase)) { throw 'CONTRACT_PLAN_FILE_MISMATCH' }
    foreach ($allowedPath in @($contract.allowed_paths)) {
        Assert-InRepo (Resolve-FullPath ([string]$allowedPath))
    }

    $ids = @($planSpec.plans | ForEach-Object { [string]$_.id })
    if (@($ids | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -gt 0) { throw 'PLAN_ID_EMPTY' }
    if (@($ids | Sort-Object -Unique).Count -ne $ids.Count) { throw 'PLAN_ID_DUPLICATE' }
    foreach ($plan in $planSpec.plans) {
        if ([string]::IsNullOrWhiteSpace([string]$plan.done_when)) { throw "PLAN_DONE_WHEN_REQUIRED: $($plan.id)" }
        foreach ($dependency in @($plan.depends_on)) {
            if ($dependency -eq $plan.id) { throw "PLAN_SELF_DEPENDENCY: $($plan.id)" }
            if ($ids -notcontains $dependency) { throw "PLAN_DEPENDENCY_MISSING: $dependency" }
        }
    }

    $resolved = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    while ($resolved.Count -lt $ids.Count) {
        $progress = $false
        foreach ($plan in $planSpec.plans) {
            if ($resolved.Contains([string]$plan.id)) { continue }
            $ready = $true
            foreach ($dependency in @($plan.depends_on)) {
                if (-not $resolved.Contains([string]$dependency)) { $ready = $false; break }
            }
            if ($ready) { [void]$resolved.Add([string]$plan.id); $progress = $true }
        }
        if (-not $progress) { throw 'PLAN_DEPENDENCY_CYCLE' }
    }

    New-Item -ItemType Directory -Path $runFull -Force | Out-Null
    $statePlans = @()
    foreach ($plan in $planSpec.plans) {
        $statePlans += [ordered]@{
            id = [string]$plan.id
            title = [string]$plan.title
            depends_on = @($plan.depends_on)
            done_when = [string]$plan.done_when
            reference = [string]$plan.reference
            status = 'pending'
            attempts = 0
            reset_count = 0
            finalizer_count = 0
            evidence = @()
            last_error = $null
        }
    }
    $state = [ordered]@{
        schema_version = 1
        run_id = [string]$contract.run_id
        status = 'running'
        contract_path = $contractFull
        plan_file = $planFull
        consecutive_failures = 0
        created_at = Get-UtcNow
        updated_at = Get-UtcNow
        plans = $statePlans
    }
    Write-State $state
    Add-Event 'run_initialized' @{ run_id = $state.run_id; plan_count = $state.plans.Count }
    Write-Output "RUN_INITIALIZED:$($state.run_id)"
    exit 0
}

$state = Read-State

switch ($Action) {
    'show' {
        $state | ConvertTo-Json -Depth 20
    }
    'select' {
        if ($state.status -eq 'complete') { Write-Output 'ALL_PLANS_PASS'; break }
        if ($state.status -ne 'running') { Write-Output "RUN_TERMINAL:$($state.status)"; break }
        $active = @($state.plans | Where-Object { $_.status -eq 'running' })
        if ($active.Count -gt 1) { throw 'MULTIPLE_ACTIVE_PLANS' }
        if ($active.Count -eq 1) { Write-Output "ACTIVE_PLAN:$($active[0].id)"; break }
        $candidate = $null
        foreach ($plan in @($state.plans | Where-Object { $_.status -in @('rework', 'pending') })) {
            $ready = $true
            foreach ($dependency in @($plan.depends_on)) {
                $depPlan = Find-Plan $state $dependency
                if ($depPlan.status -ne 'passed') { $ready = $false; break }
            }
            if ($ready) { $candidate = $plan; break }
        }
        if ($null -eq $candidate) {
            if (@($state.plans | Where-Object { $_.status -ne 'passed' }).Count -eq 0) { Write-Output 'ALL_PLANS_PASS' }
            else { Write-Output 'NO_ELIGIBLE_PLAN' }
        } else {
            Write-Output "NEXT_PLAN:$($candidate.id)"
        }
    }
    'start' {
        Assert-RunMutable $state
        if (@($state.plans | Where-Object { $_.status -eq 'running' }).Count -gt 0) { throw 'ACTIVE_PLAN_ALREADY_EXISTS' }
        $plan = Find-Plan $state $PlanId
        if ($plan.status -notin @('pending', 'rework')) { throw "PLAN_NOT_STARTABLE: $($plan.status)" }
        foreach ($dependency in @($plan.depends_on)) {
            if ((Find-Plan $state $dependency).status -ne 'passed') { throw "DEPENDENCY_NOT_PASSED: $dependency" }
        }
        $plan.status = 'running'
        $plan.attempts = [int]$plan.attempts + 1
        $plan.reset_count = 0
        $plan.finalizer_count = 0
        Write-State $state
        Add-Event 'plan_started' @{ plan_id = $plan.id; attempt = $plan.attempts }
        Write-Output "PLAN_STARTED:$($plan.id):$($plan.attempts)"
    }
    'record-reset' {
        Assert-RunMutable $state
        $plan = Find-Plan $state $PlanId
        if ($plan.status -ne 'running') { throw 'PLAN_NOT_RUNNING' }
        if ([int]$plan.reset_count -ne 0) { throw 'RESET_ALREADY_RECORDED' }
        $plan.reset_count = 1
        Write-State $state
        Add-Event 'reset_recorded' @{ plan_id = $plan.id; attempt = $plan.attempts }
        Write-Output "RESET_RECORDED:$($plan.id)"
    }
    'record-finalizer' {
        Assert-RunMutable $state
        $plan = Find-Plan $state $PlanId
        if ($plan.status -ne 'running') { throw 'PLAN_NOT_RUNNING' }
        if ([int]$plan.finalizer_count -ne 0) { throw 'FINALIZER_ALREADY_RECORDED' }
        $plan.finalizer_count = 1
        Write-State $state
        Add-Event 'finalizer_recorded' @{ plan_id = $plan.id; attempt = $plan.attempts }
        Write-Output "FINALIZER_RECORDED:$($plan.id)"
    }
    'pass' {
        Assert-RunMutable $state
        $plan = Find-Plan $state $PlanId
        if ($plan.status -ne 'running') { throw 'PLAN_NOT_RUNNING' }
        if ([int]$plan.reset_count -ne 1) { throw 'RESET_COUNT_NOT_ONE' }
        if ([int]$plan.finalizer_count -ne 1) { throw 'FINALIZER_COUNT_NOT_ONE' }
        if ([string]::IsNullOrWhiteSpace($Evidence)) { throw 'EVIDENCE_REQUIRED' }
        $plan.status = 'passed'
        $plan.evidence = @($plan.evidence) + $Evidence
        $plan.last_error = $null
        $state.consecutive_failures = 0
        Write-State $state
        Add-Event 'plan_passed' @{ plan_id = $plan.id; evidence = $Evidence }
        Write-Output "PLAN_PASSED:$($plan.id)"
    }
    'fail' {
        Assert-RunMutable $state
        $plan = Find-Plan $state $PlanId
        if ($plan.status -ne 'running') { throw 'PLAN_NOT_RUNNING' }
        if ([string]::IsNullOrWhiteSpace($Reason)) { throw 'FAIL_REASON_REQUIRED' }
        $state.consecutive_failures = [int]$state.consecutive_failures + 1
        $plan.last_error = $Reason
        if ([int]$state.consecutive_failures -ge 2) {
            $plan.status = 'failed'
            $state.status = 'halted'
            Write-State $state
            Add-Event 'run_halted' @{ plan_id = $plan.id; consecutive_failures = $state.consecutive_failures; reason = $Reason }
            Write-Output "AUTOPILOT_STOP:$($plan.id):2"
            exit 2
        }
        $plan.status = 'rework'
        Write-State $state
        Add-Event 'plan_rework' @{ plan_id = $plan.id; consecutive_failures = $state.consecutive_failures; reason = $Reason }
        Write-Output "PLAN_REWORK:$($plan.id):1"
    }
    'wait-human' {
        Assert-RunMutable $state
        $plan = Find-Plan $state $PlanId
        if ($plan.status -ne 'running') { throw 'PLAN_NOT_RUNNING' }
        if ([string]::IsNullOrWhiteSpace($Reason)) { throw 'WAIT_REASON_REQUIRED' }
        $plan.status = 'wait_human'
        $plan.last_error = $Reason
        $state.status = 'wait_human'
        Write-State $state
        Add-Event 'run_wait_human' @{ plan_id = $plan.id; reason = $Reason }
        Write-Output "WAIT_HUMAN:$($plan.id)"
    }
    'complete' {
        Assert-RunMutable $state
        if (@($state.plans | Where-Object { $_.status -ne 'passed' }).Count -ne 0) { throw 'NOT_ALL_PLANS_PASSED' }
        $state.status = 'complete'
        Write-State $state
        Add-Event 'run_completed' @{ run_id = $state.run_id; plan_count = $state.plans.Count }
        Write-Output "RUN_COMPLETE:$($state.run_id)"
    }
}

