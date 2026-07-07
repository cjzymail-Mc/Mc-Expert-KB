# guard-delete.ps1 — PreToolUse 安全网（L2：AST 结构化识别 + 正则兜底）
# 作用：扫描 Bash/PowerShell 工具调用的命令串，识别"真正的删除动作"就强制弹确认（ask）。
# 为什么需要：方案 A 的 settings `ask` 规则是「命令开头前缀匹配」，把 Remove-Item/rm
#   包进 foreach/脚本/管道（开头变成 $f= 之类）就会绕过 → 静默删除。
#
# L2 与旧 L1 的区别（2026-06-09）：
#   L1 旧版直接对【命令全文】跑 substring 正则 \brd\b 等 → 把 `find -name "*RD*"`
#      这种【字符串字面量里的 RD】误判成删除命令（PS -match 默认大小写不敏感，RD 也中）。
#   L2 改为先用 PowerShell 语法分析器把命令解析成 AST，只在【命令位置】(CommandAst 的
#      命令名 / [IO.File]::Delete 这类成员调用) 上找删除动词；字符串字面量 "*RD*" 在 AST
#      里是 StringConstant，不是命令名，自然被忽略 → 消除该类误报。
#      仍能抓住包进 foreach { Remove-Item } 的删除（那个 Remove-Item 是真命令名）。
#   兜底：若命令解析报错（怪 bash 语法 PS 啃不动），回退到旧的全文正则——保护永不掉线，
#      只在那一刻退回粗粒度。
# 边界：防「误包」不防「故意混淆」（base64/别名/变量间接 `& $var` 仍可绕）。
#   fail-open：脚本自身出错绝不阻断会话。
try {
  $raw = [Console]::In.ReadToEnd()
  if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
  $data = $raw | ConvertFrom-Json
  $cmd = [string]$data.tool_input.command
  if ([string]::IsNullOrWhiteSpace($cmd)) { exit 0 }

  # 删除动词（命令名层面，大小写不敏感比较——PowerShell 命令名本就大小写不敏感）
  $deleteVerbs = @('Remove-Item', 'rm', 'rmdir', 'rd', 'del', 'erase', 'ri')

  # 全文正则兜底用（仅在 AST 解析失败时启用）
  $fallbackPatterns = @(
    'Remove-Item', '\brm\b', '\brmdir\b', '\bdel\b', '\brd\b',
    '\[IO\.File\]::Delete', '\[System\.IO\.(File|Directory)\]::Delete'
  )

  $hitReason = $null

  # ---- L2：AST 结构化识别 ----
  $tokens = $null; $errors = $null
  $ast = [System.Management.Automation.Language.Parser]::ParseInput($cmd, [ref]$tokens, [ref]$errors)

  if ($errors -and $errors.Count -gt 0) {
    # 解析失败 → 回退全文正则（保护不掉线）
    foreach ($p in $fallbackPatterns) {
      if ($cmd -match $p) { $hitReason = "命令含删除动作(AST 解析失败，全文正则兜底匹配 /$p/)，强制确认。"; break }
    }
  }
  else {
    # 1) 命令位置：CommandAst 的命令名命中删除动词
    $cmdAsts = $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.CommandAst] }, $true)
    foreach ($c in $cmdAsts) {
      $name = $c.GetCommandName()
      if ($name -and ($deleteVerbs -contains $name)) {
        $hitReason = "命令含删除动作(命令名 '$name')，强制确认——包进脚本/循环/管道的删除也会被抓到。"
        break
      }
    }
    # 2) 成员调用：[IO.File]::Delete / [System.IO.Directory]::Delete(...)
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

  if ($hitReason) {
    $out = @{
      hookSpecificOutput = @{
        hookEventName            = 'PreToolUse'
        permissionDecision       = 'ask'
        permissionDecisionReason = $hitReason
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
  exit 0
}
