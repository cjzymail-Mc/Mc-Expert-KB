# decision · kb-memory-boundary

**决策**：在 `Mc-Expert-repo`（中央 KB）内，memory 机制**两层分治**，与源 repo 的 auto-memory 定位**相反**——这个 repo 特殊，是"被策展的元记忆库"，不照搬源 repo 的"全量自动累积"。

| 层 | 是什么 | 规则 |
|---|---|---|
| **KB 内容层** `principles` / `decisions` / `reflexes` / `repo-map` / `references` | 跨 repo 知识的**策展成品**（薄、稳定） | **只经入库判据闸门人工进入；绝不被 auto-memory 自动写入/merge** |
| **`.claude/auto-memory/`** | 待审**收件箱（inbox）**、原始捕获缓冲 | session 原始反馈先落这；**晋升进内容层走三连问判据 + `mc-update`，人工策展** |
| **KB 元进度**（Stage / 已入 / 已否 / 续接） | 策展**过程**记忆，非成品 | 由 `MEMORY.md` 状态段 + 决策溯源子索引承担，**不另立机制** |

**日期**：2026-06-01

**理由**：
- 本 repo 与源 repo（3rd-ppt / Agent-3）的 memory **功能相反**：源 repo 要 auto-memory 自动沉淀域内经验；本 repo 是策展层，要的是**克制**。
- auto-memory「全量自动累积」与 KB 入库判据（[[../principles]] 入库/样本判据：做减法 / 默认不入 / 三连问）**方向相反**。若让它自动灌进内容层 = 污染稳定层、拉低信噪比，**毁掉 KB 立身理由**。
- 但策展**过程**仍需跨 session 续接（这 Stage 干到哪、什么入了什么被否了为啥）→ 由 `MEMORY.md` 状态段 + auto-memory inbox 承担，**与内容层物理隔离**。

**CLAUDE.md 的功能定位（本 repo）**：
- 本 repo 的 CLAUDE.md **应保持薄**。它的角色 = 主 session（=KB 策展者）每次进 repo 的**操作手册 / 导航卡**，**不是 KB 内容的副本**。
- 该装：① 一句话"这是中央 KB 稳定层"；② **本边界规则**（auto-memory=inbox、入内容层走判据闸门、别污染）；③ 导航（指向 `MEMORY.md` 索引去读哪个文件）；④ 策展节奏（"先讨论清楚再动"）。
- **不该装**：principles / reflexes / decisions 的内容本身——会和源文件**双份漂移**（违 reflexes「别散在 CLAUDE.md」）。CLAUDE.md 只**指针 + 常驻执行本边界**，知识留在各源文件。
- 分工：`decisions/kb-memory-boundary.md`（本卡）= 完整理由，按需读；CLAUDE.md = 把"auto-memory≠内容层"这条**从第 1 轮就激活**在策展者脑子里。

**现状**：`.claude/auto-memory/` 已存在（3 账号 junction 同步，含 `feedback_ppt_selfcheck.md` + 自身 `MEMORY.md`）；KB `MEMORY.md` 已在记 Stage 0/1 状态 + 决策溯源。机制已在，本决策是**定位**而非新建。

**何时重新评估**：inbox 长期积压无人晋升 → 考虑轻量 curator 流程；出现内容层被 auto 污染的实例 → 加硬校验（如 pre-commit 校验内容层只人工改）。当前都不需要。

**原档指针**：本 session 讨论（2026-06-01，Stage 1 延伸）；入库判据原文见 [[../principles]]「入库/样本判据」段。

相关决策：[[per-agent-memory-no]]（同样"不为新增复杂度、满足事故条件才引入"的克制）；偏好底座 [[../principles]]（入库判据 / 少做）；执行面 [[../reflexes]]（skills-first：别散在 CLAUDE.md）
