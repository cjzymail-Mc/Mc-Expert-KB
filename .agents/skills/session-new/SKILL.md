---
name: session-new
description: "[Codex adapter] 会话交接固化——第一动作硬执行 shell 读 Claude session-new 母本；显式指定现有文件时原位补全且不另建 plan，未指定时才产 plan。正文只留 Codex 差异；手工 $session-new 触发。"
---

# $session-new（Codex adapter for Claude session-new skill）

执行型 adapter。**不走 junction**：Codex 的 `allow_implicit_invocation` 只能由 adapter 的 `agents/openai.yaml` 控制，junction 直指母本注入不了 Codex 侧 policy。

## 第零前置：读共同 binding

先完整读取 `$env:USERPROFILE/.agents/skills/_mc-common/codex-runtime-bindings.md`。母本 locator、`Task(mc-expert)` 当前 turn preflight、manual-only 与 exactly-once 口径不在本 adapter 重复维护。

## 第一步：读母本（单一真相源，硬执行 · 禁跳 · 每次先读）

```powershell
pwsh -NoProfile -File (Join-Path (Join-Path $env:USERPROFILE '.agents\skills\_mc-common') 'resolve-master.ps1') -SkillName session-new -Cat
```

母本（Claude user-scope）：四步（第 0 步主线回顾 / 第 1 步固化成交接物 / 第 2 步 memory / 第 3 步状态文件 / 第 4 步汇报）。**读母本后按母本四步执行通用流程**，正文不复制母本业务逻辑——母本改动下次读取即可见。

> ⚠️ **§6.6 实测**：旧 adapter 描述说"读母本"但正文没给硬 Get-Content 指令，靠复制母本正文维持，导致母本改动不自然生效。本步是**硬指令**：不读母本不准往下走（resolve-master.ps1 找不到会 MASTER_NOT_FOUND exit 1、fail-loud）。resolve-master 优先读 `$env:CLAUDE_SKILL_MASTER_DIR`，其次 sibling `Mc-Expert-repo\.claude\skills\session-new\SKILL.md`。

## Codex 侧执行（薄翻译母本四步 + 第 0 步主线回顾）

正文只保留**与母本不同的 Codex 差异**；与母本相同的通用逻辑（四步结构 / 交接物内容要求 / 反例）读母本执行，不在此重复。

### 第 0 步·主线回顾（产交接物前必做 · 硬执行 · 禁跳）

母本第 0 步是收尾 loop 闭合的关键。**本步是纯 LLM 文本判断，不依赖 mc-expert 陪审、不依赖任何 Claude-only 机制**——codex 自己做即可平移接住（这是母本第 0 步能落到 codex 的关键）。

1. **读主线锚点**（命中即停）：① repo 有 STATE.md 含"当前主线"行→读它（权威源）；② 否则读最近 plan 开头的「本 plan 服务的主线」anchor；③ 都没有→标"主线未显式定义"、降级为"只列候选下一步、不做偏离判断"。
2. **评估偏离**（一句话+理由）：本次任务相对主线是推进/旁支/漂移？漂移则点明漂到哪、是否该回正。
3. **判"主线下一步是否已落 plan"**：已落→第 1 步更新交接物时只固化本次+标"下一步已在<plan路径>"、不重复规划；未落→第 1 步必把"主线下一步任务"写进交接物实施步骤（带建议默认）。
4. **顺带落主线行**：未命中显式目标文件分支、repo 有 STATE.md 时更新/补"当前主线=<一句话>+活跃 plan 指针"（有变化才改）；无 STATE.md 不强造。命中显式目标文件分支时不改 STATE.md，主线判断写入目标文件。

**输出格式（缺即视作未做）**：第 1 步产出的交接物须含一段「主线回顾：偏离评估=...；下一步=...（已落<plan> / 未落→本交接物实施步骤第 N 条）」。显式目标已有固定结构时放在合适位置，不要求破坏其标题或既有开头。

