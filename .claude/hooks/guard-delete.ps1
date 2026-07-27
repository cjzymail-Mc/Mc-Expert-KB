# guard-delete.ps1 — PreToolUse 安全网（L3：AST 结构化识别 + 包装类删除/破坏性 git + 临时目录放行 + 正则兜底）
# 作用：扫描 Bash/PowerShell 工具调用的命令串，识别"真正的删除/破坏动作"就强制弹确认（ask）。
# 为什么需要：方案 A 的 settings `ask` 规则是「命令开头前缀匹配」，把 Remove-Item/rm
#   包进 foreach/脚本/管道（开头变成 $f= 之类）就会绕过 → 静默删除。
#
# L2→L3 升级（2026-07-03，见 plan-权限守卫升级-2026-07-03.md）：在 L2「AST 只看命令名」基础上补四块——
#   a. 包装命令参数扫描：find/xargs/cmd/sh/bash/pwsh/python… 命中时对参数串跑删除正则（堵内嵌删除）。
#   b. 破坏性 git：git reset --hard / clean -f / checkout -- / restore / push --force / filter-branch → ask。
#   c. 临时目录字面路径自动放行：删除动词命中后走四重闸门（纯字面量/绝对路径+白名单根/规范化再比对/reparse 检查），
#      全过才放行，任一拿不准 → 照常 ask（误判只朝"多弹"掉）。减打扰项、自研 fail-safe。
#   d. 回退正则同步：AST 解析失败时的全文兜底补上 find -delete / rmtree / xargs rm / 破坏性 git。
#
# L3.1 升级（2026-07-04，修 hooks BACKLOG #4）：AST 解析失败（多为 bash 特有语法 for/do/heredoc）时
#   不再对整条原始字符串裸跑删除正则——改「剥引号字面量 + 按分隔符切段 + 只判命令位置 token」的轻量分词，
#   消掉 grep 搜索词 / echo 标签 / --note 文本里字面 rm 的误弹；命令位置命中包装命令（bash/sh/xargs…）时
#   连引号内容一起按 wrapperPatterns 扫，保住 `bash -c "rm x"` 类内嵌真删除。分词自身抛错 → 回落旧全文裸正则。
#
# L2 与旧 L1 的区别（2026-06-09）：L1 对命令全文跑 substring 正则，把 `find -name "*RD*"` 里的
#   字符串字面量 RD 误判成删除；L2 先解析 AST，只在命令位置找删除动词，消除该类误报，仍抓 foreach { Remove-Item }。
# 边界：防「误包」不防「故意混淆」（base64/别名/变量间接 `& $var` 仍可绕）。
#   fail-open + 诊断日志：脚本自身出错 exit 0 放行（绝不阻断会话），但写一行 hooks-error.log 到账号根（有迹可查，
#   见末尾 catch 块）。B 模式判定 Test-BModeActive 是 fail-closed（拿不准退回 ask 多弹，方向=拦），两者别混。

