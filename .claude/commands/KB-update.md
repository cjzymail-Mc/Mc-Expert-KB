中央 KB（本 repo）专用的固化/更新流程。**本 repo 不是普通工作 repo，是被策展的稳定层**——别套用通用 `mc-update`（那套 auto-memory/memory 归属、fix*.md、Mc-debug、STATE.md、feature 目录在这里都不适用）。

> 立身原则：薄 / 稳定 / 人工策展 / 不污染源 repo / 做减法。依据 [[principles]] 入库判据 + [[decisions/kb-memory-boundary]]。

## 前置步：发现巡检（discovery sweep）——仅"主动巡检"场景跑

> 区分两种调起：① **手上已有候选**（刚做完某任务、想固化某条经验）→ 跳过本步，直接第 0 步。② **主动巡检**（"去看看源 repo 攒了什么该入 KB"，如今天这类）→ 先跑本步，把"我还不知道的候选"挖出来，再交第 0 步闸门。
> 性质：**只读源 repo + 只产候选清单**，幂等、零红线（呼应 [[references/loops-and-automation]] §7 只读/幂等才安全）。**事件驱动手动调起，不定时自跑、不无人值守**（KB 晋升判断本就要人在场）。
>
> ⚠️ **③ 硬事故即时收割（攒批节奏的例外）**：安全阀/事故类经验（halt 死锁 / 销毁性误操作 / 合规红线被触 / 跨入口契约漂移）一旦产生，**当场就走 ① 模式即时收割入 KB，别攒到下次巡检批量处理**——这类多是"严重度豁免"候选（单次高危即可入，不必凑频次≥3），拖着会像 `decisions/autopilot-defer-perm-to-human-gate` 那样**孤儿滞留源 repo 数天、跨入口长期不同步**（该决定 2026-06-20 产生、滞留 5 天才收割）。一般经验仍走攒批/巡检节奏。

1. 读 `MEMORY.md`「巡检台账」拿各源 repo 的**扫描截止(基线)日期**。
2. 只读扫各源 repo **晚于基线**的过程文件（memory / auto-memory / plan / debug / skills / CLAUDE / STATE），**忽略 office/pdf/ai 原材料**。富矿 repo 深扫到"生成产物层"（plan/思考/方法论 md），不止 auto-memory。
3. 每个候选先过第 0 步三重闸门预判，分档：强入 / borderline / 不入（注明理由），落成候选清单。
4. **更新「巡检台账」**：刷新扫描截止日期 + 本轮结论摘要（即便"无新增可入"也记一行，证明扫过了）。
5. 候选清单交第 1 步等用户挑。**到此停，绝不自动写内容层。**

## 第 0 步：要不要入 KB？（三重闸门，全过才写）

KB **默认不入**——多一份 = 多一份维护负担、拉低信噪比。任务完成 ≠ KB 必有更新。

1. **新增对照价值闸**（principles 三连问，任一"否"即不入）：
   ① 引入既有 KB 没有的形态/对照点/边界条件？ ② 会被反复引用？ ③ 维护成本 < 新增价值？
2. **频次闸**：这条 1 年内会被≥3 次需要吗？否（一次性反思 / git log 已是真相）→ 不写。
3. **去重闸**：Grep 工具或 `rg '<topic>' principles.md reflexes.md repo-map.md decisions/ references/` —— 已完整覆盖 → 不写；部分覆盖 → append，**不另起新条目**；完全没有 → 才允许新建。

> ⚠️ **domain 细节不入 KB**：具体染色契约 / 槽位坐标 / 某 COM quirk / 某条源 memory 原文 —— 留源 repo，`repo-map.md` 给指针即可。KB 只装"偏好/决策/反射 + 路标"。

## 第 1 步：列候选等用户审核

列出候选 + 拟落位的层，按重要性排序，**等用户挑**，不直接动手。

## 第 2 步：KB 内容层归属

