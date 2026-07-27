---
name: mc-update
description: "[Codex adapter] 直读 Claude mc-update 母本。任务收尾时跑四条 lane：文档/状态 lane（Codex 能改 repo 文件，不降级）+ 知识 lane（频次+去重闸）+ 归属/适用性 lane + proposal lane（只写 .codex/memory-inbox/，不直写 Claude memory）。两种 proposal 模式：interactive（手工列候选给用户审）/ deferred-review（全托管，mc-expert 预筛后直写 status:proposed+review:deferred）。手工 $mc-update 触发。"
---

# $mc-update（Codex adapter for Claude mc-update command）

执行型 adapter。先 shell 直读 Claude mc-update 母本拿最新逻辑，再按 Codex 平台差异执行。

## 第零步：读共同 binding

先完整读取 `$env:USERPROFILE/.agents/skills/_mc-common/codex-runtime-bindings.md`。deferred-review 需要 mc-expert 时必须执行当前 turn native tool-surface preflight；不可用即 `BLOCKED_TOOL_UNAVAILABLE`，不得改用 `codex exec`。

## 第一步：读母本（单一真相源，每次先读）

```powershell
pwsh -NoProfile -File (Join-Path (Join-Path $env:USERPROFILE '.agents\skills\_mc-common') 'resolve-master.ps1') -SkillName mc-update -Cat
```

母本是 user-scope 统一版（第 0 步两道闸 / 第 1 步列候选 / 第 2 步归属 / 第 3 步执行含 CLAUDE.md/STATE.md 同步 / 反例）。改母本 → 本 adapter 下次读取即可见。母本只读，不复制正文进 adapter（母本改动自动同步）。

> resolve-master.ps1 优先读 `$env:CLAUDE_SKILL_MASTER_DIR`，其次 sibling `Mc-Expert-repo\.claude\skills\<name>\SKILL.md`；找不到 fail-loud（MASTER_NOT_FOUND，exit 1），禁止静默用旧副本。换机设环境变量或换 sibling 路径即可。

## 四条 lane（拆开，母本把四条压成一条会漏）

母本第 0–3 步的语义落到 Codex 侧要拆成四条独立 lane。**文档/状态 lane 不被知识 lane 的频次闸门控**——没有 memory 候选不等于不需要同步 repo 文档。

```text
任务收尾
  ├─ ① 文档/状态 lane：每次都检查；有结构变化就直接更新 repo（STATE.md / AGENTS.md / CLAUDE.md 指针 / 命令表 / dangling 引用）
  └─ ② 知识 lane：频次闸（≥3 次）+ 去重闸（grep .codex/memory-inbox/ + .claude/auto-memory/ + .claude/memory/）
       ├─ 不通过 → 不写 proposal
       └─ 通过 → ③ 归属/适用性 lane → ④ proposal lane（.codex/memory-inbox/，等人审晋升）
```

### ① 文档/状态 lane（Codex 能改 repo 文件，不降级）

母本第 3 步 4a–4e 的结构同步纪律在 Codex 侧**直接执行**（不是推给用户手工处理）：

- **既有指针**（4a）：grep 新 memory/改动路径对不对得上。
- **结构性变更**（4b，严判仅三类）：新建顶级目录 / 新增跨 feature 工作流 / 新增跨 feature 约定 → AGENTS.md 落点规约表 / CLAUDE.md 结构节点同步。反例（不触发）：feature 内 schema 升版、单脚本修复、内部重命名。
- **命令表**（4c）：本次有没有新增 `$slash` skill？→ 命令表 +1 行。
- **变更日志**（4d）：4a–4c 任一触发 → STATE.md 变更日志表 +1 行（日期 + 简述）。契约层 AGENTS.md/CLAUDE.md 不维护 changelog。
- **dangling 引用**（4e 之后）：挪/删文件后 grep 修复。

> 旧 adapter 把"CLAUDE.md/STATE.md 无等价 harness"误推成要用户手工处理，是**假降级**——把 memory 写权限差异误扩大成文档更新能力不存在。Codex 有 workspace 写能力，repo 内文档直接改（`.agents`/`.codex` 只读路径走 `require_escalated`）。

### ② 知识 lane（频次 + 去重两道闸，从严）

只在任务**收尾**跑（任务途中不碰 memory，呼应母本 §0.2）：