# ---- 白名单根（改动 1c）：只有绝对路径落在这些根之下的字面量删除才自动放行 ----
$script:WhitelistRoots = @(
  'C:\Users\xy198\AppData\Local\Temp\claude\'
)
if ($env:TEMP) {
  $t = $env:TEMP
  if (-not $t.EndsWith('\')) { $t += '\' }
  $script:WhitelistRoots += $t
}

# 单条字面路径是否落在白名单内（绝对 + 规范化 + 前缀 + reparse 检查全过才 true；任一拿不准 false=弹）
function Test-PathWhitelisted {
  param([string]$Raw)
  if ([string]::IsNullOrWhiteSpace($Raw)) { return $false }
  try {
    # 闸门2：必须完全限定的绝对路径（相对路径 / `/c/...` bash 风格一律 false）
    if (-not [System.IO.Path]::IsPathFullyQualified($Raw)) { return $false }
    # 闸门3：规范化还原 `..` 穿越后再比对
    $full = [System.IO.Path]::GetFullPath($Raw)
  } catch { return $false }

  $matchedRoot = $null
  foreach ($root in $script:WhitelistRoots) {
    if ($full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { $matchedRoot = $root; break }
  }
  if (-not $matchedRoot) { return $false }

  # 闸门4：目标路径链上（root 及以下）存在 reparse point（junction/符号链接）→ false，
  #   堵"临时目录里埋 junction 指向真实目录再递归删"。
  try {
    $check = $full
    while ($check -and $check.Length -ge $matchedRoot.Length) {
      if (Test-Path -LiteralPath $check) {
        $item = Get-Item -LiteralPath $check -Force -ErrorAction Stop
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { return $false }
      }
      $parent = [System.IO.Path]::GetDirectoryName($check)
      if (-not $parent -or $parent -eq $check) { break }
      $check = $parent
    }
  } catch { return $false }

  return $true
}

# 某个删除动词 CommandAst 是否可白名单放行（闸门1：所有非 flag 参数均为纯字面量，且每条都在白名单内）
function Test-DeleteCommandWhitelisted {
  param($CmdAst)
  $paths = @()
  $elements = $CmdAst.CommandElements
  for ($i = 1; $i -lt $elements.Count; $i++) {
    $el = $elements[$i]
    if ($el -is [System.Management.Automation.Language.CommandParameterAst]) { continue }  # flag（-Recurse/-Path…）
    if ($el -is [System.Management.Automation.Language.StringConstantExpressionAst]) {
      $paths += $el.Value
    } else {
      return $false  # 变量/可扩展串/数组/子表达式 → 静态分析不知运行时指向 → 弹
    }
  }
  if ($paths.Count -eq 0) { return $false }  # 没有可判定的字面路径 → 弹
  foreach ($p in $paths) {
    if (-not (Test-PathWhitelisted $p)) { return $false }
  }
  return $true
}

# P0 清标记窄例外（2026-07-21，codex 终审会话约束版）：B 模式收尾清"自己"标记文件的 rm 会走同一 hook，
#   此时标记还在 → Test-BModeActive 判 B → deny → 清不掉 = 死锁。解：给"删标记自身"开极窄 allow 例外。
#   ★会话约束（codex 终审）：本函数只判"命令形态 + 目标路径形态"，不判"是不是当前 B 会话的标记"——
#     后者由判决段在 Test-BModeActive 之后用 sid 比对（仅 $isClearMarker -and $bMode 才放行）。
#     这样非 B 会话发同样命令清不掉 B 标记（走 ask），只有当前 B 会话能清自己那张。
#   判据（全满足才返回目标路径，任一不满足返回 $null → 不是清标记候选，照常走主判决）：
#   ① 命令是孤立 Remove-Item（命令名直接是删除动词，不包在 find/xargs/bash 包装里）；
#   ② 所有非 flag 参数是纯字面量 StringConstantExpression（无变量/可扩展串/子表达式）；
#   ③ 所有路径参数规范化后都落在 CLAUDE_CONFIG_DIR\.b-mode-active\ 目录下（无通配、无 .. 穿越、无目录外目标）；
#   ④ 无 -Recurse（清单个标记文件不需递归）。
#   ⑤ 目标文件本身不是 reparse point（防 .b-mode-active\<sid>.json 被换成 junction 指向别处，删它顺删目标）。
#   返回：合法时返回规范化后的目标路径（供判决段和"自己标记路径"比对）；否则 $null。
function Get-ClearMarkerTarget {
  param($CmdAst)
  try {
    $configDir = $env:CLAUDE_CONFIG_DIR
    if ([string]::IsNullOrWhiteSpace($configDir)) { return $null }
    $markerDirFull = [System.IO.Path]::GetFullPath((Join-Path $configDir '.b-mode-active'))
    # 尾部加分隔符，便于 StartsWith 判"落在目录内"
    if (-not $markerDirFull.EndsWith([System.IO.Path]::DirectorySeparatorChar)) { $markerDirFull += [System.IO.Path]::DirectorySeparatorChar }
    $elements = $CmdAst.CommandElements
    $targets = @()
    for ($i = 1; $i -lt $elements.Count; $i++) {
      $el = $elements[$i]
      if ($el -is [System.Management.Automation.Language.CommandParameterAst]) {
        $pText = [string]$el.Extent.Text
        if ($pText -match '-Recurse') { return $null }  # 清标记不该递归
        continue
      }
      if ($el -is [System.Management.Automation.Language.StringConstantExpressionAst]) {
        $p = $el.Value
        $pFull = $null
        try { $pFull = [System.IO.Path]::GetFullPath($p) } catch { return $null }
        if ([string]::IsNullOrEmpty($pFull)) { return $null }
        # 必须落在 .b-mode-active\ 目录内（含 .. 穿越会被 GetFullPath 规范化后跑出目录 → StartsWith 失败）
        if (-not $pFull.StartsWith($markerDirFull, [System.StringComparison]::OrdinalIgnoreCase)) { return $null }
        # 闸门⑤：目标文件本身不能是 reparse point（防被换成 junction/symlink 删到别处）
        if (Test-Path -LiteralPath $pFull) {
          $item = Get-Item -LiteralPath $pFull -Force -ErrorAction Stop
          if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { return $null }
        }
        $targets += $pFull
      } else {
        return $null  # 变量/可扩展串/数组/子表达式 → 静态不知指向 → 不当例外
      }
    }
    if ($targets.Count -eq 0) { return $null }  # 没有路径参数 → 不是清标记
    # 多目标只要都落在标记目录内，返回所有（判决段会逐个和"自己的标记路径"比对，全对才放行）
    return $targets
  } catch {
    return $null
  }
}

# 剥引号字面量（L3.1）：把 '...' 与 "..."（含 \" 转义）的内容替换为单个空格，
#   供 AST 失败兜底分词只看引号外文本——grep 搜索词 / --note 文本 / 带引号标签即被摘除。
#   未闭合引号：吞到串尾（宁可少看，后续包装命令扫描仍看原文，不失守）。
function Get-StrippedCommand {
  param([string]$s)
  $sb = [System.Text.StringBuilder]::new()
  $i = 0
  while ($i -lt $s.Length) {
    $ch = $s[$i]
    if ($ch -eq "'") {
      $i++
      while ($i -lt $s.Length -and $s[$i] -ne "'") { $i++ }
      $i++
      [void]$sb.Append(' ')
    }
    elseif ($ch -eq '"') {
      $i++
      while ($i -lt $s.Length -and $s[$i] -ne '"') {
        if ($s[$i] -eq '\' -and ($i + 1) -lt $s.Length) { $i++ }
        $i++
      }
      $i++
      [void]$sb.Append(' ')
    }
    else { [void]$sb.Append($ch); $i++ }
  }
  return $sb.ToString()
}

try {
  $raw = [Console]::In.ReadToEnd()
  if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
  $data = $raw | ConvertFrom-Json
  $cmd = [string]$data.tool_input.command
  if ([string]::IsNullOrWhiteSpace($cmd)) { exit 0 }

  # 删除动词（命令名层面，-contains 对字符串大小写不敏感）
  $deleteVerbs = @('Remove-Item', 'rm', 'rmdir', 'rd', 'del', 'erase', 'ri')

  # 内嵌解释器/脚本语言共用的删除模式（改动 1a）
  $langPatterns = @('rmtree', 'os\.remove', 'os\.unlink', '\.unlink\(', 'rmSync', 'unlinkSync', 'FileUtils\.rm')
  $wrapperPatterns = @{
    'find'       = @('-delete', '-exec\s+rm')
    'xargs'      = @('\brm\b', '\brmdir\b', 'Remove-Item')
    'cmd'        = @('\bdel\b', '\brd\b', '\berase\b', '\brmdir\b')
    'sh'         = @('\brm\b', 'Remove-Item', '\brmdir\b', '\bdel\b')
    'bash'       = @('\brm\b', 'Remove-Item', '\brmdir\b', '\bdel\b')
    'pwsh'       = @('\brm\b', 'Remove-Item', '\brmdir\b', '\bdel\b')
    'powershell' = @('\brm\b', 'Remove-Item', '\brmdir\b', '\bdel\b')
    'python'     = $langPatterns
    'python3'    = $langPatterns
    'py'         = $langPatterns
    'node'       = $langPatterns
    'perl'       = $langPatterns
    'ruby'       = $langPatterns
  }

  # 破坏性 git（改动 1b；restore 特判排除 --staged）
  $gitPatterns = @(
    '\breset\b.*--hard',
    '\bclean\b.*-[a-zA-Z]*f',
    '\bcheckout\b\s+--(\s|$)',
    '\bpush\b.*(--force\b|--force-with-lease|-f\b)',
    '\bfilter-branch\b'
  )

  # 全文正则兜底（仅 AST 解析失败时启用，改动 1d 已同步补充）
  $fallbackPatterns = @(
    'Remove-Item', '\brm\b', '\brmdir\b', '\bdel\b', '\brd\b',
    '\[IO\.File\]::Delete', '\[System\.IO\.(File|Directory)\]::Delete',
    'find .*-delete', 'rmtree', 'xargs .*\brm\b',
    'git +(reset +--hard|clean +-\w*f|push +.*--force)'
  )

  $hitReason = $null
  $clearMarkerTargets = $null  # P0 清标记候选目标列表（非空 = 这条命令是"清 .b-mode-active 目录内文件"形态）

  # ---- L3：AST 结构化识别 ----
  $tokens = $null; $errors = $null
  $ast = [System.Management.Automation.Language.Parser]::ParseInput($cmd, [ref]$tokens, [ref]$errors)

  if ($errors -and $errors.Count -gt 0) {
    # 解析失败（多为 bash 特有语法）→ L3.1 轻量分词兜底：剥引号 + 切段 + 只判命令位置 token。
    # 判据向结构化主路径对齐；分词自身抛错 → catch 回落旧全文裸正则（误判只朝"多弹"掉）。
    try {
      $stripped = Get-StrippedCommand $cmd
      $skipWords = @('do', 'then', 'else', 'elif', 'if', 'while', 'until', 'for', 'time', 'sudo', 'command', 'exec', 'builtin', 'nohup', '!')
      foreach ($seg in ($stripped -split '[;&|(){}`]|\r?\n')) {
        # 命令位置 token：跳过控制关键字 / VAR=x 赋值前缀 / 切段产生的游离 flag
        $cmdTok = $null
        foreach ($t in ($seg.Trim() -split '\s+')) {
          if (-not $t) { continue }
          if ($skipWords -contains $t.ToLowerInvariant()) { continue }
          if ($t -match '^[A-Za-z_][A-Za-z0-9_]*=') { continue }
          if ($t.StartsWith('-')) { continue }
          $cmdTok = $t; break
        }
        if (-not $cmdTok) { continue }
        $leaf = ($cmdTok -split '[\\/]')[-1] -replace '\.exe$', ''
        $lname = $leaf.ToLowerInvariant()

        # 1) 命令位置是删除动词 → ask（不走白名单放行：bash 语法段无 AST，静态判不了路径字面量）
        if ($deleteVerbs -contains $lname) {
          $hitReason = "命令含删除动作(AST 解析失败，分词兜底：命令位置 '$cmdTok')，强制确认。"
          break
        }
        # 2) 命令位置是包装命令 → 连引号内容一起对全文扫（堵 bash -c "rm x" 类内嵌删除；
        #    包装命令在场时宁可多弹，不因剥引号漏拦）
        if ($wrapperPatterns.ContainsKey($lname)) {
          foreach ($p in $wrapperPatterns[$lname]) {
            if ($cmd -match $p) { $hitReason = "命令含包装类删除(AST 解析失败，分词兜底：$lname 全文匹配 /$p/)，强制确认。"; break }
          }
          if ($hitReason) { break }
        }
        # 3) 破坏性 git（对剥引号后的本段扫）
        if ($lname -eq 'git') {
          foreach ($p in $gitPatterns) {
            if ($seg -match $p) { $hitReason = "命令含破坏性 git(AST 解析失败，分词兜底匹配 /$p/)，强制确认。"; break }
          }
          if ($hitReason) { break }
        }
      }
      # 4) 引号外的 .NET 删除调用 / rmtree / find -delete 直书（不占命令位置也要抓）
      if (-not $hitReason) {
        foreach ($p in @('\[IO\.File\]::Delete', '\[System\.IO\.(File|Directory)\]::Delete', '\brmtree\b', 'find .*-delete')) {
          if ($stripped -match $p) { $hitReason = "命令含删除/破坏动作(AST 解析失败，剥引号后匹配 /$p/)，强制确认。"; break }
        }
      }
    } catch {
      # 分词兜底自身出错 → 回退全文正则（保护不掉线）
      foreach ($p in $fallbackPatterns) {
        if ($cmd -match $p) { $hitReason = "命令含删除/破坏动作(AST 解析失败，全文正则兜底匹配 /$p/)，强制确认。"; break }
      }
    }
  }
  else {
    $cmdAsts = $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.CommandAst] }, $true)
    foreach ($c in $cmdAsts) {
      $name = $c.GetCommandName()
      if (-not $name) { continue }
      $leaf = [System.IO.Path]::GetFileName($name)
      if ($leaf) { $leaf = $leaf -replace '\.exe$', '' }
      $lname = if ($leaf) { $leaf.ToLowerInvariant() } else { $name.ToLowerInvariant() }

      # 参数串（命令名之后全部，供正则扫描）
      $argText = ''
      if ($c.CommandElements.Count -gt 1) {
        $argText = ($c.CommandElements[1..($c.CommandElements.Count - 1)] | ForEach-Object { $_.Extent.Text }) -join ' '
      }

      # 1) 直接删除动词 → 先试白名单放行；再试 P0 清标记候选（不直接放行，记目标进判决段判 B）
      if ($deleteVerbs -contains $lname) {
        if (Test-DeleteCommandWhitelisted $c) { continue }
        $cmt = Get-ClearMarkerTarget $c
        if ($cmt) {
          # P0 候选：形态像"清 .b-mode-active 目录内文件"。不在此放行——带到判决段，
          # 仅当 $bMode 且目标恰好是当前会话自己的标记文件才放行（防别的会话拆刹车）。见判决段。
          if (-not $clearMarkerTargets) { $clearMarkerTargets = @() }
          $clearMarkerTargets += @($cmt)
          $hitReason = "命令含删除动作(命令名 '$name'，目标在 .b-mode-active 目录内，P0 候选待判决段判 B)。"
          break
        }
        $hitReason = "命令含删除动作(命令名 '$name')，强制确认——包进脚本/循环/管道的删除也会被抓到。"
        break
      }

      # 2) 包装命令参数扫描（内嵌删除）
      if ($wrapperPatterns.ContainsKey($lname)) {
        foreach ($p in $wrapperPatterns[$lname]) {
          if ($argText -match $p) { $hitReason = "命令含包装类删除($lname 参数匹配 /$p/)，强制确认。"; break }
        }
        if ($hitReason) { break }
      }

      # 3) 破坏性 git
      if ($lname -eq 'git') {
        foreach ($p in $gitPatterns) {
          if ($argText -match $p) { $hitReason = "命令含破坏性 git(参数匹配 /$p/)，强制确认。"; break }
        }
        if (-not $hitReason -and ($argText -match '\brestore\b') -and ($argText -notmatch '--staged')) {
          $hitReason = "命令含破坏性 git(git restore 无 --staged 会丢工作区改动)，强制确认。"
        }
        if ($hitReason) { break }
      }
    }

    # 4) 成员调用：[IO.File]::Delete / [System.IO.Directory]::Delete(...)
    if (-not $hitReason) {
      $memberAsts = $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.InvokeMemberExpressionAst] }, $true)
      foreach ($m in $memberAsts) {
        $member = [string]$m.Member.Extent.Text
        if ($member -and ($member -match '^(Delete|DeleteDirectory)$')) {
          $hitReason = "命令含删除动作(成员调用 '::$member')，强制确认。"
          break
        }
      }
    }
  }

  # ---- B 模式判定（2026-07-21 第 3 层 hook：B 模式 rm 硬阻断）----
  # 设计：见 X-rm顽疾-第3层hook设计稿-2026-07-21.md。B 模式入口（/free /today /team-task /today-loop）
  #   启动时写标记文件 .b-mode-active（JSON: entry + ts + session_id），收尾清标记。hook 命中删除类时
  #   读标记：B 模式 → deny（不弹框、reason 回灌给 AI、AI 改追加式/攒后置门）；非 B → 维持 ask（交互不变）。
  # fail-closed（拿不准一律退回 ask=非 B 行为，只朝"多拦/多弹"掉，绝不朝"漏拦"掉）：
  #   标记读不到 / JSON 解析失败 / 缺 ts / ts 超过 TTL(2h) / 路径拼不出 → 全返回 $false。
  # ---- B 模式判定（2026-07-21 第 3 层 hook：B 模式 rm 硬阻断；会话级标记文件，codex 终审版）----
  # 设计：见 X-rm顽疾-第3层hook设计稿-2026-07-21.md + plan-rm顽疾-第3层hook施工交接 P0+P1+会话级段。
  # B 模式入口（/free /today /team-task /today-loop）启动写"本会话专属"标记文件：
  #   $env:CLAUDE_CONFIG_DIR\.b-mode-active\<session_id>.json（JSON: entry + ts + session_id）。
  #   收尾清"自己的"标记文件。hook 命中删除时按本次 stdin.session_id 找自己那张：
  #   文件存在 + JSON 里 session_id == 本次 sid + ts 在 TTL 内 → B 模式 deny；任一不对 → 非 B ask。
  # 会话级文件缘由（codex 终审 2026-07-21）：单文件 `.b-mode-active` 会被同账号并发 B 会话覆盖（后写覆盖先写，
  #   先写者保护静默失效）+ 收尾互删。改每会话一文件（文件名含 sid）→ 同账号多 /free 各自独立、不覆盖不互删。
  #   配合 P0 清标记例外（见 Test-ClearMarkerException）只放行"当前 B 会话清自己那张" → 别的会话拆不了你的刹车。
  # fail-closed（拿不准一律退回 ask=非 B 行为，只朝"多拦/多弹"掉，绝不朝"漏拦"掉）：
  #   CLAUDE_CONFIG_DIR 没设 / sid 非法 / 自己的标记文件读不到 / JSON 解析失败 / 缺字段 / session_id 对不上 / ts 超过 TTL / ts 在未来 → 全 $false。
  # TTL=30min + 未来时间戳容差 age>=-5min（防时钟漂移/误写未来 ts 长期有效）。
  function Test-BModeActive {
    param([string]$CurrentSessionId)
    $ttlMinutes = 30
    $futureToleranceMinutes = 5
    try {
      $configDir = $env:CLAUDE_CONFIG_DIR
      if ([string]::IsNullOrWhiteSpace($configDir)) { return $false }
      if ([string]::IsNullOrWhiteSpace($CurrentSessionId)) { return $false }
      # sid 做文件名安全处理：只留字母数字和 -（会话 ID 是 UUID，本就只含这些；防路径注入/../等）
      $safeSid = ($CurrentSessionId -replace '[^A-Za-z0-9-]', '').Trim('-')
      if ([string]::IsNullOrWhiteSpace($safeSid)) { return $false }
      $markerPath = Join-Path (Join-Path $configDir '.b-mode-active') ($safeSid + '.json')
      if (-not (Test-Path -LiteralPath $markerPath)) { return $false }
      $raw = $null
      try { $raw = Get-Content -LiteralPath $markerPath -Raw -ErrorAction Stop } catch { return $false }
      if ([string]::IsNullOrWhiteSpace($raw)) { return $false }
      $obj = $null
      try { $obj = $raw | ConvertFrom-Json -ErrorAction Stop } catch { return $false }
      if (-not $obj) { return $false }
      $entry = [string]$obj.entry
      $ts    = [string]$obj.ts
      $sid   = [string]$obj.session_id
      if ([string]::IsNullOrWhiteSpace($entry) -or [string]::IsNullOrWhiteSpace($ts) -or [string]::IsNullOrWhiteSpace($sid)) { return $false }
      # JSON 里 session_id 必须对上当前会话（文件名已按 sid 定位，这里是二次确认防文件被错放/改名）
      if (-not ($sid -eq $CurrentSessionId)) { return $false }
      # ts 解析：用 [datetime]$ts 强转 + try/catch。非法 ts（如 "not-a-date"）强转会抛异常 → 本 catch 接住 → return $false（fail-closed）。
      # 不用 [datetime]::TryParse($ts,[ref]$dt)——pwsh 7 无匹配的 2 参数重载，调用本身抛 "Cannot find an overload"（会被外层 catch 吞 → 标记永远无效，是早期 bug 的根因）。
      $tsDt = $null
      try { $tsDt = [datetime]$ts } catch { return $false }
      if (-not $tsDt) { return $false }
      $ageMin = ((Get-Date) - $tsDt).TotalMinutes
      if ($ageMin -gt $ttlMinutes) { return $false }
      if ($ageMin -lt (-1 * $futureToleranceMinutes)) { return $false }
      # 顺手 GC：当前会话标记有效，扫 .b-mode-active\ 目录删掉其他 ts 超过 TTL 的僵尸 <sid>.json
      # （崩了没清标记的会话留下的垃圾）。本会话自己的那张不删。失败 SilentlyContinue 不影响 return。
      try {
        $markerDir = Split-Path $markerPath -Parent
        if (Test-Path -LiteralPath $markerDir) {
          Get-ChildItem -LiteralPath $markerDir -Filter '*.json' -File -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_.FullName -ieq $markerPath) { return }  # 跳过自己那张
            try {
              $j = Get-Content -LiteralPath $_.FullName -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
              $jts = [datetime]([string]$j.ts)
              if (((Get-Date) - $jts).TotalMinutes -gt $ttlMinutes) {
                Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
              }
            } catch {
              # 僵尸文件 JSON 坏或读不了：留它等下次或手工清，不在此删（防误删非过期文件）
            }
          }
        }
      } catch {}
      return $true
    } catch {
      return $false  # 任何意外 → fail-closed
    }
    return $false
  }
  # 给定 session_id 算出它的标记文件绝对路径（P0 清标记例外 + skill 侧统一用同一路径公式）
  function Get-BModeMarkerPath {
    param([string]$CurrentSessionId)
    $configDir = $env:CLAUDE_CONFIG_DIR
    if ([string]::IsNullOrWhiteSpace($configDir) -or [string]::IsNullOrWhiteSpace($CurrentSessionId)) { return $null }
    $safeSid = ($CurrentSessionId -replace '[^A-Za-z0-9-]', '').Trim('-')
    if ([string]::IsNullOrWhiteSpace($safeSid)) { return $null }
    return (Join-Path (Join-Path $configDir '.b-mode-active') ($safeSid + '.json'))
  }

  if ($hitReason) {
    $curSid = $null
    try { $curSid = [string]$data.session_id } catch {}
    $bMode = Test-BModeActive -CurrentSessionId $curSid
    # P0 清标记例外（codex 终审会话约束版）：仅当 当前是 B 模式 + 命令目标恰好全等于"本会话自己的标记文件"
    #   才放行（exit 0 空输出 = allow）。非 B 会话或目标不是自己标记 → 不放行，照常 deny/ask。防别的会话拆刹车。
    if ($clearMarkerTargets -and $bMode) {
      $ownMarker = Get-BModeMarkerPath $curSid
      $allOwn = $ownMarker -and ($clearMarkerTargets | Where-Object { -not ($_ -ieq $ownMarker) }).Count -eq 0
      if ($allOwn) {
        exit 0  # 当前 B 会话清自己那张标记，放行（不 deny、不 ask、不回灌 reason）
      }
    }
    $decision = if ($bMode) { 'deny' } else { 'ask' }
    $reason = if ($bMode) {
      "$hitReason [B 模式硬阻断：B 自主流程中途不发 rm，攒后置人工门或改追加式（第 3 层 hook deny）。]"
    } else { $hitReason }
    $out = @{
      hookSpecificOutput = @{
        hookEventName            = 'PreToolUse'
        permissionDecision       = $decision
        permissionDecisionReason = $reason
      }
    } | ConvertTo-Json -Compress -Depth 5
    # 直接写 UTF-8 字节流，绕过控制台默认编码（中文 reason 否则会乱码）
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($out)
    $stdout = [Console]::OpenStandardOutput()
    $stdout.Write($bytes, 0, $bytes.Length)
    $stdout.Flush()
    exit 0
  }
  exit 0
} catch {
  # fail-open + 诊断日志（2026-07-21）：守卫脚本自身任何异常都 exit 0 放行，避免 hook bug 阻断用户正常命令
  # （比静默放行删除更糟的是把用户卡死）。但纯静默 = 删除守卫一旦有 bug 就"空输出 exit 0"被无视 → 失守无迹可查。
  # 折中：放行 + 写一行诊断日志到当前账号根的 hooks-error.log（带时间戳 + 异常摘要 + 行号），有迹可查又不扰民。
  # 与 Test-BModeActive 的 fail-closed 区分：那是"B 模式判定拿不准 → 退回 ask 多弹"，方向是拦；这里是"脚本整体崩 → 放行"，方向是放。
  try {
    # 日志写当前账号根（CLAUDE_CONFIG_DIR，与 B 模式标记同源定位）；缺失则不写（不回退到别的账号根，防记错地方）
    $logPath = $null
    if (-not [string]::IsNullOrWhiteSpace($env:CLAUDE_CONFIG_DIR)) {
      $logPath = Join-Path $env:CLAUDE_CONFIG_DIR 'hooks-error-guard-delete.log'
    }
    if ($logPath) {
      # 简单轮转：日志超 1MB 先挪 .old 再写新（轮转失败 SilentlyContinue，绝不让诊断逻辑反过来让 catch 再抛）
      try {
        if (Test-Path -LiteralPath $logPath) {
          $size = (Get-Item -LiteralPath $logPath -Force -ErrorAction Stop).Length
          if ($size -gt 1MB) {
            Move-Item -LiteralPath $logPath -Destination ($logPath + '.old') -Force -ErrorAction Stop
          }
        }
      } catch {}
      $line = '[' + (Get-Date).ToString('s') + '] guard-delete.ps1 EXC: ' + ($_.Exception.Message -replace '\s+', ' ').Trim() + ' | line#' + $_.InvocationInfo.ScriptLineNumber
      Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
    }
  } catch {}
  exit 0
}