| 内容性质 | 归属文件 | 卡片格式 |
|--|--|--|
| 用户决策偏好 / 跨主题元规则 | `principles.md` | 自由条目 + 用户原话 |
| 跨 repo 已决决策（**不重判，互链**） | `decisions/<slug>.md` | 决策/日期/理由/现状/何时重新评估/原档指针/相关 |
| 跨 repo 硬反射（**双 repo 命中**才算真反射，挂命中 repo） | `reflexes.md` | 一句反射 + 〔命中 repo〕 |
| 源 repo 地图 / 决策溯源指针 | `repo-map.md` | 每 repo 一段 / 溯源表一行 |
| 外部事实（CC 机制 / 权限 / API 等） | `references/<slug>.md` | **必标核实日期 + 易过期警示** |
| KB 内务决策（如 memory 边界 / agent 部署） | `decisions/<slug>.md` | 同决策卡 |
| 未晋升的原始反馈 | `.claude/auto-memory/`（**inbox，不是内容层、不进 KB git**） | 原样落，待晋升 |

**红线**（[[decisions/kb-memory-boundary]]）：`.claude/auto-memory/` = 待审 inbox，**绝不自动 merge 进内容层**；晋升必须人工过第 0 步闸门。

## 第 3 步：执行（仅对用户挑中的）

1. 按去重闸落位：部分覆盖 → append；完全没有 → 才新建。
2. 写文件：frontmatter（`name`/`description`/`type`）或决策卡格式；**互链** `[[name]]`（链相关偏好/决策/反射，链不存在的 slug 也行=标记待写）。
3. **更新 `MEMORY.md` 索引**（这是每会话加载的总索引）：加一行 `- [Title](path) — hook`，分类正确（核心文档 / decisions / references / agents / Stage 状态）。
4. references 类：核实日期 + "易过期"一行 + Stage 复核指针（若承重某决策）。
5. **`.gitignore` 边界自检**：新增是**内容层**(principles/decisions/reflexes/repo-map/references/MEMORY.md/CLAUDE.md/agents) → 该进 git；是 **inbox/工具/scratch**(auto-memory/commands/skills/todays-task) → 该忽略。新增类别若不在 .gitignore 覆盖内，提示用户补。
6. **`CLAUDE.md` 同步检查**（保持薄！）：仅当新增**顶级结构** / **新边界规则** / **新导航入口**时才动 CLAUDE.md，且**只加指针,绝不复制内容**（违反就是它自己禁的"别散在 CLAUDE.md"）。
7. 挪/删文件后 grep dangling 互链并修；凝固态档案（已封决策卡的主体）不回溯篡改，只改头部状态。
8. **references 事实条目被实证推翻** → 就地订正 + 瘦成指针、正文下沉到新权威节（区别于 decisions/ 的"不回溯篡改"——references 本就随实证/版本更新，这是其设计用途，不算篡改）；且**收口单一权威前先 `rg '<旧口径关键词>'` 把同口径散点全揪**（同一旧结论常散在 注 / FAQ / 正文 多处），逐处降为"指向权威节的一句指针"，别只改一处、留 KB 内部自打架。〔2026-06-18 idle-零正文收口实战 + mc-expert 陪审〕

## 反例（KB 专属）

- ❌ 默认入库 / 任务完成必更新 KB（KB 做减法，git log + 源 repo 已是真相）
- ❌ 把 domain 细节复制进 KB（该留源 repo，repo-map 给指针）
- ❌ auto-memory 自动并入内容层（违 kb-memory-boundary 物理隔离）
- ❌ 重新辩论已封的 decisions/（要推翻才动，否则只互链引用）
- ❌ references 不标核实日期 / 不标易过期
- ❌ CLAUDE.md 里塞 principles/reflexes 内容副本（双份漂移）
- ❌ 同主题已有条目还新建近似条目（该 append 就 append）
- ❌ 删/移文件不更新 MEMORY.md 索引与互链（dangling）
