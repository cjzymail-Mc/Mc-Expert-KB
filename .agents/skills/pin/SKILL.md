---
name: pin
description: "[Codex user-scope skill] 用户手工把刚才的纠正写入中央 raw-signal sink，供 reflect 归纳；仅显式 $pin 触发。"
---

# `$pin`（Codex user-scope 手工纠正捕捞）

用户当场纠正 AI 后，显式输入 `$pin`，把这一条 human-labeled correction signal 写进中央 ignored raw lane。它不是 knowledge proposal，不写 `.codex/memory-inbox/`，也不直接进入 KB 内容层。

先完整读取 `$env:USERPROFILE/.agents/skills/_mc-common/codex-runtime-bindings.md` 的 manual-only、失败状态与 finalizer 所有权。本 skill 不调用 Claude 母本。

## 固定单源

```powershell
$pinScript = 'D:\Downloads\Mc Claude Code Workshop\Mc-emoji\[feature-05-loop-self-improvement]\历史扫描\pin_capture.py'
$pinLog = 'D:\Downloads\Mc Claude Code Workshop\Mc-Expert-repo\.claude\auto-memory\pin\pinned-candidates.jsonl'
```

- writer/core 唯一正式副本仍在 Mc-emoji feature05；禁止复制到本 skill。
- sink 唯一活跃写目标是中央 `pin/pinned-candidates.jsonl`；禁止回退旧 feature05 sink。
- 任一路径缺失即 fail-loud：分别报告 `PIN_SCRIPT_NOT_FOUND` / `PIN_SINK_NOT_FOUND`，不得改写普通 memory proposal。

## 执行

1. 从本对话识别：
   - `corr`：用户刚才的纠正原文，不是 `$pin` 本身；
   - `ai`：被纠正的 AI 动作/回复要点；
   - 可选 `followup` 与 `$pin` 后备注 `note`。
2. 认不出真实纠正就停下询问，禁止硬造。
3. 在调用 writer 前先做确定性存在性检查；sink 缺失时禁止让 writer 自动新建：

   ```powershell
   if (-not (Test-Path -LiteralPath $pinScript -PathType Leaf)) { Write-Error "PIN_SCRIPT_NOT_FOUND: $pinScript"; exit 1 }
   if (-not (Test-Path -LiteralPath $pinLog -PathType Leaf)) { Write-Error "PIN_SINK_NOT_FOUND: $pinLog"; exit 1 }
   ```

4. 先 dry-run，不写盘：

   ```powershell
   python $pinScript --pin-log $pinLog --platform codex --corr "..." --ai "..." --followup "..." --note "..." --dry
   ```

5. dry-run 正常后正式写入同一参数（去掉 `--dry`）。脚本按 `ai + corr + followup` 去重；命中重复属于成功跳过。
6. 汇报类别、纠正摘要、总条数、中央 sink 路径和是否命中去重。

## 边界

- standalone 只由用户手工 `$pin` 触发；`allow_implicit_invocation:false`。
- today/free 等 finalizer 的 pin 段只产提案，用户批准后由人工门批量调用 writer，不自动调用本 skill。
- `src.platform=codex`；Claude `/pin` 使用相同 writer/sink、标记 `claude`。
- 中央 sink 被 Git ignore，只是 `/reflect` 的原始信号输入；知识晋升仍须人工签字与 `/KB-update` 闸门。
