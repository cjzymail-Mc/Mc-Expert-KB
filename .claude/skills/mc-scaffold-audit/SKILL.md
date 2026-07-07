---
name: mc-scaffold-audit
description: 扫描整个 repo 是否符合「项目脚手架规范」，输出「合规 + 整改建议」报告（只 check 不自动改）。先判 repo 类型（production/learning/KB）定默认期望，再按信号（检到 team-task.md / 多产物目录 / 超 100 行 CLAUDE.md 等）定实际查哪些项——type 定默认、signal 定实查。检查项分四层：L1 契约/状态/记忆（含原「CLAUDE.md 三层拆分」全套判据+STATE.md 模板+迁移步骤，作为子流程）、L2 计划/执行/复盘（mc-plan/mc-progress/mc-debug）、L3 协作/自动化（team/loops/commands/skills）、L4 命名约定。核心元规则=「少做」：缺项默认语气是「按需，没痛点别建」，不是「待整改」。两种模式：**bootstrap**（新建 repo 起手→生成默认 CLAUDE.md 模板，含「顶级文件夹落点规约表」根治每个冷会话乱放过程文件的痛点 + 文件夹骨架；production 预建 mc-plan/mc-progress/mc-debug，learning 只写规约表不预建）/ **audit**（老 repo 体检→出合规+整改报告，只 check 不自动改）。任何新 repo 起手 / 老 repo 体检 / 想知道某 repo 缺哪些骨架 / CLAUDE.md 超 100 行混演进史时用。跨 repo 通用（user 级单一事实源，经 skills junction 覆盖多账号）。
---

# mc-scaffold-audit — 项目脚手架合规检查

> 用途：在任意 repo（新或旧）跑一遍，按**同一套脚手架规范**判断它是否符合，不符合就**输出整改建议**。
> 输出：一份「合规 + 整改建议」报告，**只 check 不自动改**（改动留人审，见 §0 元规则）。
> 由来：原 `claude-md-three-layer-refactor`（CLAUDE.md 三层拆分）升级而来——三层拆分降为本规范的 L1 子流程（全套判据/模板/坑保留，见 §4）。规范底座取自 Wu Prj「四层+三轴」体系 + 2026-06-21 草案评审（mc-expert 陪审）。

---

## 0. 第一原则：少做（反过度工程元规则）

**这个 skill 不是「逼你把脚手架补齐」的力量。** 对齐 KB `principles.md`「少做」：出现具体痛点前不加抽象。

- check 报告里「缺 X」的默认语气 = **「按需，没痛点就别建」**，不是「待整改」。只有「**违反硬规则**」「**已有痛点对应的缺失**」才升级成必改项。
- 学习/实验 repo 标准就该稀疏——别拿生产 repo（如 Wu Prj）的重型骨架去刷它的「不合规」。
- 本 skill 永远只出报告、不自动改文件（理由见 §5）。

---

## 1. 怎么用：先分模式，再走流程

**两种模式（先判这是新 repo 起手还是老 repo 体检）：**

- **A · Bootstrap**（新建 repo 起手 / 老 repo 缺契约骨架想补齐）→ 生成默认 CLAUDE.md（含落点规约表）+ 按类型预建文件夹骨架。**见下方「⬛ Bootstrap 模式」节**（它复用 §2 判类型）。
- **B · Audit**（老 repo 体检合规）→ 下面三步，只 check 不自动改：

1. **判 repo 类型** → 定「默认期望档」（§2）。
2. **扫信号** → 信号决定「这个 repo 实际该查哪些项」（§3，type 定默认、signal 定实查）。
3. **出报告** → 合规 ✅ / 整改建议（按需语气 + 优先级 + 具体动作指针）/ 按类型不适用（§5）。

> 盘点 repo 结构时若文件多，派 Explore subagent 一次性平行盘，别自己串行 Glob/Read。

---

## 2. 判 repo 类型（type 定默认期望）

