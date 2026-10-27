---
description: 手工把上一条「用户纠正」强制捞进 feature-05 捕获网（绕过词表召回，最高 tier）
---

用户刚纠正了我一个错误，并独立输入 `/pin` 要把这条纠正**手工兜底捞进 feature-05 捕获网**——这是机械 hook 会漏的那类（无标志词的苏格拉底式纠正），人亲手贴标签、100% 命中、最高质量燃料。

## 你要做的（就这一件事，别扩展、别重开任务）

1. 从**本对话上下文**认出两样东西：
   - **纠正原文** = 用户在这条 `/pin` **之前那一条**真实纠正（不是 /pin 本身；如果 /pin 前一条是我在回应、再往前才是纠正，就取那条纠正）。
   - **被纠正的 AI 动作** = 我当时说/做的、被这条纠正指向的那段（取要点即可，几百字内）。
2. 先确认中央 sink 已存在；缺失就明确报 `PIN_SINK_NOT_FOUND` 并停止，禁止让 writer 自动新建、禁止回退旧 sink：
   ```powershell
   $pinLog = "D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/.claude/auto-memory/pin/pinned-candidates.jsonl"
   if (-not (Test-Path -LiteralPath $pinLog -PathType Leaf)) { Write-Error "PIN_SINK_NOT_FOUND: $pinLog"; exit 1 }
   ```
3. 跑写入器（**绝对路径**，因为本命令已铺开到 3 账号、可能从任意 repo 调用；路径含中文/空格务必整体引号）：
   ```
   python "D:/Downloads/Mc Claude Code Workshop/Mc-emoji/[feature-05-loop-self-improvement]/历史扫描/pin_capture.py" --pin-log "D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/.claude/auto-memory/pin/pinned-candidates.jsonl" --corr "<纠正原文>" --ai "<被纠正的AI动作要点>" --note "$ARGUMENTS"
   ```
   `--pin-log` 显式指向中央 KB 的 ignored raw-signal lane，所以不管你在哪个 repo `/pin`，候选都汇到同一个 `pinned-candidates.jsonl`；它仍是待 `/reflect` 消化的原始纠正信号，不是 KB 内容层。
   - `$ARGUMENTS` = 用户在 `/pin` 后可能附的一句备注（没有就传空）。
   - 若这条纠正后用户已给了「错因/想要啥」的补充，可加 `--followup "<那句>"`。
4. 只回一行确认（脚本会打印 `✅ 已 pin…`，把它转述给用户即可），**不要**复述纠正内容、不要顺势去"修那个错"（除非用户另外要求）。

## 边界
- 认不出上一条纠正（比如 /pin 前没有明显纠正）时，**别硬造**：直接问用户"你指的是哪条纠正？"，不要瞎写候选。
- 脚本自带去重（同一条纠正 pin 两次会跳过）与中央独立落档（不混进 gold/live 或普通 knowledge proposal），这些不用你管。中央 sink 缺失或不可写时必须明确失败，不得降级到旧 sink。
