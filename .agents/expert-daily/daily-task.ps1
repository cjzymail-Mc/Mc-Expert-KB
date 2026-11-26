[CmdletBinding()]
param(
    [ValidateSet('Ensure','Use','Record','Run')][string]$Mode = 'Ensure',
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)*$')][string]$Expert,
    [ValidateSet('codex','codex2')][string]$Launcher,
    [string]$Feedback, [string]$Subject, [string]$Outcome, [string]$Evidence,
    [ValidateSet('automatic','explicit','continued','unclassified')][string]$InvocationSource = 'unclassified',
    [string]$SessionId = $env:CODEX_THREAD_ID
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3

# The global skills folder may be a junction. Store the physical path in the task.
function Get-PhysicalDirectory([string]$Path) {
    $dir = Get-Item -Force -LiteralPath $Path
    if ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        $target = @($dir.Target)[0]
        if (-not $target) { throw "Cannot resolve directory link: $Path" }
        if (-not [IO.Path]::IsPathRooted($target)) { $target = Join-Path $dir.Parent.FullName $target }
        return Get-PhysicalDirectory $target
    }
    if (-not $dir.Parent) { return $dir.FullName }
    return Join-Path (Get-PhysicalDirectory $dir.Parent.FullName) $dir.Name
}

function Write-LocalJson([string]$Path, $Value) {
    $parent = Split-Path -Parent $Path
    [void][IO.Directory]::CreateDirectory($parent)
    $tmp = Join-Path $parent ([guid]::NewGuid().ToString('N') + '.tmp')
    [IO.File]::WriteAllText($tmp, (ConvertTo-Json -InputObject $Value -Depth 5), [Text.UTF8Encoding]::new($false))
    if ($PSVersionTable.PSEdition -eq 'Core') {
        [IO.File]::Move($tmp, $Path, $true)
    } elseif ([IO.File]::Exists($Path)) {
        [IO.File]::Replace($tmp, $Path, [NullString]::Value)
    } else {
        [IO.File]::Move($tmp, $Path)
    }
}

function Get-Key([string]$Value) {
    $hash = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value))).Replace('-','').ToLowerInvariant() }
    finally { $hash.Dispose() }
}

function Read-RegisteredTask($Folder, [string]$Name) {
    try { return $Folder.GetTask($Name) }
    catch {
        if ($_.Exception.GetBaseException().HResult -in @(-2147024894,-2147024893)) { return $null }
        throw
    }
}

function Test-Registration($Task, [string]$Shell, [string]$Arguments) {
    if (-not $Task -or -not $Task.Enabled) { return $false }
    $d = $Task.Definition
    if ($d.Actions.Count -ne 1 -or $d.Triggers.Count -ne 1) { return $false }
    $a = $d.Actions.Item(1)
    $t = $d.Triggers.Item(1)
    if ($a.Type -ne 0 -or $t.Type -ne 2) { return $false }
    $settings = $d.Settings
    return ($d.RegistrationInfo.Description -ceq $ownerLabel -and
        $a.Path -eq $Shell -and $a.Arguments -ceq $Arguments -and $a.WorkingDirectory -eq $serviceDir -and
        $t.Enabled -and $t.DaysInterval -eq 1 -and $t.StartBoundary -match 'T17:00:00$' -and
        [datetime]$t.StartBoundary -le [datetime]::Today.AddHours(17) -and -not $t.EndBoundary -and
        $t.Repetition.Interval -in @($null,'','PT0S') -and $t.RandomDelay -in @($null,'','PT0S') -and
        $d.Principal.LogonType -eq 3 -and $d.Principal.RunLevel -eq 0 -and
        (([xml]$Task.Xml).Task.Principals.Principal.UserId -in @($sid,$identity.Name)) -and
        $settings.StartWhenAvailable -and $settings.MultipleInstances -eq 2 -and
        -not $settings.DisallowStartIfOnBatteries -and -not $settings.StopIfGoingOnBatteries)
}

function Get-ExpertLocal([string]$Name) {
    return Join-Path $skillsDir "$Name\.local\$env:COMPUTERNAME\$sid"
}

