---
name: mc-update
description: 任务完成后的文档更新流程——判断要不要固化记忆（频次+去重两道闸）→列候选等用户审→归属判断（auto-memory vs memory vs fix/Mc-debug）→执行+CLAUDE.md/STATE.md 同步。仅当用户显式输入 /mc-update 时触发，不做 model-driven 自动调用。
---

# mc-update（任务完成后的文档更新流程）

> **说明（user-scope 统一版）**：本文件是各 repo `mc-update.md` 的合并版，落地在 user-scope，所有 repo 共用；无本地覆盖。
> - CLAUDE.md / STATE.md 章节号已去除，改为语义化引用（如"CLAUDE.md 命令表"）。各 repo 跑时按本地编号自行映射。
> - 第 3 步 4e（顶级文件夹规约）按需触发：repo 有顶级文件夹硬底线才走，无则整段跳过；其中示例为 Agent-4 实际规约，其它 repo 不适用时忽略。

## 入口与读取范围（claude-glm）

本机由 claude-glm 调用；skill 母本仍在中央 KB `.claude/skills/`，通过当前配置根的 `skills/` junction 发现，不能把母本目录名误认成原生 Claude 账号。当前 profile 由 `CLAUDE_CONFIG_DIR` 确定，不回退读 `~/.claude/projects`。

- 普通项目先读当前 repo 的两层 MEMORY 索引，去重时也检查当前 profile 已存在的本项目 harness memory；同一物理目录只算一份。harness 目录是项目级，不称 user-scope 通用记忆。
- 沿用当前 repo 的既有落点与用户指定；没有消费指针时补薄入口，不自动迁移或合并 memory 目录，不动 junction。
- 当前 repo 是中央 KB（`D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo`）时，改走其 `/KB-update` 流程；KB inbox 不套用普通项目 auto-memory 归属。

## 接收 reflect 补漏候选（有交接时才读）

只接收用户带入、属于当前 repo 的 reflect 候选，作为第 1 步同一清单的一部分；不主动全盘挖历史。检查候选的原始来源、dedup_hash、已有吸收点和净新增内容，再复用第 0–3 步。中央 KB 候选转其 `/KB-update`；其他 repo 候选保留明确路由，不写进当前项目。

reflect 不另设签字桌。候选与落点已有明确用户批准时复用该批准；实质内容或落点改变才再确认，空白批注不算批准。已完整覆盖的直接登记吸收点，不重复写记忆或重复请用户审批。