| 类型 | 判定信号（自动探测 + 不确定时问用户） | 默认期望档 |
|---|---|---|
| **production**（生产/交付） | 有 `mc-progress/` 或大量产物目录 / 有对外交付物 / 有 pipeline 脚本 | 全套（**v2** 展开，见 §6） |
| **learning**（学习/实验） | CLAUDE.md 自称实验/学习 / 以 `[feature-XX]` 分主题 / 无交付压力 | 精简集（**v1 主战场**） |
| **KB**（中央知识库/被策展层） | 是 skills/agents/principles 的单一事实源 / 经 junction 覆盖多账号 | 策展档（特殊形态，对齐 KB `decisions/kb-memory-boundary.md`；**别套通用模板**，v2 再立） |

> ⚠️ **单 repo 可跨多类**（Wu Prj 同时是 production+learning+team；本 repo 是 learning 却有 team 实验+skills）。所以类型只定**默认期望值**，真正查哪些项由 §3 的**信号**决定——不要按类型二选一硬套清单。
> 类型探测不确定时停下问用户「这个 repo 算哪类」，不强行猜。

---

## 3. 检查清单（signal 定实查）

> 图例：✅必须　🔶推荐　⬜按需（**有对应信号/痛点才查**）　— 不适用
> **signal 列 = 命中该信号才把此项纳入实际检查**；没命中则跳过（呼应 §0 少做）。

### L1 契约/状态/记忆层　【v1 重点】

| 检查项 | 触发信号 | production | learning | 整改动作 |
|---|---|---|---|---|
| `CLAUDE.md` 存在 | 任何 repo | ✅ | ✅ | 无则建最小契约骨架 |
| `CLAUDE.md` 已三层拆分 | 超 100 行 / 混带日期演进史 / §N 跨文件引用 >20 | ✅ | 🔶 | **走 §4 三层拆分子流程**（全套判据+STATE.md 模板+迁移步骤+坑） |
| `STATE.md` 存在 | 出现变更日志 / feature 状态 / 带日期"已停/已废"演进史 | ✅ | 🔶 | 承接演进史；纯实验 repo 无演进史可缓 |
| 记忆层 `MEMORY.md`（+ auto-memory/memory 分桶） | 已有反射经验/feedback 类内容散落 | ✅ | 🔶 | — |
| **`CLAUDE.md` 声明「落点规约」节**〔P0·新〕 | 任何 repo（痛点 2 的根） | ✅ | ✅ | **缺＝P0 必改**（唯一破「按需」语气的项，理由见下 L1+）；整改＝按 Bootstrap §B.1 对应变体把「顶级文件夹落点规约表」补进 CLAUDE.md。**KB 型豁免**（被策展读库本就无落点规约，见 §2） |

### L1+ 落点合规（痛点 2 专项　【新增】）

> 这是本 skill 的根需求之一：管住「每个冷会话怎么顺手怎么放过程文件、用户最后找不到」。两条都查。

1. **〔P0〕CLAUDE.md 有没有「落点规约」节** —— 见上表。这是**唯一破「§0 少做·按需」语气**的检查项：缺它不是「可缓」而是 P0 必改——因为 CLAUDE.md 是每个冷会话**唯一自动加载**的层，没有这张表就管不住未来任何一次随手乱放（skill 按需触发、冷启动不读，救不了；auto-memory 定位是高频反射 inbox、放结构契约错位）。整改指针 → Bootstrap §B.1（按 §2 type 选 production / learning 变体）。
2. **〔P1〕磁盘游离过程文件检测** —— 扫根目录有无散落的执行产物却无归位：散放 `*.py` 脚本、孤立 `debug-*.md` / `mc-debug*.md`、批量 `*.json` / `*.html` / `*.xlsx` / `*.png` 产物等。命中判据＝该进某夹的产物散在根（如有 `mc-debug*.md` 却无 `mc-debug/` 收纳、根级脚本未进 `[feature-XX]/` 或 `mc-progress/`）。报告**列清单 + 逐个建议归位**（按该 repo 落点规约表的「该类型→该去哪」），**不自动移动**（check-only，见 §5）。
   > ⚠️ **从宽**（呼应 §0 + L4「check 从宽」）：契约/状态/导航 md（CLAUDE / STATE / MEMORY / README / `*-task` / team-progress）+ learning 变体允许的**根级讨论 md** 都不算游离；只揪「明显该进某夹的执行产物散在根」，别把正常根文件刷成假阳性。

