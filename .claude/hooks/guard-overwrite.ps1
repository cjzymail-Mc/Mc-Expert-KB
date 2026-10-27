# guard-overwrite.ps1 — PreToolUse(Edit|Write) 关键文件覆写守卫
# 作用：Edit/Write 命中「保护清单」里的关键文件时强制弹确认（ask），防误覆写守卫自身/配置/备份。
# 为什么需要：本 repo 有 07-01 生成器覆盖 v1_gold 备份的事故前科；settings/hook 脚本一旦被误改会静默削弱防线。
# 参照官方 protect-files.sh 范式 + 社区「deny 规则 + PreToolUse 路径清单」双层做法（本层是后者）。
# 用 ask 不用 deny：用户确认后仍可正常改，只把"误覆写"从静默变成一次确认。
# 边界：官方示例只做子串匹配、不处理 `..`；这里先 GetFullPath 规范化再比对。
#   fail-open：脚本自身出错绝不阻断会话（exit 0）。
try {
  $raw = [Console]::In.ReadToEnd()
  if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
  $data = $raw | ConvertFrom-Json
  $fp = [string]$data.tool_input.file_path
  if ([string]::IsNullOrWhiteSpace($fp)) { exit 0 }

  try { $full = [System.IO.Path]::GetFullPath($fp) } catch { $full = $fp }
  $p = $full.ToLowerInvariant()

  # 保护清单（已小写；-like 中 \ 与 . 均为字面量，* 为通配）
  # 2026-07-07 通用化：原硬编码 yk 路径 → *\.claude*\... 覆盖 mc/xh/glm 各账号 + KB repo 源
  $protected = @(
    '*\.claude*\settings*.json',             # 所有 .claude* 的 user 级 + 项目级 + KB repo 源 settings
    '*\.claude*\hooks\*.ps1',                # 所有 .claude* hooks 脚本入口 + KB repo 源
    '*\.claude*\hooks\*.py',
    '*.bak*'                                 # 任何 .bak 备份
  )

  $hit = $false
  foreach ($pat in $protected) { if ($p -like $pat) { $hit = $true; break } }

  if ($hit) {
    $out = @{
      hookSpecificOutput = @{
        hookEventName            = 'PreToolUse'
        permissionDecision       = 'ask'
        permissionDecisionReason = "覆写关键文件($full)——守卫/配置/备份类，强制确认，防误覆写削弱防线。"
      }
    } | ConvertTo-Json -Compress -Depth 5
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