处理完 reflect 候选后，按共享 [reflect 台账约定](../reflect/SKILL.md#4-处理台账reflect-与接收流程共用) 回写关联 hash：实际核实已吸收、明确拒绝，或批准且写入后回读成功才终结；仅批准、失败或待查不终结。note 带实际落点/裁决来源。补账失败只在原候选记录留待补账，先查目的地再恢复，不重复 apply；不改原始 pin 或其他项目知识。

## 第 0 步：要不要固化？

> 本流程是固化记忆的**唯一入口**（CLAUDE.md §0.2）：只在任务完成后走，任务途中一律不碰
> `.claude/{auto-memory,memory}/`、任何 `MEMORY.md`、harness memory 目录。途中发现的可固化
> 经验只在收尾口头提示「建议 mc-update 固化 X」，由用户在本流程里拍板。

**两道闸门，全过才写**：

1. **频次闸**：这条经验 1 年内会被反复需要 ≥ 3 次吗？
   - ❌ 否（一次性反思 / git log 已是真相）→ **不写**，本次结束
2. **去重闸**：先用 Grep 工具或 `grep -r '<topic>' .claude/auto-memory/ .claude/memory/`（PowerShell 不支持 brace expansion，两路径分列），有没有同主题条目已覆盖？
   - ✅ 已被现有条目完整覆盖 → **不写**（哪怕够 ≥3 次——再写只是近似重复条目，徒增索引拥挤）
   - 仅部分覆盖 → 走 append（第 3 步），**不另起新条目**
   - 完全没有 → 才允许新建

两道都过才继续。任务完成 ≠ memory 必有更新——很多时候 git log + Mc-debug-N.md 已是真相，强行固化只污染索引层。

## 第 1 步：列清单等用户审核

**列出候选文件，按重要性排序展示，等用户挑选。** 不要直接动手。

候选清单含两类（并排展示，用户一次挑全）：

1. **本会话可固化经验**（经第 0 步两道闸筛过的）。
2. **Codex inbox proposal**（如本 repo 存在 `.codex/memory-inbox/` 目录）：扫该目录下 `status: proposed` 且 `review: pending` 的文件，逐条列 `title` + `applicability` + `destination_candidate` + 证据摘要。
   - **静默 skip**：目录不存在 → 整类跳过、不报错、不打印（多数纯 Claude repo 无此目录）。**三种零候选情况同样静默**（不打印任何"0 条/无候选"提示）：目录存在但为空 / 目录存在但无 `status: proposed + review: pending` 文件 / 整类跳过。**只有列到 ≥1 条候选时，候选清单才出现 inbox lane 标题**（零候选 = 零噪声）。
   - **`review: deferred` 不列**：deferred 是 `$today` 全托管 finalizer 产的、设计为攒批后审，不在本 lane 即时处理（见 today SKILL.md finalizer 段）；硬塞进 interactive 审会绕过 batch 语义。
   - **用相对路径**扫 `.codex/memory-inbox/`（`/mc-update` 在哪个 repo 跑就扫哪个 repo 的），禁硬编码任何 repo 私料绝对路径。

## 第 2 步：归属判断

**memory 归属**（核心问句：没这条知识，新会话前 2-3 回复会出错吗？）：

| 答案 | 归属 | 路径 |
|--|--|--|
| ✅ 用户偏好 / 跨主题元规则 / 高频反射 | auto-memory | `.claude/auto-memory/` |
| ❌ 特定任务 / 技术细节 / 一次性踩坑 / 架构档案 | memory | `.claude/memory/` |
| 🔧 skill-bound 经验（随某 skill 走、任意 repo 用该 skill 都适用） | user-scope skill | 随该 skill 沉淀（SKILL.md / skill 级 memory），**不塞 repo 级 memory**（换 repo 加载不到） |

> **skill 层判定**：经验是否"绑在某个 skill 上、跨 repo 用该 skill 时都该浮现"？是 → 随 skill（user-scope，junction 跨账号生效），别塞 repo 级 memory（换 repo 就丢）。源 2026-07-09 Hot-Fix：GLM-vision 经验错塞 auto-memory，用户点破"memory 是 repo 级、我可能在任意 repo 用该 skill"（reflect 续30 签字 #2）。

**改动归属**：

| 改动类型 | 写到 |
|--|--|
| 技术 bug + 代码修复 + 实证 | `[feature*]/fix*.md` |
| 跨主题讨论 / 架构决策 / 架构精简 | 本 repo 的 Mc-debug 目录续写（顶级 `mc-debug/`、`【Mc-debug】/` 或 `[feature*]/` 下；续写不另起） |
| 反复用得上的元规则 / 高频反射 | `.claude/memory/feedback_*.md` |
| 无新规则可提炼（meta / process 改动） | 啥都不写（git log 即真相） |

## 第 3 步：执行（仅对用户挑中的候选）

1. 按第 0 步去重闸结论落位：部分覆盖 → append 现有文件；完全没有 → 才新建条目
2. 写文件（frontmatter：`name` / `description` / `type`）
3. 更新 MEMORY.md 索引（auto-memory 索引尤其精简，每会话都加载）
4. **CLAUDE.md / STATE.md 同步检查**（必做，不是"如有"）：
   - 4a **既有指针**：grep 是否对得上新 memory 路径（auto-memory vs memory 路径不要错）
   - 4b **结构性变更**（**严判**：仅以下三类触发）：新建**顶级目录** / 新增**跨 feature 工作流场景** / 新增**跨 feature 约定** → CLAUDE.md 文件结构 / 详情索引相应章节加节点
     - 反例（**不触发**）：feature 内 schema 升版、单 RD 脚本修复、内部脚本重命名、单个 memory 条目新增
   - 4c **命令表**：本次有没有新增 `/role-*` 或 slash command？→ CLAUDE.md 命令表 +1 行
   - 4d **变更日志**：4a-4c 任一触发 → **STATE.md 变更日志**表 +1 行（日期 + 简述）。**不是** CLAUDE.md（CLAUDE.md 是契约层，不维护 changelog；STATE.md 是状态层）
   - 4e **顶级文件夹规约**（**可选段落**，仅当本 repo 有顶级文件夹硬底线时填写；无则整段删除）：
     - 本次有没有顶级文件夹的新增 / 重命名 / 职责拆分？→ sync CLAUDE.md 顶级文件夹规约区 + STATE.md +1 行
     - 调拨产物前先按本 repo 的硬底线归位，**禁止跨档塞文件**
     - 示例（Agent-4 实际规约，其他 repo 请替换或删除）：
       - `mc-plan/` — **仅** plan md（main-plan、sub-plan-NN-xxx），不放脚本/台账/产物
       - `mc-progress/` — 执行产物（脚本、台账 xlsx、模板等），备份在 `mc-progress/backups/`
       - `mc-debug/` — 架构讨论 / 计划制定 / 复盘类 md
5. 挪/删文件后，grep dangling 引用并修复（凝固态档案除外：`*debug*` / `*plan*` / `*fix*` 不回溯篡改；CLAUDE.md 末尾如已加重定向锚点则为旧 §引用兜底）
6. **inbox proposal 回写**（仅当第 1 步挑了 Codex inbox proposal 时）：
   - 用户批准某 proposal → 先回写 inbox 源文件：`status: accepted` + `reviewer: <用户>` + `accepted_at: YYYY-MM-DD`。
   - 按该 proposal 的 `applicability` 走第 2 步路由表 apply（写目的地 memory + 更新 MEMORY 索引，与普通候选同流程）。
   - 写目的地成功后，回写 inbox 源文件追加：`applied_at: YYYY-MM-DD` + `destination: <实际写入路径>`。
   - 用户拒绝 → 回写 `status: rejected` + `reviewer` + `rejected_at`。
   - **防悬挂兜底**：第 3 步末尾 grep `.codex/memory-inbox/` 里 `status: accepted` 但缺 `applied_at` 的文件 = 悬挂清单，列进本流程报告交用户人工裁决（重试 apply / 手动 mark rejected / 手动 apply）。skill 流程中途可能被打断（compact / 用户打断 / 写目的地失败），这是"分两次写 + 末尾 grep 列悬挂清单"，**不做强一致性保证**。
     - **排除 legacy inline 格式**：`status: accepted # 已路由并入 X`（行尾带 `#` 注释的老文件）是 legacy 已应用、只是没字段化 `applied_at`，**不算悬挂、不列入报告**。悬挂判定 = `status: accepted` 且**无** `applied_at` 且 status 行**无** `#` 注释。（fixture 验证发现：不排除 legacy 会让 3 条 legacy 误报污染悬挂清单。）
   - **不自动重试**：已 `status: accepted` 的 proposal **不再列入第 1 步候选**（即便缺 applied_at）；悬挂的恢复靠 grep 报告 → 用户人工裁决，skill **不自动重试 apply**（自动重试 = 弱一致性引擎语义，撞 main-plan §4 禁区 1/2）。
   - **legacy accepted 不回填**：已有 inline 注释格式（`status: accepted # 已路由并入 X`）的老文件保留作 audit，不补 `applied_at`/`destination` 字段（protocol §52 不批量重写历史）。字段化记录只对本次起新 review 的 proposal 生效。
   - inbox 源文件 apply 后**原地保留**（作 audit 记录，protocol 第 4 条要求），不删不移。

## 反例

- ❌ 任务完成必写 memory（git log 已是真相）
- ❌ 任务途中主动写 / 改记忆文件（CLAUDE.md §0.2 禁止；只在收尾走本流程）
- ❌ 踩坑都塞 auto-memory（每次会话 system prompt 拥挤）
- ❌ 用户偏好放 memory（按需加载导致前 2-3 回复风格不对）
- ❌ 不 grep 同主题就写新 memory（产生重复 / 碎片）；同主题已有条目还新建近似条目（该 append 就 append）
- ❌ 删/移文件后不更新索引（产生 dangling 引用）
- ❌ meta/process 改动塞进 fix*.md（拉低 fix 文档信噪比）
- ❌ 新建顶级目录或文件类型，但忘改 CLAUDE.md 文件结构图（下次会话拿到过时的项目地图）
- ❌ 把 "如有 CLAUDE.md 指针就更新" 误读为 "没有就跳过"（实际：常常是该新增一条）
- ❌ 把 changelog 行写进 CLAUDE.md（契约层不维护变更日志 → 写到 STATE.md 变更日志）
- ❌ 给 inbox 回写加"两阶段保证一致性"的强语义（如：要么都成功要么都撤销 / 一条 proposal 只能 apply 一次的硬保证）—— 撞 main-plan §4 禁区 2（promotion tool 强保证）；本 lane 是"分两次写 + 末尾 grep 列悬挂清单交用户"，**不做强保证、靠人工兜底**，不是强一致性流程
- ❌ inbox accepted 未 applied 的悬挂 proposal 自动重试 apply（自动重试 = 弱一致性引擎语义，撞 main-plan §4 禁区 1/2；应靠末尾 grep 报告交用户人工裁决）
- ❌ `/mc-update` 在没有 `.codex/memory-inbox/` 的 repo 报"扫不到目录"噪声（应静默 skip）；目录存在但无 pending proposed 也静默（零候选 = 零噪声）