### L2 计划/执行/复盘层　【production 为主，v2 展开细则】

| 检查项 | 触发信号 | production | learning | 整改动作 |
|---|---|---|---|---|
| `mc-plan/`（main-plan + sub-plan-NN-*.md） | 有多步/多 feature 规划需求 | ✅ | ⬜ | **硬规约：只放 plan md，脚本/台账/备份禁入** |
| `mc-progress/` | 有脚本+产物需组织 | ✅ | ⬜ | 形态=`scripts/{probe,ledger,classify,report,...}/ 领域动词子目录+各 README`（function 轴）；产物按 topic 轴；备份按 time 轴。learning repo 用 `[feature-XX]/{tools,output}` 即可。**★复用意图维度（正交于功能轴）**：`scripts/` 下 **repo 私有散件躺扁平 `scripts/{功能}/`**（好复用、不炸夹）；**skill 候选簇（互相 import／抽了公共模块／总一起跑）收进自足子夹 `scripts/<簇名>/`**（自带公共模块+README，子夹住 scripts/ 底下不新建顶级夹→不炸夹）。**解耦硬规矩：簇只 import 自己子夹内、禁伸出去引兄弟功能轴脚本／禁硬编码项目私料路径**——守住则将来整夹拎出即成 skill（见 §B.3）。毕业信号见 §B.3 |
| `mc-debug/`（mc-debugNN-*.md 架构讨论/复盘） | 有设计决策/复盘 | 🔶 | ⬜ | — |
| 全局**权威档/真相源**（台账.xlsx 或品类总档） | 有多产物/多口径需统一 | ✅ | ⬜ | 多产物项目须有唯一事实源 |
| **`spec-gate-*.md`（开工门禁/规格签字冻结）** | 有批量改造/放量前需冻结规格 | ✅ | ⬜ | 探测→拟规格→**用户签字冻结为基线**→才放量；对齐 `references/task-decomposition.md`「两段合同 plan 批准制」。配 `批量改造开工门禁` 类 skill |

### L3 协作/自动化层

| 检查项 | 触发信号 | production | learning | 整改动作 |
|---|---|---|---|---|
| `team-task.md` + 根 `team-progress.md` + `team-progress/` 归档目录 | **检到任一 team 文件 / 会用 `/team-task`** | 🔶 | 🔶 | 三件套要齐（缺归档目录会让建队前归档步骤无落点） |
| `todays-task.md` | 用 `/today` 流程 | 🔶 | 🔶 | — |
| `Loops/`（README + 队列态 + 确定性验收器 verify_*.py 三件） | 有重复自驱 loop | ⬜ | ⬜ | 对齐 `references/loops-and-automation.md`；⚠️写操作不无人值守 |
| `.claude/commands/*.md`（slash/role/loop 注册） | 有自定义命令需求 | ✅ | 🔶 | — |
| `skills/*.md`（含子包 SKILL.md） | 工作流已成熟可固化 | ✅ | 🔶 | — |
| 未来：`coordination/`（跨 worktree 看板） | **多 worktree 并行（现无则不查）** | ⬜ | ⬜ | **现在不做、规范留位**；⚠️须放 repo 外公共区，不放 worktree 内 |

### L4 命名约定（跨类型通用，命中即查；check 从宽避免假阳性）

| 约定 | 规范 | check 口径 |
|---|---|---|
| 临时文件 | `__tmp_*`（双下划线前缀） | 严判 |
| 备份 | 可溯源即可（含 topic 或时间戳之一；理想 `*.before-{topic}-yyyymmdd-HHMMSS`） | **从宽**——现实常混用多种格式，只要可溯源就放行，别刷假阳性 |
| 冻结规格 | `*-FROZEN.md` | 严判 |
| 共享/管理目录 | `【名称】/` | 提示 |
| 改配置/CLAUDE.md 前 | 必先备份 `.bak` | 硬规则 |