1. **频次闸**：1 年内反复需要 ≥3 次？否（一次性/git log 已是真相）→ 不写。
2. **去重闸**：grep `.codex/memory-inbox/` + `.claude/auto-memory/` + `.claude/memory/`（三路径分列，PowerShell 不支持 brace expansion）。已被现有条目完整覆盖 → 不写；部分覆盖 → append；完全没有 → 才允许新建 proposal。

### ③ 归属/适用性 lane（双轴：存在哪 + 适用于谁）

正式存储继续只有一份（`.claude/auto-memory/` 每会话索引 + `.claude/memory/` 按需）。但每条 proposal 必须带**两个独立轴**（schema v2）：

```yaml
scope: project|cross-project|machine-specific   # 存在哪（沿用）
applicability: shared|codex-only|claude-only|skill-bound  # 适用于谁（新增）
producer_platform: codex
destination_candidate: <路径或类别>              # 建议去向，人审时可改
```

| 候选类型 | 正式去向 | 处理 |
|---|---|---|
| shared 高频反射/偏好 | `.claude/auto-memory/` | 每会话索引 |
| shared 项目技术/档案 | `.claude/memory/` | 按需读 |
| codex-only 经验 | 默认 `.claude/memory/`，标 codex-only | Claude 不应用；Codex 按需读 |
| claude-only 经验 | `.claude/memory/` 或 Claude skill | Codex 不应用 |
| skill-bound | 对应 user-scope skill/adapter | 不塞 repo memory |
| machine-specific | `.claude/memory/`，标机器范围 | 禁止推广 |
| 一次性证据/实施细节 | feature report / git | 不写 memory |

默认不把 codex-only 细节塞 auto-memory（挤 Claude 启动上下文）；只有"Codex 新会话前 2–3 回复必需"的极少数才例外且索引显眼标范围。

### ④ proposal lane（只写 inbox，不直写 Claude memory）

Codex **不直写** `.claude/auto-memory/` 或 `.claude/memory/`（边界，plan02 D3）。通过闸门的候选只写 `.codex/memory-inbox/` proposal，等人审晋升（正式 apply 入口是 Claude `/mc-update`，见 §7.5 M1-Scope）。inbox 是 proposal/audit 暂存，不是"Codex 自己已学会"。

## 两种 proposal 模式（§7.4）

| 模式 | 触发 | 行为 |
|--|--|--|
| **interactive**（手工 `$mc-update`） | 用户直接输入 `$mc-update` | 列候选给用户审（按重要性排序），用户挑后才写 proposal；不 apply 正式 memory |
| **deferred-review**（全托管收尾） | `$today` 全托管收尾调用 | mc-expert 预筛后直接写 `status: proposed` + `review: deferred` 的 inbox 文件，在最终报告列出；不等用户、不 apply canonical |

deferred-review 不是绕过人工记忆门——人工门从"能不能先保存 proposal"后移到"能不能写正式 canonical"，符合 `signal → proposal → review → apply` 边界，避免无人值守在最后一步死等。

## inbox protocol（schema v2）

新 proposal 从 schema v2 起强制双轴字段（`scope` + `applicability`）。旧档不批量回写（§7.6：2 份旧 proposed 在首次 review 时补字段、3 份已 accepted 留作 audit 不动）。不建 pending/accepted/rejected 目录树（文件量不值得再造索引/状态机）——见 `.codex/memory-inbox/inbox-protocol.md`。

## Claude-only 机制翻译

- **Claude memory 直写** → Codex 侧只产 proposal 到 `.codex/memory-inbox/`，**不直写**。
- **MEMORY.md 索引更新**（Claude auto-memory 索引）→ Codex 不更新 Claude 索引；inbox proposal 自带 frontmatter 即索引。
- **正式 apply**（写 canonical memory）→ Codex 无 apply 权限；Claude `/mc-update` review 流程（P6 M1-Scope 后扫 Codex inbox）是唯一 apply 入口。

## 边界

- standalone 只由手工 `$mc-update` 触发；也允许被用户显式启动的 `$today/$free/$today-loop` 以 `caller_id=finalizer` 作为授权子流程调用。两者都不构成 standalone implicit invocation（`allow_implicit_invocation: false` 保持）。
- 任务途中不碰 memory（只在收尾走本流程）。
- 文档/状态 lane 不被知识 lane 闸门控：没有 memory 候选 ≠ 跳过 STATE/文档同步。
- 不假装"Codex 能 apply canonical memory"——只能产 proposal。