function Get-CallSources($Receipt) {
    if ($Receipt.PSObject.Properties['calledAt']) { $count = @($Receipt.calledAt).Count }
    else { $count = 1 }
    $saved = @()
    if ($Receipt.PSObject.Properties['callSources']) { $saved = @($Receipt.callSources) }
    for ($i = 0; $i -lt $count; $i++) {
        if ($i -lt $saved.Count -and $saved[$i] -in @('automatic','explicit','continued')) { [string]$saved[$i] }
        else { 'unclassified' }
    }
}

function Get-DayRegistrationCounts([string]$Dir, [string]$Date) {
    $counts = [ordered]@{automatic=0; explicit=0; continued=0; unclassified=0; unreadableReceipts=0}
    $sessions = Join-Path $Dir 'sessions'
    if ([IO.Directory]::Exists($sessions)) {
        try { $files = [IO.Directory]::GetFiles($sessions, "$Date-*.json") }
        catch { $counts.unreadableReceipts++; return $counts }
        foreach ($file in $files) {
            try {
                $receipt = Get-Content -Raw -Encoding UTF8 -LiteralPath $file | ConvertFrom-Json -ErrorAction Stop
                foreach ($kind in (Get-CallSources $receipt)) { $counts[$kind]++ }
            } catch { $counts.unreadableReceipts++ }
        }
    }
    return $counts
}

function Write-Invocation([string]$Dir) {
    $now = [datetimeoffset]::Now
    $date = $now.ToString('yyyy-MM-dd')
    $project = (Get-Location).ProviderPath
    $entry = Join-Path $Dir ("sessions\$date-" + (Get-Key "$SessionId|$project") + '.json')
    $first = $now.ToString('o')
    $marks = @()
    $sources = @()
    if ([IO.File]::Exists($entry)) {
        $prior = Get-Content -LiteralPath $entry -Raw -Encoding UTF8 | ConvertFrom-Json
        $sources = @(Get-CallSources $prior)
        $first = $prior.firstSeen
        if ($first -is [datetime]) { $first = $first.ToString('o') }
        if ($prior.PSObject.Properties['calledAt']) { $marks = @($prior.calledAt) }
        else { $marks = @($first) }
    }
    if ($Mode -ne 'Record' -or -not $marks.Count) {
        $marks += $now.ToString('o')
        $sources += $InvocationSource
    }
    $call = [ordered]@{expert=$Expert; session=$SessionId; project=$project; date=$date; firstSeen=$first; lastSeen=$now.ToString('o'); calledAt=$marks; callSources=$sources}
    if ($env:CODEX_HOME) { $call.codexHome = $env:CODEX_HOME }
    Write-LocalJson $entry $call
}