---

## ⬛ Bootstrap 模式（新建 repo 起手生成骨架）

> 何时用：**新建 repo 起手**，或老 repo 缺契约骨架想补齐。与 audit（体检已有 repo）互补，复用 §2 判类型。
> 由来：解决用户两个痛点——①新建 repo 徒手命名文件夹易手滑敲错；②（更重）每个 task 都是新会话，过程文件怎么顺手怎么放、Claude 每次放的地方都不一样、用户根本找不到。
> **核心架构判断（痛点②为什么只能靠 CLAUDE.md）**：痛点②根因＝**冷 Claude 不知落点**。而每个冷会话**唯一自动加载**的是 CLAUDE.md（项目级 + `.claude/` 级）；**skill 按需触发、冷启动不读 → 救不了**；auto-memory 虽常驻但定位是高频反射 inbox、放结构契约错位；hooks 技术能注入但重复 CLAUDE.md 还更隐蔽＝过度工程（违少做）。**所以 bootstrap 的第一产物＝把「落点规约表」烧进 repo 的 CLAUDE.md。**（陪审依据：[[decisions/kb-memory-boundary]]「CLAUDE.md 从第 1 轮激活边界规则」+ `references/loops-and-automation` §1「loop 与 skill 正交」明确 skill ≠ 每会话自动激活。）
> 所以 skill 对痛点②是**双向**的：bootstrap 时把规约表写进新 repo 的 CLAUDE.md；audit 时（§3 L1+）检查每个 repo 有没有这张表。

### B.0 不黑箱纪律（先读）

- 主 Claude 读 skill → 据 repo 类型（§2）选模板变体 → **动手前先列「将创建的文件/文件夹清单」给用户确认** → 再 mkdir + 写文件。
- 按 **D1 按类型决定预建**：**production 意图**的 repo 预建 `mc-plan/` `mc-progress/` `mc-debug/` + 各 README（用户会用、治手滑）；**learning** repo **不预建文件夹**、只写 CLAUDE.md（含轻量规约表）。
- 关键洞察：**规约表的存在本身就让「延迟建夹」不再有痛点**——痛点②是「冷 Claude 不知落点」而非「文件夹不存在」。所以空 repo 声明规约表（零成本契约）即可，物理建夹留给第一个 plan 落地时按表即时创建（空夹＝噪音 + 误导「必填」）。
- **bootstrap 只对新 repo 建新文件**；对已有文件仍 **check-only**（不自动改，见 §5 三条硬依据）。

### B.1 默认 CLAUDE.md 最小模板（两变体 · KB 缺此模板，本次补）

**production 变体——核心是落点规约表（最小普适内核）：**

```markdown
# CLAUDE.md — <repo 名> 项目契约
> 本文件 = 契约层（不可变硬规则 / 落点规约 / 命名约定）。
> 项目状态/变更日志/近期决定 → STATE.md（出现演进史时分层，见 mc-scaffold-audit §4）。
> 反射记忆 → .claude/auto-memory/（每会话自动加载）。

## 1. 本 repo 是什么
<一句话定位 + 主要产物>

## 2. 顶级文件夹落点规约（每个会话务必遵守）
工作产物按职责归位，不要混塞。目标文件夹不存在时先创建再放。
| 文件夹 | 只放什么 | 不放什么 |
|---|---|---|
| mc-plan/ | 计划类 md（main-plan / sub-plan-NN-xxx） | 脚本、产物、复盘 md |
| mc-progress/ | 执行产物：脚本、台账、输出、备份 | 计划 md、架构讨论 md |
| mc-debug/ | 架构讨论 / 计划制定 / 复盘类 md | 执行产物、计划 md |
| .claude/ | 命令、agent、memory（harness 管） | 工作产物 |
> 新增/重命名顶级文件夹须同步更新本表。
<!-- 脚本若成簇要析出 skill → 收进 scripts/<簇名>/ 自足子夹、守解耦规矩（只 import 子夹内），见 §B.3 -->
<!-- 🔶 按需（出现信号再加，别预建）：
     - STATE.md：出现带日期演进史/变更日志时分层
     - team-task.md + team-progress.md + team-progress/：用 Agent Teams 时建 -->

## 3. 命名约定
- 临时文件：__tmp_*（双下划线前缀，便于清理）
- 备份：*.before-{topic}-yyyymmdd-HHMMSS（可溯源即可）
- 冻结规格：*-FROZEN.md
- 共享/管理目录：【名称】/
- 改配置/CLAUDE.md 前：必先备份 .bak
```

