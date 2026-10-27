# decision · dual-tool-single-source

**决策**：Claude Code 与 Codex CLI 双工具协作时，**知识层（角色 / skill / runbook / memory / 生产脚本）只维护一份**（单一真源），两个工具各配一个 **~5 行薄 shim** 指向真源 + 机制差异说明。机制差异（Claude 的 Plan mode/auto-memory junction vs Codex 的 hooks/sandbox/agents）只算**「入口适配」**，**不是「两套知识」**。

> 一句话：**「两套 skill / 两套角色」是伪命题**——5 个角色 `.claude/commands/role-*.md` 与 `.codex/prompts/role-*.md` 字节级一致，都是指向 `[work-flow-rebuild]/roles/<role>.md` 的 ~5 行 shim。AGENTS.md（Codex 读）= 共享契约单源；CLAUDE.md 收缩为 Claude-only 入口。

**日期**：2026-05-15（STATE 定「剥离 codex 维护职责」）→ 2026-07-18（skill 统一 plan 冻结 + today-loop P-A→P-D 自动验收 PASS）

**理由**：
- 两工具的**知识**（做什么 / 怎么做 / 角色职责 / 经验反射）是同一套——不存在"Claude 版知识"和"Codex 版知识"。维护两份 = 双份漂移，改一处漏另一处（实例：Agent-3 starter 的 README「全程 COM 严禁」↔ runbook「明文首选 python-docx」就因 COM-free 默认决策从未回灌 starter 而长期自相矛盾）。
- 两工具真正不同的是**机制层**（谁能读 memory / 怎么跑 hook / 沙箱怎么开）——这一层差异**封闭在入口适配里**（shim + tool-adapters.md 一页纸列差异 + 各自踩坑指针），不外溢成知识分叉。
- 呼应偏好底座 [[../principles]]「稳定 > 新颖」「少做」：不为"对称"建两套，真源一份 + 入口薄适配即够。

**现状**（Agent-3 已落地）：
- 5 角色 shim 字节级一致，以 `[work-flow-rebuild]/roles/` 为唯一正文（`diff` 验收全空）。
- AGENTS.md = Codex 端契约单源（含「禁止在 `.claude/commands` 与 `.codex/prompts` 各写一份角色逻辑」明文）；CLAUDE.md 收缩为 ~15 行 Claude-only 入口。
- `[work-flow-rebuild]/tool-adapters.md` 一页纸列两工具机制差异 + 踩坑指针。
- 2026-07-18 `$today-loop` P-A→P-D 自动验收 PASS（机制有效）；干净机器 Office 全链 + 视觉核验 + 对外交付仍留 loop 后**人工验收**（不因自动 PASS 冒充）。

**何时复用此判断**：任何「要不要为工具 X 单独写一份 skill / 角色 / 文档」的评估。结论：知识只一份，差异只进入口适配层。只有当某工具的机制差异导致知识**真要分叉**（如某操作只在一工具成立）时才例外，否则单一真源。

**何时重新评估**：出现"某条知识在两工具表现确实不同、单一真源无法覆盖"的实例 → 才考虑分叉。当前（2026-07-18）未出现。

**原档指针**：
- 决策冻结 + 目标架构：`[Agent-3 Claude+Codex] Info Classifier/plan-skill-unification.md`（§0.1「两套 skill 是伪命题」/ §1 目标架构 / §5.2 冻结决策）
- 验收记录：`Debug/today-loop/20260718-skill-unification/results/FINAL_AUDIT.md`
- STATE 原始决策：`[Agent-3] STATE.md` 2026-05-15「剥离 codex 维护职责」

相关决策：[[orchestrator-route]]（协作 ≠ 控制，同类"别为对称造复杂度"克制）、[[kb-memory-boundary]]（KB 也守"内容层一份、别双份漂移"）；偏好底座 [[../principles]]（稳定 > 新颖 / 少做）；跨工具 memory 加载机制差异见 [[../references/claude-codex-memory-difference]]（机制层差异的事实底本）。
