[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidateSet('init','show','recover','select','start','preflight-check','advance','pending-review','review-pass','pass','fail','wait-human','redline','complete')][string]$Action,
  [Parameter(Mandatory=$true)][string]$RunDir,
  [string]$PlanFile,[string]$ContractFile,[string]$PlanId,[string]$From,[string]$Evidence,[string]$Reason,
  [string]$TargetPath,[string]$ProposedAction,[switch]$SimulateCrashAfterEvent
)
$ErrorActionPreference='Stop'

function Full([string]$p){
  if([IO.Path]::IsPathRooted($p)){[IO.Path]::GetFullPath($p)}else{[IO.Path]::GetFullPath((Join-Path (Get-Location) $p))}
}
function RepoRoot {
  $r=(& git rev-parse --show-toplevel 2>$null)
  if($LASTEXITCODE -ne 0){throw 'REPO_ROOT_NOT_FOUND'}
  (Full $r.Trim()).TrimEnd('\','/')
}
$root=RepoRoot
function IsUnder([string]$child,[string]$parent){
  $c=(Full $child).TrimEnd('\','/');$p=(Full $parent).TrimEnd('\','/')
  $c -eq $p -or $c.StartsWith($p+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)
}
function ResolveSafe([string]$p){
  $f=Full $p
  if(!(IsUnder $f $root)){throw "OUTSIDE_REPO:$f"}
  $relative=[IO.Path]::GetRelativePath($root,$f)
  $physical=$root
  foreach($part in $relative.Split([IO.Path]::DirectorySeparatorChar,[StringSplitOptions]::RemoveEmptyEntries)){
    $candidate=Join-Path $physical $part
    if(Test-Path -LiteralPath $candidate){
      $item=Get-Item -Force -LiteralPath $candidate
      if(($item.Attributes-band [IO.FileAttributes]::ReparsePoint)-ne 0){
        $target=@($item.Target)[0]
        if(!$target){throw "REPARSE_TARGET_UNREADABLE:$candidate"}
        if([IO.Path]::IsPathRooted($target)){$physical=Full $target}else{$physical=Full (Join-Path (Split-Path -Parent $candidate) $target)}
        if(!(IsUnder $physical $root)){throw "REPARSE_ESCAPE:$f=>$physical"}
      }else{$physical=$candidate}
    }else{$physical=$candidate}
  }
  if(!(IsUnder $physical $root)){throw "REPARSE_ESCAPE:$f=>$physical"}
  $f
}
function ContractPath([string]$p,[string]$field){
  if(!$p-or [IO.Path]::IsPathRooted($p)){throw "CONTRACT_PATH_NOT_RELATIVE:$field"}
  ResolveSafe (Join-Path $root $p)
}
function Rel([string]$p){[IO.Path]::GetRelativePath($root,(Full $p)).Replace('\','/')}
function Sha([string]$p){(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()}
function Now {[DateTime]::UtcNow.ToString('o')}

$run=ResolveSafe $RunDir
$statePath=Join-Path $run 'state.json';$eventsPath=Join-Path $run 'events.jsonl'
function ReadRawState {
  if(!(Test-Path -LiteralPath $statePath)){throw 'STATE_NOT_FOUND'}
  Get-Content -Raw -Encoding UTF8 -LiteralPath $statePath|ConvertFrom-Json -AsHashtable
}
function Validate($s){
  if($s.schema_version-ne 1){throw 'BAD_SCHEMA'}
  if($s.status-notin @('running','complete','halted','wait_human')){throw 'BAD_RUN_STATUS'}
  if([int]$s.last_event_seq-lt 1){throw 'BAD_EVENT_SEQ'}
  if([int]$s.consecutive_failures-lt 0-or [int]$s.consecutive_failures-gt 2){throw 'BAD_FAILURE_COUNT'}
  foreach($field in @('allowed_paths','read_only_paths','forbidden_actions','human_gates','terminal_evidence')){if($null-eq $s[$field]){throw "STATE_FIELD_MISSING:$field"}}
  foreach($field in @('contract_sha256','plans_sha256')){if([string]$s.frozen_inputs[$field]-notmatch '^[0-9a-f]{64}$'){throw "BAD_FROZEN_HASH:$field"}}
  $active=@($s.plans|Where-Object status -eq 'running')
  if($active.Count-gt 1){throw 'MULTIPLE_ACTIVE'}
  if($active.Count-eq 1-and $s.current_plan-ne $active[0].id){throw 'CURRENT_PLAN_MISMATCH'}
  if($active.Count-eq 0-and $null-ne $s.current_plan){throw 'CURRENT_PLAN_STALE'}
  foreach($p in $s.plans){
    if($p.status-notin @('pending','running','rework','passed','failed','wait_human')){throw 'BAD_PLAN_STATUS'}
    if($p.status-eq 'passed'-and @($p.evidence).Count-eq 0){throw 'PASSED_WITHOUT_EVIDENCE'}
  }
  if([int]$s.consecutive_failures-eq 2-and $s.status-ne 'halted'){throw 'FAILURE_TWO_NOT_HALTED'}
}
function WriteSnapshot($s){
  Validate $s
  $tmp=$statePath+'.tmp'
  $s|ConvertTo-Json -Depth 30|Set-Content -Encoding utf8NoBOM -LiteralPath $tmp
  Move-Item -Force -LiteralPath $tmp -Destination $statePath
  Validate (ReadRawState)
}
function ReadEvents {
  if(!(Test-Path -LiteralPath $eventsPath)){return @()}
  $out=@();$lineNo=0
  foreach($line in @(Get-Content -Encoding UTF8 -LiteralPath $eventsPath)){
    $lineNo++;if([string]::IsNullOrWhiteSpace($line)){continue}
    try{$out+=,($line|ConvertFrom-Json -AsHashtable)}catch{throw "EVENT_LOG_CORRUPT:$lineNo"}
  }
  $out
}
function StateJson($value){$value|ConvertTo-Json -Depth 30 -Compress}
function RecoverState {
  $s=ReadRawState;$events=@(ReadEvents)
  if(!$events.Count){throw 'EVENT_LOG_EMPTY'}
  for($i=0;$i-lt $events.Count;$i++){if([int]$events[$i].seq-ne $i+1){throw 'EVENT_SEQUENCE_GAP'}}
  $last=$events[-1]
  if([int]$s.last_event_seq-gt [int]$last.seq){throw 'STATE_AHEAD_OF_EVENTS'}
  if([int]$s.last_event_seq-lt [int]$last.seq){
    if($null-eq $last.state_after){throw 'EVENT_NOT_REPLAYABLE'}
    $s=$last.state_after;WriteSnapshot $s
  }
  if([int]$s.last_event_seq-eq [int]$last.seq-and (StateJson $s)-cne (StateJson $last.state_after)){throw 'STATE_EVENT_DIVERGENCE'}
  Validate $s;$s
}
function VerifyFrozen($s){
  $cf=ResolveSafe (Join-Path $root $s.frozen_inputs.contract_file)
  $pf=ResolveSafe (Join-Path $root $s.frozen_inputs.plans_file)
  if((Sha $cf)-ne $s.frozen_inputs.contract_sha256){throw 'CONTRACT_HASH_MISMATCH'}
  if((Sha $pf)-ne $s.frozen_inputs.plans_sha256){throw 'PLANS_HASH_MISMATCH'}
}
function Commit($s,[string]$name,$data){
  $events=@(ReadEvents);$seq=$events.Count+1
  $s.last_event_seq=$seq;$s.updated_at=Now;Validate $s
  $record=[ordered]@{seq=$seq;at=Now;event=$name;data=$data;state_after=$s}
  ($record|ConvertTo-Json -Depth 30 -Compress)|Add-Content -Encoding utf8NoBOM -LiteralPath $eventsPath
  if($SimulateCrashAfterEvent){throw 'SIMULATED_CRASH_AFTER_EVENT'}
  WriteSnapshot $s
}
function Plan($s,$id){$m=@($s.plans|Where-Object id -eq $id);if($m.Count-ne 1){throw "PLAN_NOT_FOUND:$id"};$m[0]}
function Mutable($s){if($s.status-ne 'running'){throw "RUN_TERMINAL:$($s.status)"};VerifyFrozen $s}
function StopHuman($s,[string]$why){
  if($s.current_plan){(Plan $s $s.current_plan).status='wait_human'}
  $s.current_plan=$null;$s.status='wait_human';$s.phase='terminal';$s.last_verdict='WAIT_HUMAN'
  Commit $s 'run_wait_human' @{reason=$why};'WAIT_HUMAN'
}

if($Action-eq 'init'){
  if((Test-Path -LiteralPath $statePath)-or !$PlanFile-or !$ContractFile){throw 'INIT_INPUT_INVALID'}
  $pf=ResolveSafe $PlanFile;$cf=ResolveSafe $ContractFile
  $spec=Get-Content -Raw -Encoding UTF8 -LiteralPath $pf|ConvertFrom-Json -AsHashtable
  $c=Get-Content -Raw -Encoding UTF8 -LiteralPath $cf|ConvertFrom-Json -AsHashtable
  if($spec.schema_version-ne 1-or $c.schema_version-ne 1-or $c.mode-ne 'autopilot'){throw 'CONTRACT_INVALID'}
  foreach($field in @('allowed_paths','forbidden_actions','human_gates','terminal_evidence')){if(@($c[$field]).Count-eq 0){throw "CONTRACT_REQUIRED_FIELD:$field"}}
  if($null-eq $c.read_only_paths-or !$c.run_id-or !$c.objective){throw 'CONTRACT_REQUIRED_FIELD'}
  if([int]$c.budgets.max_consecutive_failures-ne 2-or @($spec.plans).Count-eq 0-or @($spec.plans).Count-gt [int]$c.budgets.max_plans){throw 'BUDGET_INVALID'}
  $contractRun=ContractPath $c.run_dir 'run_dir';$contractPlan=ContractPath $c.plan_file 'plan_file'
  if($contractRun-ne $run-or $contractPlan-ne $pf){throw 'CONTRACT_PATH_MISMATCH'}
  foreach($p in @($c.allowed_paths|ForEach-Object {[string]$_})){if($p-match '[*?]'){throw "CONTRACT_PATH_GLOB_UNSUPPORTED:allowed_paths:$p`nallowed_paths/read_only_paths 是字面前缀目录语义（IsUnder 字面匹配），不支持通配符 * 或 ?。要授权整棵子树请写目录本身（如 'path/to/dir'），它会覆盖该目录下所有文件。（注：仅校验 * 和 ?，不校验方括号——它是合法目录名字符，如本 repo 的 [feature-XX-...] 文件夹。）"}}
  foreach($p in @($c.read_only_paths|ForEach-Object {[string]$_})){if($p-match '[*?]'){throw "CONTRACT_PATH_GLOB_UNSUPPORTED:read_only_paths:$p`nallowed_paths/read_only_paths 是字面前缀目录语义（IsUnder 字面匹配），不支持通配符 * 或 ?。要约束整棵子树请写目录本身（如 'path/to/dir'）。"}}
  $allowed=@($c.allowed_paths|ForEach-Object {Rel (ContractPath $_ 'allowed_paths')})
  $readOnly=@($c.read_only_paths|ForEach-Object {Rel (ContractPath $_ 'read_only_paths')})
  foreach($ro in $readOnly){foreach($a in $allowed){if(IsUnder (Join-Path $root $ro) (Join-Path $root $a)){throw 'READ_ONLY_OVERLAPS_ALLOWED'}}}
  $ids=@($spec.plans|ForEach-Object {[string]$_.id});if(($ids|Sort-Object -Unique).Count-ne $ids.Count){throw 'DUPLICATE_PLAN'}
  foreach($p in $spec.plans){if([string]::IsNullOrWhiteSpace([string]$p.done_when)){throw "PLAN_DONE_WHEN_MISSING:$($p.id) -- done_when 是 plan 级客观尺度（JURY 判 PASS 的硬依据），必须写「做完长什么样」的结果状态（非动作清单）。当前缺失/空串/纯空白，init 在 hash 冻结前拒绝冻结。reference 是可选字段可不填。"}}
  $resolved=[Collections.Generic.HashSet[string]]::new()
  while($resolved.Count-lt $ids.Count){$progress=$false;foreach($p in $spec.plans){if($resolved.Contains($p.id)){continue};$ok=$true;foreach($d in @($p.depends_on)){if($d-eq $p.id-or $ids-notcontains $d-or !$resolved.Contains($d)){$ok=$false;break}};if($ok){[void]$resolved.Add($p.id);$progress=$true}};if(!$progress){throw 'DEPENDENCY_INVALID'}}
  New-Item -Force -ItemType Directory -Path $run|Out-Null
  $plans=@();foreach($p in $spec.plans){$plans+=[ordered]@{id=$p.id;title=$p.title;depends_on=@($p.depends_on);done_when=[string]$p.done_when;reference=[string]$p.reference;status='pending';attempts=0;evidence=@();review_evidence=$null;last_error=$null}}
  $s=[ordered]@{schema_version=1;last_event_seq=1;run_id=$c.run_id;objective=$c.objective;allowed_paths=$allowed;read_only_paths=$readOnly;forbidden_actions=@($c.forbidden_actions);human_gates=@($c.human_gates);terminal_evidence=@($c.terminal_evidence);frozen_inputs=[ordered]@{contract_file=Rel $cf;contract_sha256=Sha $cf;plans_file=Rel $pf;plans_sha256=Sha $pf};status='running';phase='select';current_plan=$null;last_verdict=$null;consecutive_failures=0;plans=$plans;created_at=Now;updated_at=Now}
  Validate $s
  $record=[ordered]@{seq=1;at=Now;event='run_initialized';data=@{run_id=$s.run_id};state_after=$s}
  ($record|ConvertTo-Json -Depth 30 -Compress)|Set-Content -Encoding utf8NoBOM -LiteralPath $eventsPath
  if($SimulateCrashAfterEvent){throw 'SIMULATED_CRASH_AFTER_EVENT'}
  WriteSnapshot $s;'RUN_INITIALIZED';exit
}

$s=RecoverState
if($Action-notin @('show','recover')){VerifyFrozen $s}
switch($Action){
  'show'{$s|ConvertTo-Json -Depth 30}
  'recover'{"RECOVERED:$($s.last_event_seq)"}
  'select'{if($s.status-ne 'running'){"RUN_TERMINAL:$($s.status)";break};$a=@($s.plans|Where-Object status -eq 'running');if($a.Count){"ACTIVE_PLAN:$($a[0].id):$($s.phase)";break};$n=$null;foreach($p in $s.plans|Where-Object status -in @('rework','pending')){$ok=$true;foreach($d in $p.depends_on){if((Plan $s $d).status-ne 'passed'){$ok=$false}};if($ok){$n=$p;break}};if($n){"NEXT_PLAN:$($n.id)"}elseif(@($s.plans|Where-Object status -ne 'passed').Count-eq 0){'ALL_PLANS_PASS'}else{'NO_ELIGIBLE_PLAN'}}
  'start'{Mutable $s;if($s.current_plan){throw 'ACTIVE_EXISTS'};$p=Plan $s $PlanId;if($p.status-notin @('pending','rework')){throw 'NOT_STARTABLE'};if([int]$p.attempts-ge 2){throw 'THIRD_ATTEMPT_FORBIDDEN'};foreach($d in $p.depends_on){if((Plan $s $d).status-ne 'passed'){throw 'DEPENDENCY_NOT_PASSED'}};$p.status='running';$p.attempts=[int]$p.attempts+1;$p.review_evidence=$null;$s.current_plan=$p.id;$s.phase='preflight';$s.last_verdict=$null;Commit $s 'plan_started' @{plan=$p.id;attempt=$p.attempts};'PLAN_STARTED'}
  'preflight-check'{Mutable $s;if($s.phase-ne 'preflight'){throw 'NOT_IN_PREFLIGHT'};if(!$TargetPath-or !$ProposedAction){throw 'PREFLIGHT_INPUT_REQUIRED'};if($s.forbidden_actions-contains $ProposedAction){StopHuman $s "FORBIDDEN_ACTION:$ProposedAction";break};if($s.human_gates-contains $ProposedAction){StopHuman $s "HUMAN_GATE:$ProposedAction";break};try{$target=ContractPath $TargetPath 'target_path'}catch{StopHuman $s $_.Exception.Message;break};foreach($ro in $s.read_only_paths){if(IsUnder $target (Join-Path $root $ro)){StopHuman $s "READ_ONLY_PATH:$TargetPath";return}};$inside=$false;foreach($a in $s.allowed_paths){if(IsUnder $target (Join-Path $root $a)){$inside=$true;break}};if(!$inside){StopHuman $s "OUTSIDE_ALLOWED_PATHS:$TargetPath";break};Commit $s 'preflight_passed' @{plan=$s.current_plan;target=$TargetPath;action=$ProposedAction};'PREFLIGHT_PASS'}
  'advance'{Mutable $s;$map=@{preflight='build';build='self_check';self_check='jury'};if($s.phase-ne $From-or !$map.ContainsKey($From)){throw 'PHASE_MISMATCH'};if($From-eq 'preflight'){$events=@(ReadEvents);$ok=@($events|Where-Object {$_.event-eq 'preflight_passed'-and $_.data.plan-eq $s.current_plan});if(!$ok.Count){throw 'PREFLIGHT_EVIDENCE_REQUIRED'}};$s.phase=$map[$From];Commit $s 'phase_advanced' @{plan=$s.current_plan;from=$From;to=$s.phase};"PHASE:$($s.phase)"}
  'pending-review'{Mutable $s;if($s.phase-ne 'jury'){throw 'NOT_IN_JURY'};$s.last_verdict='PENDING';Commit $s 'review_pending' @{plan=$s.current_plan};'REVIEW_PENDING'}
  'review-pass'{Mutable $s;if($s.phase-ne 'jury'-or !$Evidence){throw 'REVIEW_PASS_PRECONDITION'};$ev=ResolveSafe $Evidence;if(!(Test-Path -LiteralPath $ev -PathType Leaf)){throw 'REVIEW_EVIDENCE_NOT_FOUND'};$r=Get-Content -Raw -Encoding UTF8 -LiteralPath $ev|ConvertFrom-Json -AsHashtable;if($r.verdict-ne 'PASS'-or !$r.reviewer_id-or $r.reviewer_id-eq $r.executor_id-or !$r.plan_id-or $r.plan_id-ne $s.current_plan){throw 'REVIEW_EVIDENCE_INVALID'};$p=Plan $s $s.current_plan;$p.review_evidence=Rel $ev;$s.last_verdict='PASS';$s.phase='checkpoint';Commit $s 'review_passed' @{plan=$p.id;evidence=$p.review_evidence};'REVIEW_PASS'}
  'pass'{Mutable $s;if($s.phase-ne 'checkpoint'-or $s.last_verdict-ne 'PASS'-or !$Evidence){throw 'PASS_PRECONDITION'};$ev=ResolveSafe $Evidence;if(!(Test-Path -LiteralPath $ev -PathType Leaf)){throw 'PASS_EVIDENCE_NOT_FOUND'};$p=Plan $s $s.current_plan;if(!$p.review_evidence){throw 'REVIEW_PASS_REQUIRED'};$p.status='passed';$p.evidence=@($p.evidence)+(Rel $ev);$p.last_error=$null;$s.consecutive_failures=0;$s.current_plan=$null;$s.phase='select';Commit $s 'plan_passed' @{plan=$p.id;evidence=Rel $ev};'PLAN_PASSED'}
  'fail'{Mutable $s;if(!$Reason-or !$s.current_plan){throw 'FAIL_PRECONDITION'};$p=Plan $s $s.current_plan;$s.consecutive_failures=[int]$s.consecutive_failures+1;$p.last_error=$Reason;$s.last_verdict='REWORK';$s.current_plan=$null;$s.phase='select';if($s.consecutive_failures-ge 2){$p.status='failed';$s.status='halted';$s.phase='terminal';Commit $s 'run_halted' @{plan=$p.id;reason=$Reason};'AUTOPILOT_STOP'}else{$p.status='rework';Commit $s 'plan_rework' @{plan=$p.id;reason=$Reason};'PLAN_REWORK'}}
  'wait-human'{Mutable $s;if(!$Reason){throw 'REASON_REQUIRED'};StopHuman $s $Reason}
  'redline'{Mutable $s;if(!$Reason){throw 'REASON_REQUIRED'};if($s.current_plan){$p=Plan $s $s.current_plan;$p.status='failed';$p.last_error=$Reason};$s.current_plan=$null;$s.status='halted';$s.phase='terminal';Commit $s 'redline_halt' @{reason=$Reason};'REDLINE_HALTED'}
  'complete'{Mutable $s;if(@($s.plans|Where-Object status -ne 'passed').Count){throw 'NOT_ALL_PASSED'};foreach($relPath in $s.terminal_evidence){$ep=ContractPath $relPath 'terminal_evidence';if(!(IsUnder $ep $run)){throw "TERMINAL_EVIDENCE_OUTSIDE_RUN:$relPath"};if(!(Test-Path -LiteralPath $ep -PathType Leaf)){throw "TERMINAL_EVIDENCE_MISSING:$relPath"}};$s.status='complete';$s.phase='terminal';Commit $s 'run_completed' @{run_id=$s.run_id};'RUN_COMPLETE'}
}