**learning 变体（D2 ＝ 轻量内聚式）——把上面 §2 表换成：**

```markdown
## 2. 顶级文件夹落点规约（每个会话务必遵守）
本 repo 按主题内聚，过程文件不要散落根目录。
| 位置 | 放什么 |
|---|---|
| [feature-XX-主题]/ | 该主题的一切：tools/（脚本）+ output/（产物）内聚一处 |
| mc-debug/（或根级 *-讨论.md） | 跨 feature 的架构讨论 / 复盘 md |
| .claude/ | 命令、agent、memory |
> 目标文件夹不存在时先创建再放。
<!-- tools/ 里脚本若成簇要析出 skill → 收进 tools/<簇名>/ 自足子夹、守解耦规矩，见 §B.3 -->
<!-- 🔶 按需（别预建）：mc-plan/、mc-progress/——当出现多步规划/大量脚本产物需统一组织时再建 -->
```

### B.2 文件夹 README 骨架（仅 production 预建时随文件夹生成）

每个预建文件夹放一份极薄 README，写明「只放什么/不放什么」，让冷会话进到夹里也有就地契约：

```markdown
# mc-plan/ —— 只放计划类 md
- ✅ 放：main-plan.md、sub-plan-NN-xxx.md（多步/多 feature 规划）
- ❌ 不放：脚本、台账、产物、架构讨论/复盘 md（→ mc-progress/ 或 mc-debug/）
```
```markdown
# mc-progress/ —— 只放执行产物
- ✅ 放：脚本、台账、输出、备份（按 topic/function/time 轴自行再分，按需建子目录）
- ❌ 不放：计划 md（→ mc-plan/）、架构讨论 md（→ mc-debug/）
```
```markdown
# mc-debug/ —— 只放架构讨论/复盘 md
- ✅ 放：mc-debugNN-xxx.md（设计决策、路线讨论、事后复盘）
- ❌ 不放：执行产物（→ mc-progress/）、计划 md（→ mc-plan/）
```

### B.3 最小普适内核 vs 不抄的域内专属（防「候选 B 翻版」）

> 模板**只固化普适内核**；把某个成熟 production repo（如 Wu Prj）的局部最优硬抽成所有新 repo 普适 ＝ KB `repo-map.md`「候选 B 被否」教训的翻版。用 principles 三连问逐行筛，切三档：