$serviceDir = Get-PhysicalDirectory $PSScriptRoot
$agentDir = Split-Path -Parent $serviceDir
$repo = Split-Path -Parent $agentDir
$skillsDir = Join-Path $agentDir 'skills'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$sid = $identity.User.Value
$central = Get-ExpertLocal 'ppt-html-deck'
$marker = Join-Path $central 'registration.json'
$expertNames = @(Get-ChildItem -Directory -LiteralPath $skillsDir | Where-Object {
    [regex]::IsMatch($_.Name,'^[a-z0-9]+(?:-[a-z0-9]+)*$') -and
    [IO.File]::Exists((Join-Path $_.FullName 'daily-task.ps1')) -and
    [IO.File]::Exists((Join-Path $repo ('.codex\agents\' + $_.Name + '.toml')))
} | Sort-Object Name | ForEach-Object Name)
if (($Expert -and $Expert -cnotin $expertNames) -or (-not $Expert -and $Mode -in @('Use','Record'))) {
    throw "Unknown or missing expert: $Expert"
}
# Keep the existing task identity so migration updates the single Windows task in place.
$name = 'PPT-HTML-Deck-DailyReview-' + $sid
$ownerLabel = 'Native Codex expert daily knowledge review'
$lockKind = if ($Mode -eq 'Run') { 'review' } else { 'setup' }
$mutex = [Threading.Mutex]::new($false, "Local\$name-$lockKind")
$locked = $false
try {
    try { $locked = $mutex.WaitOne([TimeSpan]::FromSeconds(15)) }
    catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw "Another $lockKind operation is running." }

    if ($Mode -eq 'Run' -or $Expert) {
        $python = Get-Command python.exe -All -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandType -eq 'Application' -and $_.Source -notmatch '\\Microsoft\\WindowsApps\\python\.exe$'
        } | Select-Object -First 1
        $pythonArgs = @()
        if (-not $python) {
            $python = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
            $pythonArgs = @('-3')
        }
        if (-not $python) { throw 'History collection needs Python 3 (python.exe or py.exe -3) on PATH.' }
        $helper = Join-Path $serviceDir 'session-delta.py'
    }
    if ($Expert) {
        $localDir = Get-ExpertLocal $Expert
        if ($Mode -in @('Use','Ensure','Record')) {
            $nativeHome = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex'
            $sameHome = -not $env:CODEX_HOME -or [IO.Path]::GetFullPath($env:CODEX_HOME).TrimEnd('\','/') -eq $nativeHome
            $nativeSession = $false
            if ($SessionId -and $sameHome) {
                & $python.Source @pythonArgs $helper --check-native-session $SessionId
                if ($LASTEXITCODE -notin @(0,3)) { throw "Session-source check failed ($LASTEXITCODE)." }
                $nativeSession = $LASTEXITCODE -eq 0
            }
            if ($nativeSession) { Write-Invocation $localDir }
            elseif ($Mode -eq 'Record') { throw 'Feedback registration requires a verified native Codex session.' }
        }
    }
    if ($Mode -eq 'Use') { return }

    if ($Mode -eq 'Record') {
        foreach ($field in @($Feedback,$Subject,$Outcome)) {
            if ([string]::IsNullOrWhiteSpace($field)) { throw 'Record requires Feedback, Subject and Outcome.' }
        }
        $project = (Get-Location).ProviderPath
        $record = [ordered]@{session=$SessionId; project=$project; feedback=$Feedback; subject=$Subject; outcome=$Outcome; evidence=$Evidence}
        $id = Get-Key (ConvertTo-Json $record -Compress)
        $pending = Join-Path $localDir "pending\$id.json"
        if (-not ([IO.File]::Exists($pending) -or [IO.File]::Exists((Join-Path $localDir "processed\$id.json")))) {
            $record['historySource'] = 'native-codex'
            $record['id'] = $id
            $record['recordedAt'] = [datetimeoffset]::Now.ToString('o')
            Write-LocalJson $pending $record
        }
        Write-Output "Feedback $id"
        return
    }

    if ($Mode -eq 'Run') {
        if (-not $Launcher) { throw 'Run requires the registered launcher.' }
        $log = Join-Path $central 'last-run.json'
        $report = [ordered]@{historySource='native-codex'; launcher=$Launcher; startedAt=[datetimeoffset]::Now.ToString('o'); state='running'}
        try {
            $report['commandType'] = (Get-Command $Launcher -ErrorAction Stop).CommandType.ToString()
            $items = [Collections.Generic.List[object]]::new()
            $result = [ordered]@{handled=0; deferred=0; invalid=0; unattributed=0; experts=$items}
            $report['result'] = $result
            $failed = @()
            $registrationDate = ([datetimeoffset]::Now).ToString('yyyy-MM-dd')
            $report['registrationDate'] = $registrationDate
            foreach ($role in $expertNames) {
                $dir = Get-ExpertLocal $role
                $item = [ordered]@{expert=$role; state='idle'; handled=0; deferred=0; invalid=0; unattributed=0}
                $item.registrationsToday = Get-DayRegistrationCounts $dir $registrationDate
                $items.Add($item)
                $problems = @()
                try {
                    # The extractor also finds a direct named-role invocation without a skill registration.
                    & $python.Source @pythonArgs $helper --expert $role --local-dir $dir | Out-Host
                    if ($LASTEXITCODE -ne 0) { throw "session-delta exited $LASTEXITCODE" }
                } catch { $problems += $_.Exception.Message }
                try {
                    $counts = & (Join-Path $serviceDir 'review-pending.ps1') -LocalDir $dir -Expert $role -Launcher $Launcher
                    foreach ($k in @('handled','deferred','invalid','unattributed')) { $item[$k] = $counts.$k; $result[$k] += $counts.$k }
                    if ($counts.reviewed) { $item.state='reviewed' }
                    elseif ($item.deferred) { $item.state='waiting-for-evidence' }
                } catch { $problems += $_.Exception.Message }
                if ($problems.Count) {
                    $item.state='failed'
                    $item['error'] = $problems -join ' | '
                    $failed += $role
                }
            }
            if ($failed.Count) { throw ("Daily review incomplete for " + ($failed -join ', ')) }
            $report.state = 'completed'
        } catch {
            $report.state = 'failed'
            $report['error'] = $_.Exception.Message
            throw
        } finally {
            $report['finishedAt'] = [datetimeoffset]::Now.ToString('o')
            Write-LocalJson $log $report
        }
        Write-Output $result
        return
    }

    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $folder = $service.GetFolder('\')
    $registered = Read-RegisteredTask $folder $name
    if ($registered -and $registered.Definition.RegistrationInfo.Description -notin @($ownerLabel,'Codex expert daily knowledge review','ppt-html-deck daily knowledge review')) {
        throw "Task name already belongs to another task: $name"
    }
    $saved = $null
    if (Test-Path -LiteralPath $marker) {
        try {
            $data = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($data.launcher -in @('codex','codex2')) { $saved = $data }
        } catch { Write-Warning 'Unreadable local receipt. Recovering from Task Scheduler.' }
    }
    if (-not $Launcher) {
        if ($saved) { $Launcher = $saved.launcher }
        elseif ($registered -and $registered.Definition.Actions.Item(1).Arguments -match ' -Launcher (codex2|codex)$') { $Launcher = $Matches[1] }
        else { $Launcher = 'codex' }
    }
    if ($Launcher -notin @('codex','codex2')) { throw 'Invalid registered launcher. Run Ensure with an explicit -Launcher.' }
    $null = Get-Command $Launcher -ErrorAction Stop
    $shellName = if ($PSVersionTable.PSEdition -eq 'Core') { 'pwsh.exe' } else { 'powershell.exe' }
    $shell = Join-Path $PSHOME $shellName
    $script = Join-Path $serviceDir 'daily-task.ps1'
    $arguments = '-NoLogo -NonInteractive -WindowStyle Hidden -File "' + $script + '" -Mode Run -Launcher ' + $Launcher
    $changed = -not (Test-Registration $registered $shell $arguments)
    if ($changed) {
        $d = $service.NewTask(0)
        $d.RegistrationInfo.Description = $ownerLabel
        $d.Principal.UserId = $sid
        $d.Principal.LogonType = 3 # InteractiveToken, current logged-on user
        $d.Principal.RunLevel = 0 # LeastPrivilege
        $d.Settings.StartWhenAvailable = $true
        $d.Settings.DisallowStartIfOnBatteries = $false
        $d.Settings.StopIfGoingOnBatteries = $false
        $d.Settings.MultipleInstances = 2 # IgnoreNew
        $d.Settings.ExecutionTimeLimit = 'PT4H'
        $trigger = $d.Triggers.Create(2) # Daily
        $trigger.DaysInterval = 1
        $trigger.StartBoundary = [datetime]::Today.AddHours(17).ToString('yyyy-MM-ddTHH:mm:ss')
        $action = $d.Actions.Create(0) # Exec
        $action.Path = $shell
        $action.Arguments = $arguments
        $action.WorkingDirectory = $serviceDir
        $null = $folder.RegisterTaskDefinition($name,$d,6,$sid,$null,3)
        $registered = Read-RegisteredTask $folder $name
        if (-not (Test-Registration $registered $shell $arguments)) { throw 'Task read-back did not match the daily schedule.' }
    }
    $receipt = [ordered]@{historySource='native-codex'; computer=$env:COMPUTERNAME; userSid=$sid; taskName=$name; localTime='17:00'; launcher=$Launcher; shell=$shell; script=$script}
    if ($changed -or -not $saved -or (ConvertTo-Json $saved -Compress) -cne (ConvertTo-Json $receipt -Compress)) {
        Write-LocalJson $marker $receipt
    }
    if ($Expert -and $Expert -ne 'ppt-html-deck') {
        $roleMarker = Join-Path $localDir 'registration.json'
        if ($changed -or -not [IO.File]::Exists($roleMarker) -or
            [IO.File]::ReadAllText($roleMarker) -cne [IO.File]::ReadAllText($marker)) {
            Write-LocalJson $roleMarker $receipt
        }
    }
    [pscustomobject]@{task=$name; launcher=$Launcher; changed=$changed; nextRun=$registered.NextRunTime; receipt=$marker}
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