### 第 1 步·产交接物（按母本显式目标分支 / 1a / 1b）

用户显式指定现有文件时，原位更新该文件并使其冷启动自足，**不探测、不另建 plan，也不自动改 memory/状态文件**；目标不存在或有歧义时停下询问。未指定文件时才按母本 1a 定 plan 存放位置（有 plan 文件夹→进去沿用命名 / 根目录已有 plan*.md→沿用风格 / 都没有→默认根目录 `plan-<主题>.md`）。交接物内容执行母本 1b。**重入幂等**：显式目标分支始终更新同一文件；plan 分支重入前查同名/同任务 plan，存在则只更新该 plan，不重复新建。

### 第 2 步·memory（调真实 $mc-update，不直写）

Codex **不直写** Claude memory。先检查 caller：

- 命中显式目标文件分支：除非用户另行明确要求，本步跳过。
- `caller_id=finalizer`：上游已按 `$mc-update → (pin 提案) → $session-new` 执行过 `$mc-update`，本步验证上游已有 mc-update 决策/证据后**跳过重复调用**。pin 段的提案清单由上游 today-core §2.1 产出、写入本次交接物交人工门，session-new 不调 `$pin` skill。
- standalone 手工 `$session-new`：调 `$mc-update` skill，按四 lane 执行。

Codex 侧只产 proposal 到 `.codex/memory-inbox/`，正式 apply 由 Claude `/mc-update` review 流程完成。

### 第 3 步·状态文件（按母本判据直接更新，不降级）

命中显式目标文件分支时默认跳过。未命中时执行母本第 3 步：只更新"不写新会话就会丢"的状态载体，沿用 repo 既有约定（STATE.md / team-progress / todays-task），不新造。**Codex 有 workspace 写能力**——旧 adapter"拿不准就不动"的过度保守与实际能力不匹配。按母本判据直接更新允许范围内的状态文件；真拿不准某文件才不动、在汇报里提示。

### 第 4 步·汇报（按母本）

给两样：① 交接物路径（绝对）+ 命中显式目标文件分支或哪条 plan 存放规则；② 更新文件明细（逐条「路径—改了什么」，含 memory（新建/append/未动及原因）、状态文件、索引）。没动的大类也说明「未动 + 原因」。

## Claude-only 机制翻译（接真实 Codex skill，不假装原生等价）

- **`mc-update` 纪律**（母本第 2 步）→ 调真实 `$mc-update` skill（四 lane）。
- **`pin_capture.py`**（共享纠正捕捞链）→ 收尾链不再自动调 `$pin` skill；pin 段改由 today-core §2.1 产提案清单，落账走人工门（用户审后由 LLM 显式写中央 ignored raw sink）。standalone 手工 `$pin` 由 user-scope 中央 Codex skill 处理；不得回退 repo-local adapter 或旧 feature05 sink。
- **AskUserQuestion** → Codex 无原生；决策点输出问题等用户答（停人工门）。
- **`Task(mc-expert)`** → 先按共同 binding 检查当前 turn native tool surface；有工具才 spawn 只读 sub-agent 并显式读取 `.codex/agents/mc-expert.toml`，无工具写 `BLOCKED_TOOL_UNAVAILABLE`；不是自动 profile 绑定，也不得用 `codex exec` fallback。
- **Agent Teams** → 当前无同形机制；需要团队拓扑时停人工门，不偷换成单 agent。

## 边界

- standalone 只由手工 `$session-new` 触发；也允许被用户显式启动的 `$today/$free/$today-loop` 以 `caller_id=finalizer` 作为授权子流程调用。两者都不构成 implicit invocation（`allow_implicit_invocation: false` 保持）。
- 不清空/重开 session（真正关 session 仍由用户操作，adapter 只产交接物）。
- 交接物内容不得依赖本次对话历史（新会话读不到 = 没写）。