- ✅ **进默认模板**（真普适内核）：`mc-plan/`（计划 md）、`mc-progress/`（或 learning 的 `[feature-XX]/`）（执行产物）、`mc-debug/`（架构讨论/复盘）、`.claude/` + 硬底线句「目标文件夹不存在先创建再放；新增/重命名顶级文件夹须同步更新本表」。
- ✅ **进普适内核（2026-07-04 新升 · 陪审 v2 过）· 复用意图维度 + 解耦硬规矩**：`scripts/`（或 `tools/`）下 **repo 私有散件躺扁平 `{功能}/` vs skill 候选簇收进自足子夹 `<簇名>/`**；**簇只 import 自己子夹内、禁伸出去引兄弟功能轴脚本/禁硬编码私料路径**。〔**豁免下方「第二个 production repo 验证后才升普适」样本门槛**：这两条是「能否析出成 skill」的**通用软件工程切面、不含任何 repo 业务语义**，那道门是给"业务结构分法"设的、非通用原则。〕**但落地形态：bootstrap 模板只放一行注释指针、整条规矩落 audit 侧**（§3/L2 整改动作 + §5 指针），不烧进每个新 repo 冷启动 CLAUDE.md（防过早抽象/CLAUDE.md 变厚）。
- 🔶 **模板留注释占位、不写内容**：`STATE.md`（出现带日期演进史再分层，指向 §4）、team-task 三件套（用 Agent Teams 才建）——写成被注释的「按需」行、不预填。
- ❌ **不进模板**（域内专属，留原 repo，v2 有第二个 production repo 验证后再说）：scripts **具体分几个业务子目录**（probe/ledger/classify/... 的业务分法）、台账 xlsx 三轴、templates/、spec-gate-*、Loops/。〔注意区分：「按什么业务再分子目录」仍域内；但「散件扁平 vs 可析出簇进自足子夹」的**落点分法**已升普适（见上条）。〕
- **判别口诀**：**「过程文件三大类（计划/产物/复盘）的去向」+「散件 vs 可析出簇的落点分法」是普适的；「产物内部按业务再分几个 scripts 子目录 / 台账什么轴」是域内的。模板只固化前者（且复用意图/解耦规矩落 audit 侧、模板只留注释指针）。**

---

## 4. L1 子流程：CLAUDE.md 三层拆分（原 skill 全文保留）

> 当 L1 判定「`CLAUDE.md` 需三层拆分」时，执行本节。这是原 `claude-md-three-layer-refactor` 的完整内容，作为 mc-scaffold-audit 的 L1 整改动作。
> 注意：**只出整改建议指针**（报告里指向本节步骤），真正拆分仍逐段 Edit + 先 Read 确切字节、人工执行（见 §5）。

### 4.1 拆分判据：什么留 CLAUDE.md / 什么迁 STATE.md

**留 CLAUDE.md（契约层）**：
- 硬规则 / 禁止事项（如「禁用 position:absolute」「染色双闸门」）
- 顶层目录骨架（**不含**每个 feature 的内部脚本演进史）
- 自定义命令表 / 角色清单
- 跨场景执行行为规范（防卡顿、记忆纪律、超时硬约束等）
- 任何「换会话/换协作者也不变」的约束

**迁 STATE.md（状态层）**：
- 变更日志（changelog）整张表 + 入表标准说明
- 当前活跃 feature 的进度/卡点/下一步
- 近期架构决定（带日期，可能被未来决定推翻）
- "X 已停 / Y 已废 / Z 已归档" 这类生命周期标注

**判别问句**：「这条内容 6 个月后还会一字不改吗？」✅ 是 → 契约 → CLAUDE.md；❌ 否 → 状态 → STATE.md

### 4.2 命名约定（重要）

**用 `STATE.md`，不要用 `PROGRESS.md`**——
- `STATE.md` = 项目级状态（changelog + 当前 feature 状态 + 近期决定）
- `PROGRESS.md` 留给未来「跨 worktree 实时看板」——⚠️ **不放 worktree 内**（须放 git repo 之外的公共区）
- 两者语义不同：STATE 是项目快照，PROGRESS 是实时进度。一上来叫 PROGRESS.md 会与未来协调层同名冲突。

> 位置修正（2026-06-02）：原写 `.claude/coordination/PROGRESS.md` 在 worktree 内 = 位置错误，已废弃。根因：worktree working tree 文件隔离，跨 worktree 共享必须在 repo 之外有公共一份。

### 4.3 迁移操作步骤（按顺序）

**Step 1：盘点引用**
```powershell
grep -rn "CLAUDE\.md.*§" .
grep -rn "变更记录\|changelog" .
```
统计 §引用数量、识别哪些是「操作指引」（要改）、哪些是「历史事实陈述」（不改）。

