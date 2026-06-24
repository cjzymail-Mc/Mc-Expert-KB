# decision · scaffold-placement-via-claudemd

**决策**：「过程文件落点规约」（每个 repo 的工作产物该往哪放）**必须烧进该 repo 的 CLAUDE.md**，不能靠 skill / auto-memory / hooks 承载。配套地，`mc-scaffold-audit` 的 bootstrap 默认 CLAUDE.md 模板**只固化普适内核**（计划/产物/复盘三大类去向），不抄某个成熟 production repo 的域内专属结构。

> 适用面：任何「让每个 repo 都按统一规范组织/存放过程文件」的需求。**别拿本卡判 domain 内容该放哪**——本卡只管「落点规约这类**结构契约**该挂在哪个机制层」，不是具体某 repo 的目录细则（那留各 repo 自己的 CLAUDE.md）。

**日期**：2026-06-22

**理由（机制层级对比——为什么唯独 CLAUDE.md 能解）**：

痛点根因 = **每个 task 都是新（冷）会话，冷 Claude 不知道过程文件该往哪放**，于是怎么顺手怎么放、每次都不一样、用户最后找不到。解法必须满足「**每个冷会话冷启动就自动生效**」。逐一对比：

| 机制 | 冷会话自动加载？ | 判定 |
|---|---|---|
| **CLAUDE.md**（项目级 + `.claude/` 级） | ✅ 每次自动 | **正解**——落点规约表写这里，第 1 轮就约束 |
| **skill** | ❌ 按需/触发式 | **救不了**——冷启动不自动读，不可能每个 task 先喊一遍 skill |
| **auto-memory `MEMORY.md`** | ✅ 常驻 | **错位**——定位是「高频反射 inbox」，放结构契约是机制误用（见 [[kb-memory-boundary]]） |
| **hooks** | ✅（注入） | **过度工程**——技术能注入，但重复 CLAUDE.md 还更隐蔽，违 [[../principles]]「少做」 |

- 旁证：[[../references/loops-and-automation]] §1「loop 与 skill 正交」已明确 **skill ≠ 每会话自动激活**；[[kb-memory-boundary]] 反面印证（连 KB 自己都靠 CLAUDE.md 把边界规则「从第 1 轮激活」）。
- 推论：skill 对落点规约是**双向角色**——bootstrap 时把规约表**写进**新 repo 的 CLAUDE.md；audit 时**检查**每个 repo 有没有这张表。skill 是「写入/检查的工具」，CLAUDE.md 是「常驻生效的载体」，两者不是替代关系。

**模板「只装普适内核」（防候选 B 翻版）**：
- ✅ 进模板（真普适）：计划/产物/复盘**三大类的去向**（mc-plan/、mc-progress/ 或 learning 的 `[feature-XX]/`、mc-debug/）。
- ❌ 不进模板（域内专属，留原 repo）：产物**内部怎么再分**（某 repo 的 scripts 6 子目录 / 台账 xlsx 几轴 / spec-gate / Loops）。
- 判别口诀：**「三大类去向」普适；「产物内部再分」是域内的**。把成熟 production repo（如 Wu Prj）的局部最优硬抽成所有新 repo 普适 = [[../repo-map]] 孤儿审计「候选 B 被否」教训的翻版（一个 repo 的局部最优当跨 repo 普适规范）。

**按类型分两档落地（用户 2026-06-22 拍板 D1/D2）**：
- **production 意图** repo：bootstrap 预建 mc-plan/mc-progress/mc-debug + 各 README（用户会用、治「徒手命名手滑」）。
- **learning** repo：**不预建文件夹**，只写轻量规约表（`[feature-XX]/{tools,output}` 内聚 + mc-debug/ 或根级讨论 md）。关键洞察：**规约表存在本身就让「延迟建夹」不再有痛点**（痛点是「不知落点」非「夹不存在」），空预建反造「假甜区」+ 噪音。

**现状**：bootstrap 套件已落地 `mc-scaffold-audit/SKILL.md`（§Bootstrap 模式：两变体 CLAUDE.md 模板 + README 骨架 + B.3 普适内核切档）；audit 侧加了 P0「落点规约声明」检查 + L1+「磁盘游离过程文件检测」。KB 此前缺的「默认 CLAUDE.md 模板」空白已补在 skill 内（非复制进 KB 内容层）。

**何时重新评估**：
- 出现**第二个 production repo**且其落点结构与模板内核稳定一致 → 可考虑把更多项从「域内」升「普适」（当前样本只 1 个 Wu Prj，不够）。
- learning 变体粒度（`[feature-XX]/{tools,output}` vs 更细）若在多个 learning repo 自跑后发现误判 → 调模板。
- 若哪天 CLAUDE.md 因落点规约表变厚到违背「CLAUDE.md 要薄」（[[kb-memory-boundary]] 硬教训）→ 表留 CLAUDE.md、细则下沉各文件夹 README。

**原档指针**：完整设计 + 三方扫描 + mc-expert 5 问陪审 → `Mc-emoji/脚手架规范-v1-升级plan.md`（承接 `脚手架规范草案-v0.md`）；落地进度 → `Mc-emoji/team-progress.md` 2026-06-22 段。

相关决策：[[kb-memory-boundary]]（CLAUDE.md 要薄/auto-memory=inbox 的同源边界）；偏好底座 [[../principles]]（少做 / 入库判据）；自动化分层 [[../references/loops-and-automation]]（skill≠每会话激活的旁证）；反面教训 [[../repo-map]] 候选 B（局部最优≠跨 repo 普适）。