**Step 2：创建 STATE.md（项目根）** —— 模板：
```markdown
# STATE.md — 项目状态 / 变更日志 / 近期决定

> 最后更新：YYYY-MM-DD
> **与 CLAUDE.md 的分工**：CLAUDE.md = 不可变契约；本文件 = 会演进的状态。
> **与未来「跨 worktree 实时看板」的分工**：本文件 = 项目级状态；跨 worktree 看板 = 多 worktree 互看的实时进度（**未启用**）。⚠️ 须放 git repo 之外的公共区，不能放 worktree 内的 `.claude/coordination/`。

## 1. 变更日志
> 入表标准：[从原 CLAUDE.md changelog 节搬过来 + 反例]
| 日期 | 变更内容 |
|------|---------|
| [迁原表全部行] | ... |

## 2. 当前 Feature 状态
> ### [featureXX-...]
> - 当前阶段： / 在跑·卡点： / 下一步： / 关键文件指针：

## 3. 近期决定
> - YYYY-MM-DD ｜ {决定} ｜ {详情链接}
```

**Step 3：瘦身 CLAUDE.md**
- 顶部「最后更新」下方加一行：`> 项目状态 / 变更日志 / 近期决定已迁至 [STATE.md](./STATE.md)`
- 删 changelog 整节，替换为：`> 📌 项目状态 / 变更日志 / 近期决定 → 见 [STATE.md](./STATE.md)`
- §1 文件结构图：保留顶层骨架，删每节带日期的演进史长注释，改一行指针「演进详见 [feature*]/plan*.md 与 STATE.md」
- §1 结构图加 STATE.md 条目（与 CLAUDE.md 并列）
- 保留 §0/§1/§2/§3/§4 章节号不变 → 原 §N 引用零改动

**Step 4：mc-update.md 同步（若项目用 mc-update 流程）**
- 第 4 步标题改「CLAUDE.md / STATE.md 同步检查」
- 变更日志步骤指向 `STATE.md §1 变更日志`
- 结构性变更触发条件精化：「新建**顶级目录** / 新增**工作流场景** / 新增**跨 feature 约定**」
- grep 命令路径分列（PowerShell 不支持 `{a,b}` brace expansion）

**Step 5：引用迁移（关键决策）—— 只改「当前操作指引」，不改「历史事实陈述」**
- ✅ 改：`"用 mc-update 更新 CLAUDE.md 变更记录"` → `"...更新 STATE.md §1 变更日志"`；fix-*.md 里的待办指令
- ❌ 不改：「PDF_CATEGORY 与 CLAUDE.md §5 4 大类硬约定四源对齐」这类陈述当时事实的话；debug-*/mc-debug-* 等凝固态档案
- CLAUDE.md 末尾的「→ 见 STATE.md」指针为所有 dangling 旧引用提供重定向锚点。

### 4.4 三层拆分验证清单
- [ ] **结构**：`ls` 根确认 `STATE.md` 存在；`wc -l CLAUDE.md` 比改前明显下降（典型 20-40%）
- [ ] **引用 A**：grep 原 §N / "变更记录" 残留命中应只在 (a) STATE.md 迁移说明 (b) plan/debug 凝固档 (c) 改造方案文档自身
- [ ] **引用 B**：grep `STATE\.md` 应见 5+ 处新引用
- [ ] **章节稳定性**：grep `CLAUDE\.md.*§[0-4]` 数量等于改前
- [ ] **冒烟读**：新开会话加载 CLAUDE.md，无残留状态描述、目录树注释干净

### 4.5 三层拆分常见坑
1. **全角 vs 半角标点**：中文 CLAUDE.md「上限，」是全角逗号，Edit 的 old_string 写 ASCII 逗号会匹配失败 → 先 Read 确切字节
2. **直接 Set-Content/Out-File 覆盖 CLAUDE.md** 会被 auto-mode 拦截 → 用 Edit 逐段替换
3. **凝固态档案误改**：plan-*/debug-*/mc-debug-* 里的「§5 ...」陈述当时事实，不要改成 STATE.md（会引入虚假回溯）
4. **changelog 入表标准漏迁**：原表头「入表标准 + 反例」必须连表一起迁到 STATE.md §1
5. **§1 结构图 STATE.md 漏加节点**：拆完忘把 STATE.md 加进结构图
6. **PROGRESS.md 命名误用**：别一开始就把状态文件叫 PROGRESS.md（与未来跨 worktree 看板同名冲突）

---

## 5. check 报告格式（只 check 不 fix）

skill 跑完产出一份报告，**不自动改文件**（理由：KB `principles.md`「编排权留主 Claude / 不要全自动黑箱」+ 硬规则「改 CLAUDE.md 前先备份 .bak」+ §4.5 坑#2「Set-Content 覆盖被 auto-mode 拦」——自动 fix 会撞这三条）。

```
# 脚手架合规报告 — <repo 名>
repo 类型判定：learning（信号：CLAUDE.md 自称实验 repo + [feature-XX] 分主题；另检到 team 文件 → 叠加查 L3 协作）

## 合规 ✅
- CLAUDE.md 存在且 .claude/CLAUDE.md 分工清晰
- team-task.md + team-progress.md + team-progress/ 齐备

## 整改建议（按优先级；语气=按需，非硬性待办）
❗ [P0] CLAUDE.md 无「落点规约」节 —— 痛点 2 根因，没它每个冷会话都乱放过程文件、用户找不到
        → 按 §B.1 learning 变体补「顶级文件夹落点规约表」（**唯一破「按需」语气的必改项**，见 §3 L1+）
🔶 [P1] 根 CLAUDE.md ~50 行混入多条带日期教训
        → 触发 L1 三层拆分判据；建议拆出 STATE.md 承接演进史，动作见 SKILL §4.3 Step 2-5
🔶 [P1] 根目录散落 3 个 .py 脚本 + parse-*.md —— 游离过程文件（§3 L1+ #2）
        → 建议归位：脚本 → [feature-XX]/tools/ 或 mc-progress/scripts/（**若是 skill 候选簇：互相 import/总一起跑 → 收进 `<簇名>/` 自足子夹、守解耦规矩，见 §B.3**）；讨论 md → mc-debug/
⬜ [P3] 无 mc-plan/ —— learning repo 非强制；若开始多步任务可建（没痛点就别建）

## 按类型/信号不适用（跳过，不算缺陷）
- mc-progress 三轴 / 权威台账 / spec-gate：未检到对应信号，learning repo 不要求
```

**三区**：合规 ✅ / 整改建议（P0-P3 + 具体动作指针 + **按需语气**）/ 按类型·信号不适用（明确「跳过≠缺陷」）。

---

## 6. 未来（v2+，现在不做）

- **production 全套档展开**：spec-gate 开工门禁细则 / mc-progress 三轴落地细则 / 权威台账规范 —— 这些多是 Wu Prj 域内细节，硬抽成通用规范 ROI 低、风险高，留 v2 在有第二个 production repo 验证后再做（避免「一个 repo 的局部最优当跨 repo 普适规范」，见 KB `repo-map.md` 候选 B 被否教训）。
- **KB 档展开**：对齐 `decisions/kb-memory-boundary.md` 的特殊形态。
- **coordination 跨 worktree 看板**：多 worktree 并行出现具体需求时再做；位置须 repo 外公共区。
- **可选 `--fix`**：暂不做（撞 §5 三条）。
- **KB 蒸馏**：本 skill 定稿后，建议把「先判类型→signal 实查→spec-gate 开工门禁」蒸馏进 KB `references/`（spec-gate 已被 mc-expert 陪审、是 `task-decomposition` 两段合同的落地实例，最值得入库）。

---

## 7. 落地参考

- 规范底座来源：Wu Prj「四层（契约/状态/执行/记忆）+ 三轴（topic/function/time）」体系盘点（2026-06-21）。
- 评审：2026-06-21 草案 v0 经 mc-expert 跨 repo 陪审（type+signal 主轴 / spec-gate 补漏 / 反过度工程元规则 / check-only 三条硬依据）。
- L1 三层拆分原始落地案例：Info-Classifier repo `[feature02-方彩霞ppt整理]/plan07.md`（CLAUDE.md 160→127 行 + STATE.md 71 行）。
